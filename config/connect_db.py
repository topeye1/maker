from database import MariaDB

maria_db = MariaDB()


def getParameters():
    parameters = maria_db.getParameters()
    return parameters


def getApiKeys():
    keys = maria_db.getApiKeys()
    return keys


def getLiveCoins():
    coins = maria_db.getLiveCoin()
    return coins


def getLiveCoinStatus(user_num, coin_num, market):
    status = maria_db.getLiveCoinStatus(user_num, coin_num, market)
    return status


def setUsersAmount(user_num, market, amount, ins=False):
    maria_db.setUsersAmount(user_num, market, amount, ins)


def setTradeOrder(data, types, status=1):
    maria_db.setTradeOrder(data, types, status)


def getTradeOrderIds(order_id):
    return maria_db.getTradeOrderIds(order_id)


def getUnSaveTradeIds(user_num, market):
    return maria_db.getUnSaveTradeIds(user_num, market)


def setUpdateOrder(data, types, where, user_num=0, symbol='', market='htx', make_price=0, profit_money=0, update_time=''):
    return maria_db.updateTradeOrder(data, types, where, user_num, symbol, market, make_price, profit_money, update_time)


"""
def setUpdateOrderPosition(maria_db, where):
    return maria_db.updateOrderPosition(where)
"""


def delCancelOrder(user_num, order_id):
    maria_db.deleteTradeOrder(user_num, order_id)


def delAllCancelOrder(symbol, user_num, market):
    maria_db.delAllCancelOrder(symbol, user_num, market)


def setCloseOrderStatus(symbol, user_num, market):
    maria_db.closePositionOrderStatus(symbol, user_num, market)


def changeBreakStatus(user_num, symbol, market, status):
    return maria_db.updateBreakStatus(user_num, symbol, market, status)


def releaseBreakStatus(user_num, symbol, market, status):
    return maria_db.updateReleaseBreakStatus(user_num, symbol, market, status)


def setOrderHoldingStatus(user_num, coin_num, market, status):
    maria_db.updateOrderHoldingStatus(user_num, coin_num, market, status)


def setOrderClose(user_num, coin_num, market):
    maria_db.updateOrderClose(user_num, coin_num, market)


def checkDoubleOrder(user_num, market, symbol, price, datetime):
    return maria_db.selectDoubleOrder(user_num, market, symbol, price, datetime)


class ConnDB:
    def __init__(self):
        self.maria_db = None

    def init_db(self):
        self.maria_db = MariaDB()
        return self.maria_db
