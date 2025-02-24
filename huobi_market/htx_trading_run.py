import concurrent.futures
import time
from apscheduler.schedulers.blocking import BlockingScheduler

import utils
from config import connect_redis, connect_db
from huobi_market import htx_hoding_run, htx_order_info


class RunTrading:
    def __init__(self, api_key, secret_key, symbol, idx, direction, param, w_param, rdb, price, swap_order, setting,
                 tradingCls, user_num, auto_ctime, balance, immediate):
        self.idx = idx
        self.direction = direction
        self.api_key = api_key
        self.secret_key = secret_key
        self.symbol = symbol
        self.w_param = w_param
        self.auto_ctime = auto_ctime

        # 선 주문 취소 시간(초)
        self.first_cancel_time = int(w_param['m5'])
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
        # self.reorder_range = int(w_param['m16'])
        self.param = param
        self.rate_rev = float(param['rate_rev'])
        self.rate_liq = float(param['rate_liq'])
        self.coin_num = int(param['coin_num'])
        self.bet_limit = int(param['bet_limit'])
        self.leverage = int(param['leverage'])
        self.dot_digit = int(param['dot_digit'])
        # 홀딩 조건 퍼센트
        self.hold_rate = int(w_param['h1'])

        self.rdb = rdb
        self.order_price = price
        self.tradingCls = tradingCls
        self.setting = setting
        self.user_num = user_num
        # scheduler
        self.check_scheduler = None
        self.run_scheduler = False
        self.scheduler_time = 3

        self.order_info = None
        self.checkOrderCnt = 0
        self.cancel_time = 0
        self.is_position = False
        self.next_price = 0
        self.amount = 0
        self.balance = balance
        self.swap_order = swap_order
        # Broker ID
        self.brokerID = w_param['brokerID']
        self.order_info = htx_order_info.HuobiOrderInfo(self.api_key, self.secret_key, self.symbol)

        self.class_status = 0
        self.immediate = immediate

    def __del__(self):
        print(f"HTX - delete run : {self.symbol}-{self.direction} {self.idx}")

    def run_reorder(self, idx, direction, price=0):
        is_status = self.setting.getRunStatus(idx, direction)
        if is_status == 1:
            return

        if self.setting.is_close or self.setting.s_brake or self.setting.l_stop:
            return
        re_idx = self.setting.checkNextIndex(idx, self.direction)
        if re_idx > -1:
            self.tradingCls.run_thread(re_idx, direction, price)
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
                # 정지된 스레드 닫고 재시작
                run_status = self.setting.getRunStatus(self.idx, self.direction)
                pos_status = self.setting.getOrderStatus(self.idx, self.direction)
                if run_status == 0 and pos_status == 0:
                    self.class_status = 2
                    self.shutDownCheckSchedule()
                    self.del_run()
                    return

                # 10초 간격 으로 주문 청산 상태 확인
                if self.checkOrderCnt >= 10:
                    work1 = executor.submit(self.checkTradeOrder)
                    works.append(work1)
                    self.checkOrderCnt = 0
                else:
                    self.checkOrderCnt += self.scheduler_time

                # [m5]체결 되지 않은 주문 취소
                if run_status == 1 and pos_status < 6 and self.idx == 0:
                    if self.cancel_time >= self.first_cancel_time:
                        work2 = executor.submit(self.cancelFirstOrder)
                        works.append(work2)
                        self.cancel_time = 0
                    self.cancel_time += self.scheduler_time
                else:
                    self.cancel_time = 0
                """
                # Holding 상태 체크
                if self.setting.holding_status is False:
                    if self.setting.s_brake or self.setting.l_stop:
                        work3 = executor.submit(self.checkHoldingStatus)
                        works.append(work3)
                """
                if run_status == 1 and pos_status < 6:
                    if self.is_position is False:
                        work4 = executor.submit(self.onOpenOrderPosition)
                        works.append(work4)

                # 최대 청산 가격 얻기
                if self.direction == 'sell':
                    if self.setting.peak_max_price > self.setting.symbol_price:
                        self.setting.peak_max_price = self.setting.symbol_price
                elif self.direction == 'buy':
                    if self.setting.peak_max_price < self.setting.symbol_price:
                        self.setting.peak_max_price = self.setting.symbol_price

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

    def checkOrderExecution(self, amount):
        self.setting.setRunStatus(self.idx, self.direction, 1)
        self.setting.setOrderStatus(self.idx, self.direction, 3)
        self.class_status = 1
        self.amount = amount
        self.start_order_scheduler()

    def onOpenOrderPosition(self):
        # 주문이 오픈 상태로 설정
        is_open = False
        if self.direction == 'buy':
            if self.order_price <= self.setting.symbol_price:
                is_open = True
        elif self.direction == 'sell':
            if self.order_price >= self.setting.symbol_price:
                is_open = True

        if is_open is False:
            self.is_position = False
            return
        self.is_position = True

        price = 0
        min_max_pro = self.getMinMaxPro(self.order_price)
        if self.direction == "sell":
            if self.idx == 0 and self.immediate is False:
                price = self.order_price - self.order_price * ((self.rate_liq + min_max_pro) / 100) * self.strengths[
                    self.idx]
            else:
                price = self.order_price
        elif self.direction == "buy":
            if self.idx == 0 and self.immediate is False:
                price = self.order_price + self.order_price * ((self.rate_liq + min_max_pro) / 100) * self.strengths[
                    self.idx]
            else:
                price = self.order_price
        state, order_id, volume = self.swap_order.onTradingSwapOrder(self.direction, self.idx, self.balance,
                                                                     self.amount, self.order_price, self.leverage,
                                                                     self.bet_limit,
                                                                     price, self.rate_rev, self.rate_liq, self.brokerID)
        if state:
            datetime = utils.setTimezoneDateTime().strftime("%Y-%m-%d %H:%M:%S")
            print(f"      onOpenOrderPosition : --{datetime}-- user={self.user_num}, {self.symbol}-{self.direction} {self.idx},  order_id={order_id}")
            if self.idx == 0:
                # 포지션 된 주문의 반대 방향은 주문 취소 한다
                self.cancelReverseOrder()

            # 마켓 주문 가격 얻기
            order_price, order_money = self.order_info.onCheckOrderInfo(order_id, self.user_num)

            tp_price = 0
            sl_price = 0
            rate_liq = self.rate_liq
            if self.idx > 0:
                # B2 S2 이상의 주문 에서는 손실율 을 설정값 의 절반 값으로 설정
                rate_liq = self.rate_liq / 2

            if self.direction == "sell":
                tp_price = utils.getRoundDotDigit(
                    order_price - order_price * (self.rate_rev / 100) * (1 + self.strengths[self.idx]) / 2,
                    self.dot_digit)
                sl_price = utils.getRoundDotDigit(order_price + order_price * (rate_liq / 100), self.dot_digit)
            elif self.direction == "buy":
                tp_price = utils.getRoundDotDigit(
                    order_price + order_price * (self.rate_rev / 100) * (1 + self.strengths[self.idx]) / 2,
                    self.dot_digit)
                sl_price = utils.getRoundDotDigit(order_price - order_price * (rate_liq / 100), self.dot_digit)
            # tp/sl 보관
            self.order_info.onKeep_TPSL_Price(order_id, self.user_num, tp_price, sl_price)
            self.setting.setStOrderStatus(self.idx, 'create', self.direction, order_price, tp_price, sl_price,
                                          self.amount, volume, order_money, order_id)
        else:
            print(f"onOpenOrderPosition : state={state}")
            self.class_status = 2
            self.shutDownCheckSchedule()
            self.del_run()
            self.setting.setStOrderStatus(self.idx, 'complete', self.direction)
            self.run_reorder(self.idx, self.direction)

    # 10초 간격 으로 해당 주문 체결이 완료 되었 는지 체크 하기
    def checkTradeOrder(self):
        pos_status = self.setting.getOrderStatus(self.idx, self.direction)
        if pos_status < 6:
            return
        # 주문이 SL 상태 인지 체크
        tp, sl = self.setting.getTpSl(self.idx, self.direction)
        if sl == 0:
            return
        b_complete = False
        if self.direction == 'buy':
            if self.setting.symbol_price <= sl:
                b_complete = True
        elif self.direction == 'sell':
            if self.setting.symbol_price >= sl:
                b_complete = True

        b_max_liq = self.onCheckLiquidationMaxPrice()
        if b_max_liq:
            b_complete = True

        if b_complete:
            # 주문 닫고 새 주문 넣기
            datetime = utils.setTimezoneDateTime().strftime("%Y-%m-%d %H:%M:%S")
            print(f"SL Close Order : --{datetime}-- user={self.user_num}, {self.symbol}-{self.direction} {self.idx}, sl={sl}, symbol_price={self.setting.symbol_price}")
            self.tradingCls.restartSymbolOrder(False, 0)
            # self.closeSLOrders()
            # 재 주문 넣기
            # self.setReOrder()
        else:
            # 다음 주문 넣기
            next_status = self.setting.getNextStatus(self.idx, self.direction)
            is_next_price = self.calcNextOrderPrice()
            if is_next_price and next_status == 0:
                self.setNextOrder()
    """
    # 재주문 넣기
    def setReOrder(self):
        # break 상태 나 holding 상태 이면 주문을 넣지 않는다.
        if self.setting.s_brake or self.setting.l_stop or self.setting.holding_status:
            return
        if self.idx == 0:
            self.sleep_time(self.idx)
            self.run_reorder(self.idx, self.direction)
    """
    # 다음 주문 넣기
    def setNextOrder(self):
        # break 상태 나 holding 상태 이면 주문을 넣지 않는다.
        if self.setting.s_brake or self.setting.l_stop or self.setting.holding_status:
            return
        if self.idx < 3:
            number = self.idx + 1
        else:
            number = 0
        next_idx = self.setting.checkNextIndex(number, self.direction)
        if next_idx > -1:
            # 현 주문의 다음 주문 넣기
            self.setting.setNextStatus(self.idx, self.direction, 1)
            self.sleep_time(next_idx)
            self.run_reorder(next_idx, self.direction, self.next_price)

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

    # 선 주문 취소
    def cancelFirstOrder(self):
        # self.sleep_time(self.idx)
        run = self.setting.getRunStatus(0, self.direction)
        pos = self.setting.getOrderStatus(0, self.direction)
        if run == 1 and pos < 6:
            self.class_status = 2
            self.shutDownCheckSchedule()
            self.del_run()
            self.setting.setStOrderStatus(self.idx, 'complete', self.direction)
            self.run_reorder(self.idx, self.direction)

    # SL 가격 으로 완료 된 주문 끝내기
    """
    def closeSLOrders(self):
        volume = self.setting.getVolume(self.idx, self.direction)
        order_money = self.setting.getOrderMoney(self.idx, self.direction)
        # 주문 닫는 api 호출 하기
        order_id = self.setting.getOrderID(self.idx, self.direction)
        close_price = self.setting.symbol_price
        close_side = self.direction
        profit = 0
        if self.direction == "sell":
            close_price = self.setting.symbol_price + self.setting.symbol_price * (5 / 100)
            profit = (self.order_price - self.setting.symbol_price) / self.order_price * order_money
            close_side = "buy"
        elif self.direction == "buy":
            close_price = self.setting.symbol_price - self.setting.symbol_price * (5 / 100)
            profit = (self.setting.symbol_price - self.order_price) / self.order_price * order_money
            close_side = "sell"
        profit = utils.getRoundDotDigit(profit, 6)
        make_money = order_money + profit
        b_cl, res = self.swap_order.onTradingSwapCloseOrder(self.symbol, close_side, order_id, volume, close_price, make_money, profit, self.leverage, self.setting.symbol_price, self.brokerID)
        # 주문 서비스 종료
        if res == 1:
            if b_cl is False:
                self.swap_order.saveClosedOrderInfo(self.symbol, order_id, order_id, close_price, make_money, profit)
            self.class_status = 2
            self.shutDownCheckSchedule()
            self.del_run()
            self.setting.setStOrderStatus(self.idx, 'complete', self.direction)
            for i in range(self.idx, 4):
                run = self.setting.getRunStatus(i, self.direction)
                pos = self.setting.getOrderStatus(i, self.direction)
                if run == 1 and pos < 6:
                    self.setting.setRunStatus(i, self.direction, 0)
                    self.setting.setOrderStatus(i, self.direction, 0)
        else:
            time.sleep(10)
            self.closeSLOrders()
    """
    # 반대 주문 취소
    def cancelReverseOrder(self):
        close_side = "buy"
        if self.direction == "sell":
            close_side = "buy"
        elif self.direction == "buy":
            close_side = "sell"
        run = self.setting.getRunStatus(0, close_side)
        pos = self.setting.getOrderStatus(0, close_side)
        if run == 1 and pos < 6:
            self.setting.setRunStatus(0, close_side, 0)
            self.setting.setOrderStatus(0, close_side, 0)
            print(f"      cancelReverseOrder : Positioned Order={self.symbol}-{self.direction}, Cancel Order={self.symbol}-{close_side}")

    # Holding 상태 확인
    def checkHoldingStatus(self):
        s1_status = self.setting.getOrderStatus(0, 'sell')
        s2_status = self.setting.getOrderStatus(1, 'sell')
        b1_status = self.setting.getOrderStatus(0, 'buy')
        b2_status = self.setting.getOrderStatus(1, 'buy')
        if s1_status == 6 and s2_status == 6 and b1_status == 6 and b2_status == 6:
            # S1S2 + B1B2의 경우가 생기면 Holding 으로 상태를 전환
            self.setting.holding_status = True
            connect_db.setOrderHoldingStatus(self.user_num, self.coin_num, 'htx', 1)
        else:
            if self.direction == 'buy':
                price1 = utils.getRoundDotDigit(float(self.setting.BUY_PRICE[0]), 6)
                # 현재 가격이 홀딩 조건 가격 보다 더 커지면
                limit_price = utils.getRoundDotDigit(float(price1 + price1 * (self.hold_rate / 100)), 6)
                if self.setting.symbol_price >= limit_price and price1 > 0:
                    self.setting.holding_status = True
                    hold_price = utils.getRoundDotDigit(
                        float(self.setting.symbol_price - self.setting.symbol_price * (5 / 100)), 6)
                    holdingCls = htx_hoding_run.HoldingOrderTradeHTX(self.param, self.w_param, self.rdb, self.setting)
                    holdingCls.run_holding_thread(4, 'sell', hold_price)
            elif self.direction == 'sell':
                price1 = utils.getRoundDotDigit(float(self.setting.SELL_PRICE[0]), 6)
                # 현재 가격이 홀딩 조건 가격 보다 더 작으면
                limit_price = utils.getRoundDotDigit(float(price1 - price1 * (self.hold_rate / 100)), 6)
                if self.setting.symbol_price <= limit_price and price1 > 0:
                    self.setting.holding_status = True
                    hold_price = utils.getRoundDotDigit(
                        float(self.setting.symbol_price + self.setting.symbol_price * (5 / 100)), 6)
                    holdingCls = htx_hoding_run.HoldingOrderTradeHTX(self.param, self.w_param, self.rdb, self.setting)
                    holdingCls.run_holding_thread(4, 'buy', hold_price)

    # 다음 주문 가격 확인
    def calcNextOrderPrice(self):
        if self.setting.holding_status:
            return False
        if self.idx < 3:
            next_idx = self.idx + 1
        else:
            next_idx = 0
        self.next_price = 0
        if self.direction == 'buy':
            comp_price = self.order_price + (self.order_price * (self.rate_liq / 100)) * self.strengths[next_idx]
            if self.setting.symbol_price >= comp_price:
                self.next_price = self.setting.symbol_price + self.setting.symbol_price * (self.rate_liq / 100) * \
                                  self.strengths[next_idx]
        elif self.direction == 'sell':
            comp_price = self.order_price - (self.order_price * (self.rate_liq / 100)) * self.strengths[next_idx]
            if self.setting.symbol_price <= comp_price:
                self.next_price = self.setting.symbol_price - self.setting.symbol_price * (self.rate_liq / 100) * \
                                  self.strengths[next_idx]

        if self.next_price > 0:
            self.next_price = utils.getRoundDotDigit(self.next_price, self.dot_digit)
            return True
        return False

    # 최대 가격이 주문 가격의 1% 보다 크면서 하락 일 경우 최대 가격과 주문 가격의 차이의 50%에서 청산
    # 최대 가격이 주문 가격의 1% 미만 이면 하락 일 경우 주문 가격 (혹은 현재 가격)으로 청산
    def onCheckLiquidationMaxPrice(self):
        pro = 0
        max_pro = 1
        liq_pro = 50
        if self.setting.peak_max_price == 0:
            return False
        if self.direction == 'buy':
            pro = ((self.setting.peak_max_price - self.order_price) / self.order_price) * 100
        elif self.direction == 'sell':
            pro = ((self.order_price - self.setting.peak_max_price) / self.setting.peak_max_price) * 100

        if pro >= max_pro:
            if self.direction == 'buy':
                if self.setting.symbol_price < self.setting.peak_max_price:
                    liq_price = self.setting.peak_max_price - ((self.setting.peak_max_price - self.order_price) / liq_pro) * 100
                    if self.setting.symbol_price <= liq_price:
                        print(f"   onCheckLiquidationMaxPrice : {self.symbol} {self.direction} {self.idx}")
                        return True
            elif self.direction == 'sell':
                if self.setting.symbol_price > self.setting.peak_max_price:
                    liq_price = self.order_price - ((self.order_price - self.setting.peak_max_price) / liq_pro) * 100
                    if self.setting.symbol_price >= liq_price:
                        print(f"   onCheckLiquidationMaxPrice : {self.symbol} {self.direction} {self.idx}")
                        return True

        return False
