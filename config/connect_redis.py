import utils
from database import RedisDB


def getCoinCurrentPrice(rdb, market, symbol, types):
    try:
        current_price = rdb.get(utils.getRedisCurrentPriceKey(market, symbol), types)
        if current_price is None:
            return 0
        return float(current_price)
    except Exception as e:
        print(f"{e}")
        return 0


def getCoinMiddlePrice(rdb, market, symbol):
    try:
        field = 'price'
        middle_price = rdb.hget(utils.getRedisMiddlePriceKey(market, symbol), field)
        if middle_price is None:
            return 0
        return float(middle_price)
    except Exception as e:
        print(f"{e}")
        return 0


def getMaxMinPrice(rdb, market, symbol):
    try:
        max_price = rdb.hget(utils.getRedisMiddlePriceKey(market, symbol), 'max_price')
        min_price = rdb.hget(utils.getRedisMiddlePriceKey(market, symbol), 'min_price')
        if max_price is None:
            max_price = 0
        if min_price is None:
            min_price = 0
        return float(max_price), float(min_price)
    except Exception as e:
        print(f"{e}")
        return 0, 0


class ConnRedis:
    def __init__(self):
        self.redis_db = None

    def init_db(self):
        self.redis_db = RedisDB()
        return self.redis_db
