import concurrent.futures
import time

from apscheduler.schedulers.background import BackgroundScheduler

from config import connect_redis, connect_db
from binance_market import bin_cancel_order, bin_order_info


class RunTrading:
    def __init__(self, api_key, secret_key, symbol, idx, direction, param, w_param, rdb, price, order_id, setting,
                 tradingCls, user_num):
        self.idx = idx
        self.direction = direction
        self.api_key = api_key
        self.secret_key = secret_key
        self.orderCls = None
        self.symbol = symbol
        self.order_id = order_id
        self.order_info = None
        self.w_param = w_param
        self.brake_base_time = int(w_param['w5']) * 60
        self.brake_rate = float(w_param['w6'])
        self.brake_check_time = int(w_param['w7'])
        self.brake_delay_time = int(w_param['w8']) * 60
        # s1, b1 선주문 취소 시간(100분)
        self.first_cancel_time = int(w_param['m5']) * 60
        # s2~s4, b2~b4 주문 취소 시간(1시간)
        self.next_cancel_time = int(w_param['m19']) * 60 * 60
        self.order_next_time = int(w_param['m8'])
        self.order_one_reset_time = int(w_param['m7'])
        self.order_two_reset_time = int(w_param['m10'])
        self.order_add_delay_time = int(w_param['m9'])
        self.strengths = [float(w_param['m1']), float(w_param['m2']), float(w_param['m3']), float(w_param['m4'])]
        self.param = param
        self.rate_rev = float(param['rate_rev'])
        self.rate_liq = float(param['rate_liq'])
        self.rdb = rdb
        self.c_price = price
        self.r_price = 0
        self.tradingCls = tradingCls
        self.setting = setting
        self.arr_prices = []
        self.avr_price = 0
        self.user_num = user_num
        # scheduler
        self.check_scheduler = None

        self.is_sell = 0
        self.is_buy = 0
        self.b_price = 0
        self.order_status = 0
        self.brake_time = 0
        self.brake_cnt = 0
        self.is_next = False

        self.scheduler_time = 3
        self.brakeOrderCnt = 0
        self.checkOrderCnt = 0
        self.run_scheduler = False
        self.cancel_time = 0
        self.close_time = 0
        self.next_complete = False

    def __del__(self):
        print(f"BIN - delete run : {self.symbol}-{self.direction} {self.idx}")

    def run_reorder(self, idx, direction):
        re_idx = self.setting.checkBinanceNextIndex(idx, self.direction)
        if re_idx > -1:
            self.tradingCls.run_binance_thread(re_idx, direction, self.r_price, self.c_price)

    def del_run(self):
        del self

    def start_order_scheduler(self):
        self.run_scheduler = True
        self.check_scheduler = BackgroundScheduler()
        self.check_scheduler.add_job(self.onBinanceOrderScheduler, 'interval', seconds=3, max_instances=50, misfire_grace_time=10, coalesce=True)
        self.check_scheduler.start()

    def onBinanceOrderScheduler(self):
        try:
            if self.run_scheduler is False:
                return
            with concurrent.futures.ThreadPoolExecutor() as executor:
                works = []
                self.run_scheduler = False
                # 현재 주문이 실행 상태가 아니면 삭제
                if self.setting.getBinanceRunStatus(self.idx, self.direction) == 0:
                    self.shutDownCheckSchedule()
                    #self.del_run()
                    return
                # 3초 간격으로 현재가 확인
                work0 = executor.submit(self.checkPrice)
                works.append(work0)
                # 급등, 급락 주문 확인
                if self.brakeOrderCnt >= self.brake_check_time / self.scheduler_time:
                    work1 = executor.submit(self.checkBrake)
                    works.append(work1)
                    self.brakeOrderCnt = 0
                else:
                    self.brakeOrderCnt += 1

                if self.setting.is_brake is False:
                    # 30초 간격 으로 주문 체결 및 청산 상태 확인
                    if self.checkOrderCnt >= 10:
                        work2 = executor.submit(self.checkTradeOrder)
                        works.append(work2)
                        self.checkOrderCnt = 0
                    else:
                        self.checkOrderCnt += 1

                    # [m5]100분후, [m19]1시간후 체결 되지 않은 주문 취소
                    if self.order_status == 0:
                        if self.idx == 0:
                            if self.cancel_time >= self.first_cancel_time:
                                work3 = executor.submit(self.cancelBinanceOrder)
                                works.append(work3)
                                self.cancel_time = 0
                        else:
                            if self.cancel_time >= self.next_cancel_time:
                                work3 = executor.submit(self.cancelBinanceOrder)
                                works.append(work3)
                                self.cancel_time = 0
                        self.cancel_time += 3
                    else:
                        self.cancel_time = 0

                concurrent.futures.wait(works)
                executor.shutdown()
                self.run_scheduler = True
        except Exception as e:
            print(f"onBinanceOrderScheduler error : {e}")

    def getOrderStrength(self):
        idx = self.idx + 1
        if idx > 3:
            return 0
        return self.strengths[idx]

    # 3초 간격으로 현재가 확인, [m9] 시간 동안 이동 평균 계산
    def checkPrice(self):
        if self.setting.is_brake:
            self.brake_time += 3
            if self.brake_delay_time <= self.brake_time:
                self.brake_time = 0
                self.setting.is_brake = False
                self.b_price = self.r_price
                order_id = self.setting.getBinanceOrderID(self.idx, self.direction)
                self.changeTradeBreakStatus(self.symbol, 1)
            else:
                return

        r_price = connect_redis.getCoinCurrentPrice(self.rdb, 'bin', self.symbol, 'float')
        if r_price is None or r_price == 0:
            self.is_sell = 0
            self.is_buy = 0
            return
        self.r_price = r_price
        # brake 계산을 위한 이전 가격
        if self.b_price == 0:
            self.b_price = r_price

        if self.direction == 'sell':
            com_price = self.c_price + (self.c_price * self.rate_rev / 100 * self.getOrderStrength())
            if self.r_price > com_price:
                self.is_sell = 1
            else:
                self.is_sell = 0
        if self.direction == 'buy':
            com_price = self.c_price - (self.c_price * self.rate_rev / 100 * self.getOrderStrength())
            if self.r_price < com_price:
                self.is_buy = 1
            else:
                self.is_buy = 0

    # 급등, 급락 체크
    def checkBrake(self):
        if self.b_price == 0:
            return
        brake_rate = abs((self.r_price - self.b_price) / self.b_price) * 100
        if brake_rate > self.brake_rate and self.setting.is_brake is False:
            order_id = self.setting.getBinanceOrderID(self.idx, self.direction)
            if order_id != '':
                self.arr_prices.clear()
                self.changeTradeBreakStatus(self.symbol, 2)
                self.setting.is_brake = True
        if self.brake_cnt * self.brake_check_time >= self.brake_base_time:
            self.b_price = self.r_price
            self.brake_cnt = 0
        self.brake_cnt += 1

    def changeTradeBreakStatus(self, symbol, status):
        connect_db.changeBreakStatus(self.user_num, symbol, 'bin', status)

    def checkOrderExecution(self, orderCls, volume):
        self.orderCls = orderCls
        self.setting.setBinanceOrderStatus(self.idx, 'create', self.direction, self.c_price, volume, self.order_id)
        self.order_info = bin_order_info.BinanceOrderInfo(self.api_key, self.secret_key, self.symbol, self.idx)
        self.checkTradeOrder()
        self.start_order_scheduler()

    def getTpSlPrice(self, direction, price, pre_ids):
        tp_price = 0
        sl_price = 0
        if direction == "sell":
            tp_price = float(price) - float(price) * (self.rate_rev / 100)
            sl_price = float(price) + float(price) * (self.rate_liq / 100)
        elif direction == "buy":
            tp_price = float(price) + float(price) * (self.rate_rev / 100)
            sl_price = float(price) - float(price) * (self.rate_liq / 100)
        if tp_price > 0 and sl_price > 0:
            tp_id, sl_id = self.orderCls.binanceOpenTpSlOrder(self.direction, self.order_id, tp_price, sl_price, pre_ids)
            return tp_id, sl_id
        return '', ''

    # 30초 간격으로 해당 주문 체결이 완료 되였는지 체크하기
    def checkTradeOrder(self):
        # 주문이 체결 완료 되였 는지 체크
        self.order_status = self.order_info.check_order_execution(self.order_id)
        if self.order_status == 1:
            self.cancel_time = 0
            trigger_status = self.setting.getOrderTrigger(self.idx, self.direction)
            pre_ids = []
            if trigger_status == 0:
                self.setting.changeBinanceOrderStatus(self.idx, self.direction)
                orig_price = self.setting.getBinanceOrderPrice(self.idx, self.direction)
                if orig_price == 0:
                    return
                order_price = orig_price

                if self.idx > 0:
                    # s2,b2 ~ s4, b4 가 체결 완료 되면 이전 tp/sl 주문을 삭제
                    pre_idx = self.idx - 1
                    pre_ids = self.setting.getIDs(self.idx, self.direction)
                    pre_TpID, pre_SlID = self.setting.getTpSlID(pre_idx, self.direction)
                    cancel_order = bin_cancel_order.CancelOrder(self.api_key, self.secret_key, self.user_num)
                    cancel_order.onCancelOrder(pre_TpID, self.symbol)
                    cancel_order.onCancelOrder(pre_SlID, self.symbol)
                    aver_price = self.setting.getAverageOrderPrice(self.idx, self.direction)
                    if aver_price > 0:
                        order_price = aver_price
                    self.next_complete = True

                # 새로운 tp/sl 주문 생성
                tp_id, sl_id = self.getTpSlPrice(self.direction, order_price, pre_ids)
                if tp_id == '' or sl_id == '':
                    tp_id, sl_id = self.getTpSlPrice(self.direction, orig_price, pre_ids)
                    if tp_id == '' or sl_id == '':
                        tp_id, sl_id = self.getTpSlPrice(self.direction, self.r_price, pre_ids)
                self.setting.setOrderTrigger(self.idx, self.direction, 1)
                self.setting.setTpSlID(self.idx, self.direction, tp_id, sl_id)

            tpID, slID = self.setting.getTpSlID(self.idx, self.direction)
            if tpID != '' and slID != '':
                # 주문이 청산 완료 되였 는지 체크
                order_comp, close_id = self.order_info.check_position_liquidation(tpID, slID)
                if order_comp == 1:
                    self.close_time = 0
                    self.setting.setBinanceOrderStatus(self.idx, 'complete', self.direction)

                    cancel_order = bin_cancel_order.CancelOrder(self.api_key, self.secret_key, self.user_num)
                    if close_id == str(slID):
                        cancel_order.onCancelOrder(tpID, self.symbol)
                    if close_id == str(tpID):
                        cancel_order.onCancelOrder(slID, self.symbol)

                    self.setting.initBinanceParams(self.direction)
                    # 청산 완료된 스케쥴 끝내기
                    self.shutDownCheckSchedule()
                    #self.del_run()
                    # 재 주문 넣기
                    self.setReOrder()
            # 다음 주문 넣기
            if self.is_next is False:
                self.setNextOrder()

    # 재주문 넣기
    def setReOrder(self):
        re_idx = self.setting.checkBinanceNextIndex(self.idx, self.direction)
        if re_idx > 0:
            self.sleep_time(re_idx)
            self.run_reorder(re_idx, self.direction)

    # 다음 주문 넣기
    def setNextOrder(self):
        if self.idx < 3:
            number = self.idx + 1
        else:
            number = 0
        next_idx = -1
        if self.is_sell == 1:
            next_idx = self.setting.checkBinanceNextIndex(number, self.direction)
        elif self.is_buy == 1:
            next_idx = self.setting.checkBinanceNextIndex(number, self.direction)

        if next_idx > -1:
            self.is_next = True
            self.sleep_time(next_idx)
            self.run_reorder(next_idx, self.direction)

    def sleep_time(self, idx):
        if self.idx == idx:
            if idx == 0:
                # param [m7] s1, b1 재주문 지연 시간
                sleep_time = self.order_one_reset_time
            else:
                # param [m10] s2~s4, b2~b4 재주문 지연 시간
                sleep_time = self.order_two_reset_time
        else:
            # param [m8] 다음 주문 지연 시간
            sleep_time = self.order_next_time
        time.sleep(sleep_time)

    def shutDownCheckSchedule(self):
        try:
            if self.check_scheduler.running:
                self.run_scheduler = False
                self.check_scheduler.shutdown(wait=False)
                print(f"Binance {self.symbol}-{self.direction}-{self.idx} Scheduler shut down successfully")
            else:
                print(f"Binance {self.symbol}-{self.direction}-{self.idx} Scheduler is not running")
        except Exception as e:
            print(f"Binance shutDownCheckSchedule has already been shutdown. {e}")

    # 120분내에 주문이 체결되지 않으면 취소, 코인이 실행 중지 이면 취소
    def cancelBinanceOrder(self):
        pos_status = self.setting.getOrderTrigger(self.idx, self.direction)
        if pos_status == 1:
            return
        cancel_order = bin_cancel_order.CancelOrder(self.api_key, self.secret_key, self.user_num)
        if cancel_order.onCancelOrder(self.order_id, self.symbol):
            self.setting.setBinanceOrderStatus(self.idx, 'complete', self.direction)
            self.setting.cancelBinanceOrderStatus(self.idx, self.direction)
            idx = self.setting.checkBinanceNextIndex(self.idx, self.direction)
            if idx > -1:
                self.sleep_time(idx)
                self.run_reorder(idx, self.direction)
            self.shutDownCheckSchedule()
            #self.del_run()

    def cancelOpenOrder(self, cancel_idx):
        pos_status = self.setting.getOrderTrigger(cancel_idx, self.direction)
        if pos_status == 1:
            return 1
        cancel_order_id = self.setting.getBinanceOrderID(cancel_idx, self.direction)
        cancel_order = bin_cancel_order.CancelOrder(self.api_key, self.secret_key, self.user_num)
        if cancel_order.onCancelOrder(cancel_order_id, self.symbol):
            self.setting.setBinanceOrderStatus(cancel_idx, 'complete', self.direction)
            self.setting.cancelBinanceOrderStatus(cancel_idx, self.direction)
            self.shutDownCheckSchedule()
            #self.del_run()
        return 0

    def forceCloseOrder(self):
        cancel_order = bin_cancel_order.CancelOrder(self.api_key, self.secret_key, self.user_num)
        close_id = cancel_order.onForceClosePosition(self.symbol, 'bin', self.direction)
        if close_id != '':
            cancel_order.saveClosePosition(self.symbol, close_id)
            for i in range(0, self.idx + 1):
                self.setting.setBinanceOrderStatus(i, 'complete', self.direction)
