import concurrent.futures
import threading

from apscheduler.schedulers.background import BackgroundScheduler
import utils
from config import connect_db, connect_redis
from huobi_market import htx_swap_order, htx_setting, htx_order_info, htx_order_history
from huobi_market.htx_balance import getHuobiFutureBalance


class HoldingOrderTradeHTX:
    def __init__(self, param, w_param, rdb):
        self.param = param
        self.w_param = w_param
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

        # 주문 강도
        self.strengths = [float(w_param['m1']), float(w_param['m2']), float(w_param['m3']), float(w_param['m4'])]
        # 주문 수량
        self.orderCounts = [float(w_param['m12']), float(w_param['m13']), float(w_param['m14']), float(w_param['m15'])]

        self.rdb = rdb

        # Broker ID
        self.brokerID = w_param['brokerID']

        self.swap_order = None
        self.setting = htx_setting.HuobiSetting()
        self.live_run = None

        self.holding_scheduler = None
        self.holding_period = 3

        self.order_info = htx_order_info.HuobiOrderInfo(self.api_key, self.secret_key, self.symbol)
        self.close_history = htx_order_history.HuobiOrderHistory(self.api_key, self.secret_key, self.symbol)
        self.hold_order_id = 0
        self.direction = ''
        self.tp = 0
        self.sl = 0
        self.close_order_id = ''
        self.close_status = 0
        self.search_time = 0

    def __del__(self):
        print(f"HTX - holding delete run : {self.symbol}-{self.direction} 4")

    def del_run(self):
        del self

    def onTradingScheduler(self):
        self.holding_scheduler = BackgroundScheduler()
        self.holding_scheduler.add_job(self.tradeScheduler, 'interval', seconds=self.holding_period, max_instances=50, misfire_grace_time=10, coalesce=True)
        self.holding_scheduler.start()

    def shutDownSchedule(self):
        try:
            if self.holding_scheduler.running:
                self.holding_scheduler.shutdown(wait=False)
            else:
                print("Huobi trade_scheduler is not running")
        except Exception as e:
            print(f"Huobi trade_scheduler has already been shutdown. {e}")

    def tradeScheduler(self):
        try:
            if self.holding_scheduler is None:
                return
            with concurrent.futures.ThreadPoolExecutor() as executor:
                works = []
                # 체결 된 주문이 존재 하는지 체크
                if self.setting.holding_status:
                    work0 = executor.submit(self.checkTradeOrder)
                    works.append(work0)
                concurrent.futures.wait(works)
                executor.shutdown()
        except Exception as e:
            print(f"HTX tradeScheduler error : {e}")

    def run_holding_thread(self, idx, direction, price):
        try:
            print(f"symbol={self.symbol} - {direction}, price={price}")
            self.swap_order = htx_swap_order.TradeSwapOrder(self.api_key, self.secret_key, self.symbol,
                                                            self.user_num, self.coin_num, self.dot_digit,
                                                            self.min_digit)
            balance = getHuobiFutureBalance(self.api_key, self.secret_key)
            if balance is None:
                return
            if balance > 0:
                connect_db.setUsersAmount(self.user_num, 'htx', utils.getRoundDotDigit(float(balance), 2))

            hold_thread = threading.Thread(target=self.onCreateIsolatedTPSL, args=(idx, direction, balance, price))
            hold_thread.start()
        except Exception as e:
            print(f"HTX run_thread error : {e}")
            return

    # create holding order
    def onCreateIsolatedTPSL(self, idx, direction, balance, price):
        if price == 0:
            return
        self.direction = direction
        amount = self.bet_limit * self.orderCounts[2] + self.bet_limit * self.orderCounts[3]
        tp_price = 0
        sl_price = 0
        if direction == "sell":
            tp_price = price - price * (self.rate_rev / 100) * (1 + self.strengths[3]) / 2
            sl_price = price + price * (self.rate_liq / 100)
        elif direction == "buy":
            tp_price = price + price * (self.rate_rev / 100) * (1 + self.strengths[3]) / 2
            sl_price = price - price * (self.rate_liq / 100)

        if self.setting.symbol_price == 0:
            self.setting.symbol_price = connect_redis.getCoinCurrentPrice(self.rdb, 'htx', self.symbol, 'float')

        if float(self.setting.symbol_price) > 0:
            state, self.hold_order_id, self.tp, self.sl = self.swap_order.onTradingSwapOrder(direction, idx, balance, amount, float(self.setting.symbol_price), self.leverage, self.bet_limit,
                                                                                             price, tp_price, sl_price, self.rate_rev, self.rate_liq, self.brokerID, self.coin_num)
            print(f"symbol={self.symbol}, hold_order_id={self.hold_order_id}, state={state}  tp={self.tp}")
            if state:
                self.onTradingScheduler()

    # Holding 주문 체결 확인
    def checkTradeOrder(self):
        # 주문이 체결 되였 는지, 청산이 완료 되였 는지 체크
        status = self.order_info.onCheckOrderInfo(self.hold_order_id, self.user_num)
        print(f"user_num={self.user_num}, status={status}")
        if status == 4 or status == 6:
            # 주문 청산 완료 되었 는지 체크 하기
            side = 'sell'
            if self.direction == 'sell':
                side = 'buy'
            if self.close_order_id == '':
                self.search_time = 0
                offset, self.close_order_id = self.close_history.getHuobiOrderHistory(self.hold_order_id, self.user_num, self.tp, self.sl, side)
            else:
                if self.close_status == 7:
                    offset = self.close_history.getHuobiOrderRiskHistory(self.user_num, self.close_order_id)
                else:
                    if self.search_time == 0:
                        self.search_time = utils.setTimezoneTimestamp()
                    offset, self.close_status = self.close_history.getHuobiOrderIDHistory(self.user_num, self.close_order_id, self.search_time)

            # 주문이 청산 완료 되었 을 때
            if offset == 'close':
                print(f"offset={offset}")
                self.setting.holding_status = False
                connect_db.setOrderClose(self.user_num, self.coin_num, 'htx')
                # 청산 완료된 스케쥴 끝내기
                self.shutDownSchedule()
                self.del_run()
