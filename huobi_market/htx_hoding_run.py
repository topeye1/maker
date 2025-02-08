import threading

import utils
from config import connect_db, connect_redis
from huobi_market import htx_swap_order, htx_order_info, htx_order_history
from huobi_market.htx_balance import getHuobiFutureBalance


class HoldingOrderTradeHTX:
    def __init__(self, param, w_param, rdb, setting):
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

        self.rdb = rdb

        # Broker ID
        self.brokerID = w_param['brokerID']

        self.swap_order = None
        self.setting = setting
        self.order_info = htx_order_info.HuobiOrderInfo(self.api_key, self.secret_key, self.symbol)

    def run_holding_thread(self, idx, direction, price):
        try:
            self.swap_order = htx_swap_order.TradeSwapOrder(self.api_key, self.secret_key, self.symbol,
                                                            self.user_num, self.coin_num, self.dot_digit,
                                                            self.min_digit)
            balance = getHuobiFutureBalance(self.api_key, self.secret_key)
            if balance is None:
                return
            if balance > 0:
                connect_db.setUsersAmount(self.user_num, 'htx', utils.getRoundDotDigit(float(balance), 2))

            hold_thread = threading.Thread(target=self.onOpenHoldingOrderPosition, args=(idx, direction, balance, price))
            hold_thread.start()
        except Exception as e:
            print(f"HTX run_holding_thread error : {e}")
            return

    # create holding order
    def onOpenHoldingOrderPosition(self, idx, direction, balance, price):
        try:
            if price == 0:
                return

            print(f"onOpenHoldingOrderPosition : {self.symbol}-{direction}, BUY_AMOUNT={self.setting.BUY_AMOUNT}, SELL_AMOUNT={self.setting.SELL_AMOUNT}")
            amount = 0
            if direction == "sell":
                for buy_amount in self.setting.BUY_AMOUNT:
                    amount += buy_amount
            elif direction == "buy":
                for sell_amount in self.setting.SELL_AMOUNT:
                    amount += sell_amount

            if self.setting.symbol_price == 0:
                self.setting.symbol_price = connect_redis.getCoinCurrentPrice(self.rdb, 'htx', self.symbol, 'float')

            if float(self.setting.symbol_price) > 0 and amount > 0:
                state, order_id, volume, order_money = self.swap_order.onTradingSwapOrder(direction, idx, balance, amount, float(self.setting.symbol_price), self.leverage, self.bet_limit,
                                                                                          price, self.rate_rev, self.rate_liq, self.brokerID, self.coin_num)
                print(f"Holding order : {self.symbol} {direction}-{idx}, state={state}, order_id={order_id}, volume={volume}, amount={amount}, order_money={order_money}")
                if state:
                    # 마켓 주문 가격 얻기
                    order_price, order_money = self.order_info.onCheckOrderInfo(order_id, self.user_num)
                    self.checkHoldingOrderExecution(idx, direction, amount, volume, order_money, order_id)
        except Exception as e:
            print(f"HTX onOpenHoldingOrderPosition error : {self.symbol}, '{e}'")
            return

    def checkHoldingOrderExecution(self, idx, direction, amount, volume, money, order_id):
        self.setting.setStOrderStatus(idx, 'create', direction, self.setting.symbol_price, 0, 0, amount, volume, money, order_id)
