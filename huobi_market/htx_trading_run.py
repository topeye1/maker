import concurrent.futures
import time
from apscheduler.schedulers.blocking import BlockingScheduler

import utils
from config import connect_redis
from huobi_market import htx_cancel_order, htx_order_info, htx_order_history, htx_hoding_run


class RunTrading:
    def __init__(self, api_key, secret_key, symbol, idx, direction, param, w_param, rdb, price, order_id, setting,
                 tradingCls, user_num):
        self.idx = idx
        self.direction = direction
        self.api_key = api_key
        self.secret_key = secret_key
        self.symbol = symbol
        self.order_id = order_id
        self.w_param = w_param

        # 주문 취소 시간(분)
        self.order_cancel_time = int(w_param['m5']) * 60
        # 다음 주문 지연 시간(초)
        self.order_next_time = int(w_param['m8'])
        # param [m7] s1, b1 재주문 지연 시간(초)
        self.order_one_reset_time = int(w_param['m7'])
        # param [m10] s2~s4, b2~b4 재주문 지연 시간(초)
        self.order_two_reset_time = int(w_param['m10'])
        # 조건 만족 후 추가 매도, 매수 주문 시간 delay(초)
        self.order_add_delay_time = int(w_param['m9'])
        # 주문 강도
        self.strengths = [float(w_param['m1']), float(w_param['m2']), float(w_param['m3']), float(w_param['m4'])]
        # 재 주문 범위
        self.reorder_range = int(w_param['m16'])
        self.param = param
        self.rate_rev = float(param['rate_rev'])
        self.rate_liq = float(param['rate_liq'])
        # 홀딩 조건 퍼센트
        self.hold_rate = int(w_param['h1'])

        self.rdb = rdb
        self.order_price = price
        self.tradingCls = tradingCls
        self.setting = setting
        self.arr_prices = []
        self.avr_price = 0
        self.user_num = user_num
        # scheduler
        self.check_scheduler = None
        self.order_info = None
        self.close_history = None

        self.is_sell = 0
        self.is_buy = 0
        self.order_status = 1
        self.is_next = False

        self.scheduler_time = 3

        self.checkOrderCnt = 0
        self.cancelOrderCnt = 0
        self.run_scheduler = False
        self.cancel_time = 0
        self.close_time = 0
        self.next_complete = False
        self.is_position = False
        self.close_order_id = ''
        self.close_status = 0
        self.is_close = False
        self.offset = ''
        self.search_time = 0
        self.is_stop = False

    def __del__(self):
        print(f"HTX - delete run : {self.symbol}-{self.direction} {self.idx}")

    def run_reorder(self, idx, direction):
        if self.setting.is_close or self.setting.s_brake or self.setting.l_stop:
            return
        re_idx = self.setting.checkNextIndex(idx, self.direction)
        if re_idx > -1:
            real_price = connect_redis.getCoinCurrentPrice(self.rdb, 'htx', self.symbol, 'float')
            self.tradingCls.run_thread(re_idx, direction, real_price, self.order_price)
        else:
            return

    def del_run(self):
        del self

    def start_order_scheduler(self):
        self.run_scheduler = True
        self.check_scheduler = BlockingScheduler()
        self.check_scheduler.add_job(self.onOrderScheduler, 'interval', seconds=3, max_instances=100,
                                     misfire_grace_time=10, coalesce=True)
        self.check_scheduler.start()

    def onOrderScheduler(self):
        try:
            if self.run_scheduler is False:
                return
            with concurrent.futures.ThreadPoolExecutor() as executor:
                works = []
                if self.setting.getRunStatus(self.idx, self.direction) == 0:
                    self.shutDownCheckSchedule()
                    self.del_run()
                    return
                # 3초 간격으로 현재가 확인
                work0 = executor.submit(self.checkPrice)
                works.append(work0)

                # 30초 간격 으로 주문 체결 및 청산 상태 확인
                if self.checkOrderCnt >= 30:
                    work1 = executor.submit(self.checkTradeOrder)
                    works.append(work1)
                    self.checkOrderCnt = 0
                else:
                    self.checkOrderCnt += self.scheduler_time

                # [m5]100분후 체결 되지 않은 주문 취소
                if self.order_status < 4 and self.idx == 0:
                    if self.cancel_time >= self.order_cancel_time:
                        work2 = executor.submit(self.cancelHuobiOrder)
                        works.append(work2)
                        self.cancel_time = 0
                    self.cancel_time += 3
                else:
                    self.cancel_time = 0

                # Holding 상태 체크
                if self.setting.holding_status is False:
                    work3 = executor.submit(self.checkHoldingStatus)
                    works.append(work3)

                concurrent.futures.wait(works)
                executor.shutdown()
        except Exception as e:
            print(f"HTX onOrderScheduler error : {e}")

    def getOrderStrength(self):
        idx = self.idx + 1
        if idx > 3:
            return 0
        return self.strengths[idx]

    def getMinMaxPro(self, c_price):
        max_price, min_price = connect_redis.getMaxMinPrice(self.rdb, 'htx', self.symbol)
        pro = utils.getCurrentMinMaxProValue(max_price, min_price, c_price)
        return pro

    # 3초 간격으로 현재가 확인
    def checkPrice(self):
        if self.setting.s_brake or self.setting.l_stop:
            self.cancelBreakOrders()
            self.is_stop = True
        if self.is_stop and self.setting.s_brake is False and self.setting.l_stop is False:
            self.is_next = False
            self.is_stop = False

        if self.setting.symbol_price is None or self.setting.symbol_price == 0:
            self.is_sell = 0
            self.is_buy = 0
            return

        min_max_pro = self.getMinMaxPro(self.setting.symbol_price)
        if self.direction == 'sell':
            com_price = self.order_price + (
                        self.order_price * (self.rate_rev + min_max_pro) / 100 * self.getOrderStrength())
            if self.setting.symbol_price > com_price:
                self.is_sell = 1
            else:
                self.is_sell = 0
        if self.direction == 'buy':
            com_price = self.order_price - (
                        self.order_price * (self.rate_rev + min_max_pro) / 100 * self.getOrderStrength())
            if self.setting.symbol_price < com_price:
                self.is_buy = 1
            else:
                self.is_buy = 0

    def checkOrderExecution(self, tp, sl, amount):
        self.setting.setStOrderStatus(self.idx, 'create', self.direction, self.order_price, tp, sl, amount, self.order_id)
        self.order_info = htx_order_info.HuobiOrderInfo(self.api_key, self.secret_key, self.symbol)
        self.close_history = htx_order_history.HuobiOrderHistory(self.api_key, self.secret_key, self.symbol)
        self.checkTradeOrder()
        self.start_order_scheduler()

    # 30초 간격 으로 해당 주문 체결이 완료 되었 는지 체크 하기
    def checkTradeOrder(self):
        # 주문이 체결 되였 는지, 청산이 완료 되였 는지 체크
        tp, sl = self.setting.getTpSl(self.idx, self.direction)
        status = self.setting.getOrderStatus(self.idx, self.direction)
        if status == 3:
            self.order_status = self.order_info.onCheckOrderInfo(self.order_id, self.user_num)
            self.setting.setOrderStatus(self.idx, self.direction, self.order_status)
            if self.idx > 0:
                pre_idx = self.idx - 1
                # B2~B4, S2~S4 의 경우 이전 주문이 청산 완료 되면 주문 취소
                if self.setting.getRunStatus(pre_idx, self.direction) == 0:
                    self.cancelCurrentOrders()

        if status == 4 or status == 6:
            if self.is_close is False:
                self.setting.setOrderStatus(self.idx, self.direction, status)
                self.setting.setPositionOrderID(self.idx, self.direction)
                # 주문 청산 완료 되었 는지 체크 하기
                side = 'sell'
                if self.direction == 'sell':
                    side = 'buy'
                if self.close_order_id == '':
                    self.search_time = 0
                    self.offset, self.close_order_id = self.close_history.getHuobiOrderHistory(self.order_id,
                                                                                               self.user_num, tp, sl,
                                                                                               side)
                else:
                    if self.close_status == 7:
                        self.offset = self.close_history.getHuobiOrderRiskHistory(self.user_num, self.close_order_id)
                    else:
                        if self.search_time == 0:
                            self.search_time = utils.setTimezoneTimestamp()
                        self.offset, self.close_status = self.close_history.getHuobiOrderIDHistory(self.user_num,
                                                                                                   self.close_order_id,
                                                                                                   self.search_time)

                # 주문이 체결 완료
                if self.idx > 0:
                    self.next_complete = True
                if self.is_position is False:
                    self.is_position = True
                    self.setting.position_num += 1
            # 주문이 청산 완료 되었 을 때
            if self.offset == 'close':
                self.is_close = True
                if status == 4:
                    self.cancelSubOrder()
                self.setting.setStOrderStatus(self.idx, 'complete', self.direction)
                # 청산 완료된 스케쥴 끝내기
                self.shutDownCheckSchedule()
                self.del_run()
                # 재 주문 넣기
                self.setReOrder()
            # 다음 주문 넣기
            if self.is_next is False:
                self.setNextOrder()

    # s1, b1 새 주문 범위 판단
    def checkFirstOrderRange(self):
        if self.idx > 0:
            return True
        if self.direction == 'sell':
            buy4_price = self.setting.getOrderPrice(3, 'buy')
            if buy4_price == 0:
                return True
            limit_price = buy4_price - buy4_price * (self.rate_rev / 100) * self.reorder_range
            if self.setting.symbol_price < limit_price:
                return False
        else:
            sell4_price = self.setting.getOrderPrice(3, 'sell')
            if sell4_price == 0:
                return True
            limit_price = sell4_price + sell4_price * (self.rate_rev / 100) * self.reorder_range
            if self.setting.symbol_price > limit_price:
                return False
        return True

    # 재주문 넣기
    def setReOrder(self):
        check_first_order_status = self.checkFirstOrderRange()
        if check_first_order_status:
            re_idx = self.setting.checkNextIndex(self.idx, self.direction)
            if re_idx >= 0:
                self.sleep_time(re_idx)
                self.run_reorder(re_idx, self.direction)

    # 다음 주문 넣기
    def setNextOrder(self):
        # break 상태 나 holding 상태 이면 주문을 넣지 않는다.
        if self.setting.s_brake or self.setting.l_stop or self.setting.holding_status:
            return
        check_first_order_status = self.checkFirstOrderRange()
        if check_first_order_status:
            if self.idx < 3:
                number = self.idx + 1
            else:
                number = 0
            next_idx = -1
            if self.is_sell == 1:
                next_idx = self.setting.checkNextIndex(number, self.direction)
            elif self.is_buy == 1:
                next_idx = self.setting.checkNextIndex(number, self.direction)
            if next_idx > -1:
                self.sleep_time(next_idx)
                self.run_reorder(next_idx, self.direction)
                self.is_next = True

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
            else:
                self.run_scheduler = False
        except Exception as e:
            self.run_scheduler = False
            print(f"HTX shutDownCheckSchedule() error : {e}")

    # 120분내에 주문이 체결되지 않으면 취소, 코인이 실행 중지 이면 취소
    def cancelHuobiOrder(self):
        cancel_order = htx_cancel_order.CancelOrder(self.api_key, self.secret_key, self.user_num)
        if cancel_order.onCancelOrder(self.order_id, self.symbol):
            self.setting.setStOrderStatus(self.idx, 'complete', self.direction)
            self.setting.setOrderStatus(self.idx, self.direction, 0)
            idx = self.setting.checkNextIndex(self.idx, self.direction)
            if idx > -1:
                self.sleep_time(idx)
                self.run_reorder(idx, self.direction)
            self.shutDownCheckSchedule()
            self.del_run()

    # sub 주문 취소
    def cancelSubOrder(self):
        cancel_order = htx_cancel_order.CancelOrder(self.api_key, self.secret_key, self.user_num)
        if cancel_order.onCancelOrder(self.order_id, self.symbol, True):
            print(f"cancelSubOrder : OK\n")

    # l-stop, s-break 상태 에서 주문 취소
    def cancelBreakOrders(self):
        if self.order_status == 4 or self.order_status == 6:
            return
        cancel_order = htx_cancel_order.CancelOrder(self.api_key, self.secret_key, self.user_num)
        if cancel_order.onCancelOrder(self.order_id, self.symbol):
            self.setting.setStOrderStatus(self.idx, 'complete', self.direction)
            self.setting.setOrderStatus(self.idx, self.direction, 0)
            self.shutDownCheckSchedule()
            self.del_run()

    # 이전 주문 완료 이면 현재 주문 취소
    def cancelCurrentOrders(self):
        cancel_order = htx_cancel_order.CancelOrder(self.api_key, self.secret_key, self.user_num)
        if cancel_order.onCancelOrder(self.order_id, self.symbol):
            self.setting.setStOrderStatus(self.idx, 'complete', self.direction)
            self.setting.setOrderStatus(self.idx, self.direction, 0)
            idx = self.setting.checkNextIndex(0, self.direction)
            if idx == 0:
                self.sleep_time(idx)
                self.run_reorder(idx, self.direction)
            self.shutDownCheckSchedule()
            self.del_run()

    def checkHoldingStatus(self):
        print(f"Holding - current_price={self.setting.symbol_price}")
        if self.direction == 'buy':
            price1 = utils.getRoundDotDigit(float(self.setting.BUY_PRICE[0]), 6)
            # 현재 가격이 홀딩 조건 가격 보다 더 작으면
            limit_price = utils.getRoundDotDigit(float(price1 - price1 * (self.hold_rate / 100)), 6)
            print(f"    symbol={self.symbol}-buy, limit_price={limit_price}")
            if self.setting.symbol_price <= limit_price and price1 > 0:
                self.setting.holding_status = True
                hold_price = utils.getRoundDotDigit(float(self.setting.symbol_price - self.setting.symbol_price * (3 / 100)), 6)
                holdingCls = htx_hoding_run.HoldingOrderTradeHTX(self.param, self.w_param, self.rdb, self.setting)
                print(f"    hold_price={hold_price}")
                holdingCls.run_holding_thread(4, 'sell', hold_price)
        elif self.direction == 'sell':
            price1 = utils.getRoundDotDigit(float(self.setting.SELL_PRICE[0]), 6)
            # 현재 가격이 홀딩 조건 가격 보다 더 커지면
            limit_price = utils.getRoundDotDigit(float(price1 + price1 * (self.hold_rate / 100)), 6)
            print(f"    symbol={self.symbol}-sell, limit_price={limit_price}")
            if self.setting.symbol_price >= limit_price and price1 > 0:
                self.setting.holding_status = True
                hold_price = utils.getRoundDotDigit(float(self.setting.symbol_price + self.setting.symbol_price * (3 / 100)), 6)
                holdingCls = htx_hoding_run.HoldingOrderTradeHTX(self.param, self.w_param, self.rdb, self.setting)
                print(f"    hold_price={hold_price}")
                holdingCls.run_holding_thread(4, 'buy', hold_price)
