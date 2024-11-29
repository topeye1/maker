import concurrent.futures
import threading
import time

from apscheduler.schedulers.background import BackgroundScheduler
import utils
from config import connect_redis, connect_db
from huobi_market import htx_swap_order, htx_trading_run, htx_setting, htx_cancel_order, htx_unsave_order
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

        self.w_param = w_param  # maker parameter
        # 체결이 일어나지 않을 경우 주문 취소 시간(1시간)['m19']
        self.order_restart_time = int(w_param['m19']) * 60 * 60
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
        self.is_position_status = 0
        self.stop_time = 0
        self.brake_time = 0
        self.order_number = 0
        self.l_stop = False
        self.s_break = False
        self.s_one_break = False
        self.stop_check_time = 0
        self.is_one = False

    def del_run(self):
        for instance in self.live_instances:
            self.live_instances.remove(instance)
            instance.shutDownCheckSchedule()
            instance.del_run()
            del instance

    def onTradingScheduler(self):
        self.trade_scheduler = BackgroundScheduler()
        self.trade_scheduler.add_job(self.tradeScheduler, 'interval', seconds=self.schedule_period, max_instances=50, misfire_grace_time=10, coalesce=True)
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

                # 체결 된 주문이 존재 하는지 체크
                if self.is_position_status != self.setting.position_num:
                    self.is_position_status = self.setting.position_num
                    self.reset_time = 0
                if self.is_all_close is False:
                    if self.order_restart_time > 0:
                        if self.reset_time >= self.order_restart_time:
                            work2 = executor.submit(self.resetOrder)
                            works.append(work2)
                        self.reset_time += self.schedule_period

                # S-Break 급등, 급락 주문 확인
                if self.s_brake_time >= self.break_check_time:
                    work3 = executor.submit(self.checkShortBreak)
                    works.append(work3)
                    self.s_brake_time = 0
                else:
                    self.s_brake_time += self.schedule_period

                # L-Stop 급등, 급락 주문 확인
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
                if self.is_one is False:
                    work7 = executor.submit(self.restartFirstOrder)
                    works.append(work7)

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
        pos_status = self.setting.getSymbolPositionStatus()
        if pos_status:
            return

        brake_rate = ((self.setting.symbol_price - self.sb_price) / self.sb_price) * 100
        if abs(brake_rate) > self.s_brake_rate and self.setting.s_brake is False:
            self.setting.s_brake = True
            if self.setting.l_stop:
                connect_db.changeBreakStatus(self.user_num, self.symbol, 'htx', 4)
            else:
                connect_db.changeBreakStatus(self.user_num, self.symbol, 'htx', 3)
        if self.s_brake_cnt * self.break_check_time >= self.s_brake_base_time:
            self.sb_price = self.setting.symbol_price
            self.s_brake_cnt = 0
        self.s_brake_cnt += 1

    # L-Stop 급등, 급락 체크
    def checkLongStop(self):
        pos_status = self.setting.getSymbolPositionStatus()
        if pos_status:
            return

        stop_rate = ((self.setting.max_price - self.setting.min_price) / self.setting.symbol_price) * 100
        if stop_rate >= self.l_stop_rate and self.setting.l_stop is False:
            self.setting.l_stop = True
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
            self.order_number = 0
            self.stop_time = 0
            self.brake_time = 0
            self.setting.is_close = True
            self.setting.max_price = 0
            self.setting.min_price = 0
            if self.setting.holding_status:
                connect_db.setOrderClose(self.user_num, self.coin_num, 'htx')
                self.setting.holding_status = False

            self.onCloseSymbolOrder()
            # 주문의 실행 상태 0 (stop 상태)
            connect_db.setCloseOrderStatus(self.symbol, self.user_num, 'htx')

            i = 0
            for stop_htx in utils.stop_htx_info:
                if stop_htx[2] == self.symbol:
                    del utils.stop_htx_info[i]
                i += 1
            """
            # 청산 후 보관 되지 않은 주문 보관 하기
            unclear_ids = connect_db.getUnSaveTradeIds(self.user_num, 'htx')
            if len(unclear_ids) > 0:
                htx_unsave_order.unSavePositionOrders(self.api_key, self.secret_key, self.user_num, unclear_ids)
            """
            self.is_all_close = False
            self.shutDownSchedule()
            self.del_run()

    def onCloseSymbolOrder(self):
        cancel_order = htx_cancel_order.CancelOrder(self.api_key, self.secret_key, self.user_num)
        # 체결 안된 주문 취소
        cancel_order.onCancelAllTrade(self.symbol, 'htx')
        # 체결 된 주문 강제 청산
        sell_ids = []
        for i in range(3, -1, -1):
            sell_id = self.setting.getPositionOrderID(i, 'sell')
            if sell_id != '':
                sell_ids.append(sell_id)
            else:
                self.setting.setStOrderStatus(i, 'complete', 'sell')
        sell_close_id = cancel_order.onClosePositionOrder(self.user_num, self.symbol, 'sell', sell_ids)
        if sell_close_id != '':
            s_closed = False
            for sell_id in sell_ids:
                time.sleep(1)
                res = cancel_order.closeAllOrderHistory(self.user_num, self.symbol, sell_id, sell_close_id, s_closed)
                if res == 1:
                    s_closed = True
        buy_ids = []
        for i in range(3, -1, -1):
            buy_id = self.setting.getPositionOrderID(i, 'buy')
            if buy_id != '':
                buy_ids.append(buy_id)
            else:
                self.setting.setStOrderStatus(i, 'complete', 'buy')
        buy_close_id = cancel_order.onClosePositionOrder(self.user_num, self.symbol, 'buy', buy_ids)
        if buy_close_id != '':
            b_closed = False
            for buy_id in buy_ids:
                time.sleep(1)
                res = cancel_order.closeAllOrderHistory(self.user_num, self.symbol, buy_id, buy_close_id, b_closed)
                if res == 1:
                    b_closed = True
        # 코인별 설정 정보 초기화
        self.setting.initParams()

    # ['m19'](1시간) 시간 동안 체결이 일어 나지 않을 경우 주문 취소, 새 주문 넣기
    def resetOrder(self):
        # brake 된 상태
        if self.setting.s_brake or self.setting.l_stop:
            return
        self.reset_time = 0
        self.is_position_status = 0
        # 이미 포지션 된 주문 강제 청산
        self.onCloseSymbolOrder()
        # ['m7']분 지연
        time.sleep(int(self.w_param['m7']))
        # 새 주문 넣기
        self.onFirstOrder()

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
                    self.onFirstOrder()
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
                self.onFirstOrder()
                return
        time.sleep(self.schedule_period)

    def onFirstOrder(self):
        if self.setting.l_stop or self.setting.s_brake or self.setting.holding_status:
            return
        # sell, buy 방향의 모든 주문이 청산 완료 이면 새 주문 넣기
        sell_idx = self.setting.checkNextIndex(0, 'sell')
        if sell_idx == 0:
            self.run_thread(0, 'sell')
        buy_idx = self.setting.checkNextIndex(0, 'buy')
        if buy_idx == 0:
            self.run_thread(0, 'buy')

    def run_thread(self, idx, direction, current_price=0, pre_price=0):
        try:
            self.swap_order = htx_swap_order.TradeSwapOrder(self.api_key, self.secret_key, self.symbol,
                                                            self.user_num, self.coin_num, self.dot_digit,
                                                            self.min_digit)
            balance = getHuobiFutureBalance(self.api_key, self.secret_key)
            if balance is None:
                return
            if balance > 0:
                connect_db.setUsersAmount(self.user_num, 'htx', utils.getRoundDotDigit(float(balance), 2))
            if current_price == 0 or pre_price == 0:
                current_price = connect_redis.getCoinCurrentPrice(self.rdb, 'htx', self.symbol, 'float')
                if current_price == 0:
                    return
                # 이전 가격이 없는 경우 평균 가격 얻기
                pre_price = connect_redis.getCoinMiddlePrice(self.rdb, 'htx', self.symbol)
                if pre_price == 0:
                    pre_price = current_price
            if idx == 0:
                one_thread = threading.Thread(target=self.onCreateIsolatedTPSL, args=(idx, direction, balance, current_price, pre_price))
                one_thread.start()
            else:
                tow_thread = threading.Thread(target=self.onCreateIsolatedTPSL, args=(idx, direction, balance, current_price, pre_price))
                tow_thread.daemon = True
                tow_thread.start()
        except Exception as e:
            print(f"HTX run_thread error : {e}")
            return

    def getMinMaxPro(self, c_price):
        max_price, min_price = connect_redis.getMaxMinPrice(self.rdb, 'htx', self.symbol)
        pro = utils.getCurrentMinMaxProValue(max_price, min_price, c_price)
        return pro

    # create trading order
    def onCreateIsolatedTPSL(self, idx, direction, balance, current_price, pre_price):
        if current_price == 0 or pre_price == 0:
            return
        if self.order_number == 0:
            self.order_number = 1
        amount = self.bet_limit * self.orderCounts[idx]
        price = 0
        tp_price = 0
        sl_price = 0
        min_max_pro = self.getMinMaxPro(current_price)
        if direction == "sell":
            base_price = (current_price + pre_price) / 2
            price = current_price + base_price * ((self.rate_rev + min_max_pro) / 100) * self.strengths[idx]
            tp_price = price - price * (self.rate_rev / 100) * (1 + self.strengths[idx]) / 2
            sl_price = price + price * (self.rate_liq / 100)
        elif direction == "buy":
            base_price = (current_price + pre_price) / 2
            price = current_price - base_price * ((self.rate_rev + min_max_pro) / 100) * self.strengths[idx]
            tp_price = price + price * (self.rate_rev / 100) * (1 + self.strengths[idx]) / 2
            sl_price = price - price * (self.rate_liq / 100)

        _c_price = utils.getRoundDotDigit(price, self.dot_digit)  # 새 주문 가격
        _p_price = utils.getRoundDotDigit(pre_price, self.dot_digit)  # 이전 주문 가격

        if _c_price == _p_price:
            # 이전 가격과 같은 가격 이면 다시 계산
            time.sleep(10)
            r_price = connect_redis.getCoinCurrentPrice(self.rdb, 'htx', self.symbol, 'float')
            self.onCreateIsolatedTPSL(idx, direction, balance, r_price, pre_price)
        else:
            state, order_id, tp, sl = self.swap_order.onTradingSwapOrder(direction, idx, balance, amount, current_price, self.leverage, self.bet_limit,
                                                                         price, tp_price, sl_price, self.rate_rev, self.rate_liq, self.brokerID)
            if state:
                self.live_run = htx_trading_run.RunTrading(self.api_key, self.secret_key, self.symbol, idx, direction,
                                                           self.param, self.w_param, self.rdb, price, order_id,
                                                           self.setting, self, self.user_num)
                self.live_run.checkOrderExecution(tp, sl, amount)
                self.live_instances.append(self.live_run)
            else:
                self.run_thread(idx, direction)

    # S4가 주문 체결 된 상태 에서 B1이 존재 하지 않을 경우
    # B4가 주문 체결 된 상태 에서 S1존재 하지 않을 경우
    def restartFirstOrder(self):
        if self.setting.l_stop or self.setting.s_brake:
            return
        status_buy_0 = self.setting.getOrderStatus(0, 'buy')
        status_sell_2 = self.setting.getOrderStatus(2, 'sell')
        status_sell_3 = self.setting.getOrderStatus(3, 'sell')
        if status_buy_0 == 0:
            if (status_sell_2 == 4 or status_sell_2 == 6) and status_sell_3 <= 3:
                self.is_one = True
                time.sleep(300)
                buy_idx = self.setting.checkNextIndex(0, 'buy')
                if buy_idx == 0:
                    self.run_thread(0, 'buy')
                    self.is_one = False
        status_sell_0 = self.setting.getOrderStatus(0, 'sell')
        status_buy_2 = self.setting.getOrderStatus(2, 'buy')
        status_buy_3 = self.setting.getOrderStatus(3, 'buy')
        if status_sell_0 == 0:
            if (status_buy_2 == 4 or status_buy_2 == 6) and status_buy_3 <= 3:
                self.is_one = True
                time.sleep(300)
                sell_idx = self.setting.checkNextIndex(0, 'sell')
                if sell_idx == 0:
                    self.run_thread(0, 'sell')
                    self.is_one = False
        if self.is_one:
            self.is_one = False
