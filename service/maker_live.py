from config import ConnRedis
from huobi_market.htx_trading import OrderTradeHTX


class MakerLiveService:
    def __init__(self, param, w_param):
        self.live_status = False
        self.market = str(param['market'])

        redis_db = ConnRedis()
        self.rdb = redis_db.init_db()

        self.order_trade_htx = OrderTradeHTX(param, w_param, self.rdb)

    def startOrderTradingHTX(self):
        self.order_trade_htx.run_thread(0, "sell")
        self.order_trade_htx.run_thread(0, "buy")
