import concurrent.futures
import threading
import time

from apscheduler.schedulers.background import BackgroundScheduler
import utils
from config import connect_redis, connect_db
from huobi_market import htx_swap_order, htx_trading_run, htx_setting, htx_cancel_order
from huobi_market.htx_balance import getHuobiFutureBalance


class OrderTradeHTX:
    def __init__(self, param, w_param, rdb):
        self.threading_scheduler = None
        self.param = param
        self.user_num = int(param['user_num'])
        self.coin_num = int(param['coin_num'])
        self.symbol = str(param['coin_name'])
        self.bet_limit = int(param['bet_limit'])
        self.rate_rev = float(param['rate_rev'])
        self.leverage = int(param['leverage'])
        self.rate_liq = float(param['rate_liq'])
        self.api_key = str(param['api_key'])
        self.secret_key = str(param['secret_key'])
        self.dot_digit = int(param['dot_digit'])
        self.min_digit = float(param['min_digit'])
        # 자동 청산 처리 시간
        self.auto_ctime = float(param['auto_ctime']) * 60 * 60

        self.w_param = w_param  # maker parameter
        # param [m7] s1, b1 재주문 지연 시간(초)
        self.order_one_reset_time = int(w_param['m7'])
        # param [m10] s2~s4, b2~b4 재주문 지연 시간(초)
        self.order_two_reset_time = int(w_param['m10'])
        # 체결이 일어 나지 않을 경우 주문 취소 시간(분)['m19']
        self.order_restart_time = int(w_param['m19']) * 60
        # 주문 강도
        self.strengths = [float(w_param['m1']), float(w_param['m2']), float(w_param['m3']), float(w_param['m4'])]
        # 주문 수량
        self.orderCounts = [float(w_param['m12']), float(w_param['m13']), float(w_param['m14']), float(w_param['m15'])]

        # 급등,급락 판단을 위한 계산 주기(초)
        self.break_check_time = int(w_param['w3'])

        # L-Stop 급등,급락 기준(시간)
        self.l_stop_base_time = int(w_param['w4']) * 60 * 60
        # L-Stop 등락율(%)
        self.l_stop_rate = float(w_param['w5'])
        # L-Stop 지속 시간(시간)
        self.l_stop_delay_time = int(w_param['w6']) * 60 * 60

        # S-Break 급등,급락 기준(분)
        self.s_brake_base_time = int(w_param['w8']) * 60
        # S-Break 등락율(%)
        self.s_brake_rate = float(w_param['w9'])
        # S-Break 지속 시간(분)
        self.s_brake_delay_time = int(w_param['w10']) * 60
        # S-Break 재시작 시간(분)
        self.s_brake_restart_time = int(w_param['w11']) * 60
        # S-Break 선택 정보
        self.s_brake_sel = int(w_param['w12'])

        self.l_stop_time = 0
        self.s_brake_time = 0
        self.sb_price = 0
        self.s_brake_cnt = 0
        self.l_stop_cnt = 0

        # S-Break 주문 선택
        self.s_brake_sel_num = int(w_param['w11'])
        # Broker ID
        self.brokerID = w_param['brokerID']
        self.rdb = rdb

        self.swap_order = None
        self.setting = htx_setting.HuobiSetting()
        self.live_run = None

        self.trade_scheduler = None
        self.schedule_period = 3
        self.onTradingScheduler()
        self.live_instances = []
        self.reset_time = 0
        self.is_all_close = False
        self.stop_time = 0
        self.brake_time = 0
        self.c_time = 0
        self.is_service_start = False

    def del_run(self):
        for instance in self.live_instances:
            self.live_instances.remove(instance)
            instance.shutDownCheckSchedule()
            instance.del_run()
            del instance

    def del_run_class(self):
        for instance in self.live_instances:
            if instance.class_status == 2:
                self.live_instances.remove(instance)
                del instance

    def onTradingScheduler(self):
        self.trade_scheduler = BackgroundScheduler()
        self.trade_scheduler.add_job(self.tradeScheduler, 'interval', seconds=self.schedule_period, max_instances=50,
                                     misfire_grace_time=10, coalesce=True)
        self.trade_scheduler.start()

    def shutDownSchedule(self):
        try:
            if self.trade_scheduler.running:
                self.trade_scheduler.shutdown(wait=False)
            else:
                print("Huobi trade_scheduler is not running")
        except Exception as e:
            print(f"Huobi trade_scheduler has already been shutdown. {e}")

    def tradeScheduler(self):
        try:
            if self.trade_scheduler is None:
                return
            with concurrent.futures.ThreadPoolExecutor() as executor:
                works = []
                # symbol 의 최대, 최소 가격 얻기
                work0 = executor.submit(self.getSymbolCalcPrice)
                works.append(work0)

                # 해당 코인의 전체 주문 닫기
                work1 = executor.submit(self.closeHuobiAllOrders)
                works.append(work1)

                # 포지션 된 주문이 존재 하는지 체크
                if self.is_all_close is False:
                    # B1가격 < S1가격 이면서 거래 Reset 대기 시간을 경과 하면
                    if self.order_restart_time > 0:
                        if self.reset_time >= self.order_restart_time:
                            self.reset_time = 0
                            is_comp = self.getB1S1PriceCompare()
                            if is_comp:
                                work2 = executor.submit(self.resetOrder)
                                works.append(work2)
                        else:
                            self.reset_time += self.schedule_period

                # S-Break 급등, 급락 확인
                if self.s_brake_time >= self.break_check_time:
                    work3 = executor.submit(self.checkShortBreak)
                    works.append(work3)
                    self.s_brake_time = 0
                else:
                    self.s_brake_time += self.schedule_period

                # L-Stop 급등, 급락 확인
                if self.l_stop_time >= self.break_check_time:
                    work4 = executor.submit(self.checkLongStop)
                    works.append(work4)
                    self.l_stop_time = 0
                else:
                    self.l_stop_time += self.schedule_period

                # L-Stop 지연 시간이 끝 났는지 확인
                if self.setting.l_stop:
                    # L-Stop 이 완료 되였 는지 확인
                    work5 = executor.submit(self.checkStopComplete)
                    works.append(work5)
                # S-Break 이 존재 하는지 확인
                if self.setting.s_brake:
                    # S-Break 이 완료 되었 는지 확인
                    work6 = executor.submit(self.checkBrakeComplete)
                    works.append(work6)

                # B1, S1의 주문이 존재 하지 않을 경우
                if self.is_service_start:
                    work7 = executor.submit(self.setFirstOrder)
                    works.append(work7)

                # 자동 청산 처리
                if self.c_time < self.auto_ctime:
                    self.c_time += self.schedule_period
                else:
                    work8 = executor.submit(self.autoPositionProcess)
                    works.append(work8)
                    self.c_time = 0

                # 정지된 주문 클래스 삭제
                if len(self.live_instances) > 0:
                    work9 = executor.submit(self.del_run_class)
                    works.append(work9)

                concurrent.futures.wait(works)
                executor.shutdown()
        except Exception as e:
            print(f"HTX tradeScheduler error : {e}")

    # symbol 의 최대, 최소 가격 얻기
    def getSymbolCalcPrice(self):
        self.setting.symbol_price = connect_redis.getCoinCurrentPrice(self.rdb, 'htx', self.symbol, 'float')
        # s-brake 계산을 위한 이전 가격
        if self.sb_price == 0:
            self.sb_price = self.setting.symbol_price
        # l-stop 계산을 위한 최소, 최대 가격
        if self.setting.max_price == 0:
            self.setting.max_price = self.setting.symbol_price
        else:
            if self.setting.max_price < self.setting.symbol_price:
                self.setting.max_price = self.setting.symbol_price
        if self.setting.min_price == 0:
            self.setting.min_price = self.setting.symbol_price
        else:
            if self.setting.min_price > self.setting.symbol_price:
                self.setting.min_price = self.setting.symbol_price

    # S-Break 급등, 급락 체크
    def checkShortBreak(self):
        if self.sb_price == 0:
            return
        """
        pos_status = self.setting.getSymbolPositionStatus()
        if pos_status:
            return
        """
        brake_rate = ((self.setting.symbol_price - self.sb_price) / self.sb_price) * 100
        if abs(brake_rate) >= self.s_brake_rate and self.setting.s_brake is False:
            if self.s_brake_sel == 1:
                self.setting.s_brake = True
                self.closeOpenThread()
                if self.setting.l_stop:
                    connect_db.changeBreakStatus(self.user_num, self.symbol, 'htx', 4)
                else:
                    connect_db.changeBreakStatus(self.user_num, self.symbol, 'htx', 3)
            else:
                datetime = utils.setTimezoneDateTime().strftime("%Y-%m-%d %H:%M:%S")
                print(f"{datetime} ---checkShortBreak --- : {self.symbol}, user={self.user_num}")
                self.restartSymbolOrder(False, 2)
        if self.s_brake_cnt * self.break_check_time >= self.s_brake_base_time:
            self.sb_price = self.setting.symbol_price
            self.s_brake_cnt = 0
        self.s_brake_cnt += 1

    # L-Stop 급등, 급락 체크
    def checkLongStop(self):
        """
        pos_status = self.setting.getSymbolPositionStatus()
        if pos_status:
            return
        """
        stop_rate = ((self.setting.max_price - self.setting.min_price) / self.setting.symbol_price) * 100
        if abs(stop_rate) >= self.l_stop_rate and self.setting.l_stop is False:
            self.setting.l_stop = True
            self.closeOpenThread()
            if self.setting.s_brake:
                connect_db.changeBreakStatus(self.user_num, self.symbol, 'htx', 4)
            else:
                connect_db.changeBreakStatus(self.user_num, self.symbol, 'htx', 2)
        if self.l_stop_cnt * self.break_check_time >= self.l_stop_base_time:
            self.setting.max_price = 0
            self.setting.min_price = 0
            self.l_stop_cnt = 0
        self.l_stop_cnt += 1

    # 전체 주문 강제 취소
    def closeHuobiAllOrders(self):
        is_cancel = False
        if len(utils.stop_htx_info) == 0:
            return

        for stop_info in utils.stop_htx_info:
            time.sleep(1)
            if stop_info[0] == self.user_num and stop_info[1] == 'htx' and stop_info[2] == self.symbol:
                is_cancel = True
                break
        if is_cancel:
            self.is_all_close = True
            self.stop_time = 0
            self.brake_time = 0
            self.setting.is_close = True
            self.is_service_start = False

            i = 0
            for stop_htx in utils.stop_htx_info:
                if stop_htx[2] == self.symbol:
                    del utils.stop_htx_info[i]
                i += 1

            self.onCloseSymbolOrder(True)
            # 주문의 실행 상태 0 (stop 상태)
            connect_db.setCloseOrderStatus(self.symbol, self.user_num, 'htx')
            # 처리 안된 포지션 삭제 하기
            # connect_db.delCancelPosition(self.symbol, self.user_num, 'htx')

            self.is_all_close = False
            self.shutDownSchedule()
            self.del_run()

    def onCloseSymbolOrder(self, is_down):
        cancel_order = htx_cancel_order.CancelOrder(self.api_key, self.secret_key, self.user_num)
        # 체결 안된 주문 취소
        cancel_order.onCancelAllTrade(self.symbol, 'htx')
        # 체결 된 주문 강제 청산
        sell_ids = []
        for i in range(4, -1, -1):
            sell_id = self.setting.getOrderID(i, 'sell')
            if sell_id != '':
                sell_ids.append(sell_id)
        print(f"   {self.symbol}, sell_ids={sell_ids}")
        sell_close_id = cancel_order.onClosePositionOrder(self.user_num, self.symbol, 'sell', sell_ids)
        if str(sell_close_id) != '':
            for i in range(0, len(sell_ids)):
                idx = self.setting.getIDX('sell', sell_ids[i])
                order_price = self.setting.getOrderPrice(idx, 'sell')
                order_money = self.setting.getOrderMoney(idx, 'sell')
                profit = utils.getRoundDotDigit((order_price - self.setting.symbol_price) / order_price * order_money,
                                                self.dot_digit)
                make_money = order_money + profit
                self.swap_order.saveClosedOrderInfo(self.symbol, sell_ids[i], sell_close_id, self.setting.symbol_price,
                                                    make_money, profit)
                self.setting.setStOrderStatus(idx, 'complete', 'sell')
                time.sleep(1)
        buy_ids = []
        for i in range(4, -1, -1):
            buy_id = self.setting.getOrderID(i, 'buy')
            if buy_id != '':
                buy_ids.append(buy_id)
        print(f"   {self.symbol}, buy_ids={buy_ids}")
        buy_close_id = cancel_order.onClosePositionOrder(self.user_num, self.symbol, 'buy', buy_ids)
        if str(buy_close_id) != '':
            for i in range(0, len(buy_ids)):
                idx = self.setting.getIDX('buy', buy_ids[i])
                order_price = self.setting.getOrderPrice(idx, 'buy')
                order_money = self.setting.getOrderMoney(idx, 'buy')
                profit = utils.getRoundDotDigit((self.setting.symbol_price - order_price) / order_price * order_money,
                                                self.dot_digit)
                make_money = order_money + profit
                self.swap_order.saveClosedOrderInfo(self.symbol, buy_ids[i], buy_close_id, self.setting.symbol_price,
                                                    make_money, profit)
                self.setting.setStOrderStatus(idx, 'complete', 'buy')
                time.sleep(1)

        if is_down:
            connect_db.setOrderClose(self.user_num, self.coin_num, 'htx', 0)
        else:
            connect_db.setOrderClose(self.user_num, self.coin_num, 'htx', 1)
        self.setting.initParams()

    # ['m19'](1시간) 시간 동안 체결이 일어 나지 않을 경우 주문 취소, 새 주문 넣기
    def resetOrder(self):
        # brake 된 상태
        if self.setting.s_brake or self.setting.l_stop or self.setting.holding_status:
            return
        self.reset_time = 0
        # 이미 포지션 된 주문 강제 청산
        datetime = utils.setTimezoneDateTime().strftime("%Y-%m-%d %H:%M:%S")
        print(f"{datetime} ---if b1 < s1 , restart symbol order--- : {self.symbol}, user={self.user_num}")
        self.restartSymbolOrder(False, 0)

    # L-Stop 완료 되었 는지 확인
    def checkStopComplete(self):
        self.stop_time += self.schedule_period
        if self.l_stop_delay_time <= self.stop_time:
            self.stop_time = 0
            self.setting.l_stop = False

            if self.setting.s_brake:
                connect_db.releaseBreakStatus(self.user_num, self.symbol, 'htx', 3)
                return
            else:
                l_stop_status = self.checkLongStopStatus()
                if l_stop_status:
                    connect_db.releaseBreakStatus(self.user_num, self.symbol, 'htx', 1)
                    return
        time.sleep(self.schedule_period)

    def checkLongStopStatus(self):
        stop_rate = ((self.setting.max_price - self.setting.min_price) / self.setting.symbol_price) * 100
        if stop_rate < self.l_stop_rate:
            return True
        return False

    # S-Break 완료 되었 는지 확인
    def checkBrakeComplete(self):
        self.brake_time += self.schedule_period
        if self.s_brake_delay_time <= self.brake_time:
            self.setting.s_brake = False
            self.brake_time = 0
            if self.setting.l_stop:
                connect_db.releaseBreakStatus(self.user_num, self.symbol, 'htx', 2)
                return
            else:
                connect_db.releaseBreakStatus(self.user_num, self.symbol, 'htx', 1)
                return
        time.sleep(self.schedule_period)

    def run_thread(self, idx, direction, current_price=0):
        status = self.setting.getOrderStatus(idx, direction)
        if status > 0:
            return
        try:
            self.swap_order = htx_swap_order.TradeSwapOrder(self.api_key, self.secret_key, self.symbol,
                                                            self.user_num, self.coin_num, self.dot_digit,
                                                            self.min_digit)
            balance = getHuobiFutureBalance(self.api_key, self.secret_key)
            if balance is None:
                return
            if balance > 0:
                connect_db.setUsersAmount(self.user_num, 'htx', utils.getRoundDotDigit(float(balance), 2))

            if idx == 0:
                one_thread = threading.Thread(target=self.start_thread, args=(idx, direction, balance, current_price))
                one_thread.start()
            else:
                tow_thread = threading.Thread(target=self.start_thread, args=(idx, direction, balance, current_price))
                tow_thread.daemon = True
                tow_thread.start()
        except Exception as e:
            print(f"HTX run_thread error : {e}")
            return

    # create trading order
    def start_thread(self, idx, direction, balance, current_price):
        is_next = True
        if current_price == 0:
            if self.setting.symbol_price == 0:
                self.setting.symbol_price = connect_redis.getCoinCurrentPrice(self.rdb, 'htx', self.symbol, 'float')
            current_price = self.setting.symbol_price
            is_next = False
        amount = self.bet_limit * self.orderCounts[idx]
        price = 0
        if direction == "sell":
            if is_next is False:
                price = current_price - current_price * (self.rate_liq / 100) * self.strengths[idx]
            else:
                price = current_price
        elif direction == "buy":
            if is_next is False:
                price = current_price + current_price * (self.rate_liq / 100) * self.strengths[idx]
            else:
                price = current_price
        if price > 0:
            price = utils.getRoundDotDigit(price, self.dot_digit)

            self.live_run = htx_trading_run.RunTrading(self.api_key, self.secret_key, self.symbol, idx, direction,
                                                       self.param, self.w_param, self.rdb, price, self.swap_order,
                                                       self.setting, self, self.user_num, self.auto_ctime, balance)
            self.live_instances.append(self.live_run)
            self.c_time = 0
            self.is_service_start = True
            self.live_run.checkOrderExecution(amount)

    def setFirstOrder(self):
        if self.setting.l_stop or self.setting.s_brake or self.setting.holding_status:
            return
        buy_idx = self.setting.checkNextIndex(0, 'buy')
        if buy_idx == 0:
            self.run_thread(0, 'buy')
        sell_idx = self.setting.checkNextIndex(0, 'sell')
        if sell_idx == 0:
            self.run_thread(0, 'sell')

    # B1, S1 주문가 비교
    # B1의 주문가 가 S1의 주문가 보다 작으면 True
    def getB1S1PriceCompare(self):
        b1_price = self.setting.getOrderPrice(0, 'buy')
        s1_price = self.setting.getOrderPrice(0, 'sell')

        b1_status = self.setting.getOrderStatus(0, 'buy')
        b2_status = self.setting.getOrderStatus(1, 'buy')
        b3_status = self.setting.getOrderStatus(2, 'buy')
        b4_status = self.setting.getOrderStatus(3, 'buy')
        s1_status = self.setting.getOrderStatus(0, 'sell')
        s2_status = self.setting.getOrderStatus(1, 'sell')
        s3_status = self.setting.getOrderStatus(2, 'sell')
        s4_status = self.setting.getOrderStatus(3, 'sell')

        if b2_status == 6 or b3_status == 6 or b4_status == 6:
            return False
        if s2_status == 6 or s3_status == 6 or s4_status == 6:
            return False
        if b1_status == 6 and s1_status == 6:
            if b1_price > 0 and s1_price > 0:
                if b1_price < s1_price:
                    return True
        return False

    # 자동 포지션 처리
    def autoPositionProcess(self):
        b1_price = self.setting.getOrderPrice(0, 'buy')
        b1_comp = b1_price + b1_price * (self.rate_rev / 100)
        s1_price = self.setting.getOrderPrice(0, 'sell')
        s1_comp = s1_price - s1_price * (self.rate_rev / 100)

        b_force = False
        if b1_price > 0:
            if b1_comp <= self.setting.symbol_price:
                b_force = True
        if s1_price > 0:
            if s1_comp >= self.setting.symbol_price:
                b_force = True

        if b_force:
            datetime = utils.setTimezoneDateTime().strftime("%Y-%m-%d %H:%M:%S")
            print(f"Auto Position Process : --{datetime}-- {self.symbol},  user={self.user_num}")
            self.restartSymbolOrder(False, 1)

    def closeOpenThread(self):
        for i in range(0, 4):
            buy_status = self.setting.getOrderStatus(i, 'buy')
            if buy_status < 6:
                self.setting.setStOrderStatus(i, 'complete', 'buy')
            sell_status = self.setting.getOrderStatus(i, 'sell')
            if sell_status < 6:
                self.setting.setStOrderStatus(i, 'complete', 'sell')

    def restartSymbolOrder(self, b_close, sleep_idx):
        self.onCloseSymbolOrder(b_close)

        self.sb_price = self.setting.symbol_price
        self.s_brake_cnt = 0
        self.s_brake_time = 0
        self.l_stop_time = 0
        self.l_stop_cnt = 0

        if sleep_idx == 0:
            time.sleep(self.order_one_reset_time)
        elif sleep_idx == 1:
            time.sleep(self.order_two_reset_time)
        elif sleep_idx == 2:
            time.sleep(self.s_brake_restart_time)
        # sell, buy 방향의 모든 주문이 청산 완료 이면 새 주문 넣기
        sell_idx = self.setting.checkNextIndex(0, 'sell')
        if sell_idx == 0:
            self.run_thread(0, 'sell')
        buy_idx = self.setting.checkNextIndex(0, 'buy')
        if buy_idx == 0:
            self.run_thread(0, 'buy')
