import copy
import json
import os

from dotenv import load_dotenv
from mysql import connector

import utils
from config import log

load_dotenv()


class MariaDB:
    def __init__(self, host=os.getenv('DB_HOST'),
                 database=os.getenv('DB_NAME'),
                 user=os.getenv('DB_USER'),
                 password=os.getenv('DB_PASSWORD')):
        self._host = host
        self._database = database
        self._user = user
        self._password = password

    def getParameters(self):
        try:
            query = f"SELECT pname, pvalue FROM fix_params WHERE enabled=1"
            rows = self.select_sql(query=query)
            watcher_params = {}
            if rows is None:
                return watcher_params
            for row in rows:
                watcher_params[row[0]] = row[1]

            bquery = f"SELECT brokerID FROM fix_broker_id LIMIT 1"
            brow = self.select_sql(query=bquery)
            if brow is None:
                watcher_params['brokerID'] = ''
            else:
                watcher_params['brokerID'] = brow[0][0]

            return watcher_params
        except Exception as e:
            self.error("getParameters " + str(e))
            return []

    def getApiKeys(self):
        try:
            query = f"SELECT a.user_num, a.market, a.api_key, a.secret_key, a.create_date, a.kid FROM tbl_api_key AS a "
            query += f"INNER JOIN(SELECT MAX(kid) as kid FROM tbl_api_key GROUP BY user_num, market) as b "
            query += f"ON a.kid = b.kid"
            rows = self.select_sql(query=query)
            if rows is None:
                return
            result = []
            for row in rows:
                watcher_params = {
                    'user_num': row[0],
                    'market': row[1],
                    'api_key': row[2],
                    'secret_key': row[3],
                    'create_date': row[4]
                }
                if len(result) > 0:
                    if utils.filterData(result, watcher_params, 'user_num', 'market'):
                        result.append(watcher_params)
                else:
                    result.append(watcher_params)

            return result
        except Exception as e:
            self.error("getApiKeys " + str(e))
            return []

    def getLiveCoin(self):
        try:
            query = f"SELECT A.cid AS cid, A.user_num AS user_num, A.coin_num AS coin_num, B.coin_name AS coin_name, "
            query += f"A.market AS market, A.bet_limit AS bet_limit, A.rate_rev AS rate_rev, A.leverage AS leverage, "
            query += f"A.rate_liq AS rate_liq, C.api_key AS api_key, C.secret_key AS secret_key, "
            query += f"B.digit AS dot_digit, B.min_volume AS min_digit "
            query += f"FROM tbl_live_coins AS A "
            query += f"LEFT JOIN fix_coins AS B ON B.coin_id = A.coin_num "
            query += f"LEFT JOIN tbl_api_key AS C ON C.kid = A.kid "
            query += f"WHERE A.is_run = 1"
            rows = self.select_sql(query=query)

            result = []
            if rows is not None:
                for row in rows:
                    watcher_params = {
                        'user_num': row[1],
                        'coin_num': row[2],
                        'coin_name': row[3],
                        'market': row[4],
                        'bet_limit': row[5],
                        'rate_rev': row[6],
                        'leverage': row[7],
                        'rate_liq': row[8],
                        'api_key': row[9],
                        'secret_key': row[10],
                        'dot_digit': row[11],
                        'min_digit': row[12]
                    }

                    result.append(watcher_params)
            return result
        except Exception as e:
            self.error("getLiveCoin " + str(e))
            return []

    def getLiveCoinStatus(self, user_num, coin_num, market):
        try:
            query = f"SELECT is_run FROM tbl_live_coins WHERE user_num = {user_num} AND coin_num={coin_num} AND market='{market}' LIMIT 1"
            rows = self.select_sql(query=query)
            if rows is None:
                return 0
            if rows:
                res = rows[0][0]
                if res == 1:
                    return 1
            return 0
        except Exception as e:
            self.error("getLiveCoinStatus " + str(e))
            return 0

    def getTradeOrderIds(self, order_id):
        try:
            query = f"SELECT order_num FROM tbl_trade_order WHERE tp_id='{order_id}' OR sl_id='{order_id}' ORDER BY order_date DESC"
            rows = self.select_sql(query=query)
            result = []
            if rows is not None:
                for row in rows:
                    result.append(row[0])
            return result
        except Exception as e:
            self.error("getLiveCoinStatus " + str(e))
            return 0

    def getUnSaveTradeIds(self, user_num, market):
        try:
            query = f"SELECT symbol, tp_id, sl_id, tp_price, sl_price FROM tbl_trade_order WHERE user_num={user_num} AND market='{market}' AND make_date='' ORDER BY order_date DESC"
            rows = self.select_sql(query=query)
            result = []
            if rows is not None:
                for row in rows:
                    params = {
                        'symbol': row[0],
                        'tp_id': row[1],
                        'sl_id': row[2],
                        'tp_price': row[3],
                        'sl_price': row[4]
                    }

                    result.append(params)
            return result
        except Exception as e:
            self.error("getLiveCoinStatus " + str(e))
            return 0

    def selMarketAmount(self, user_num, market, toDay):
        try:
            query = f"SELECT user_num "
            query += f"FROM tbl_market_amount "
            query += f"WHERE user_num={user_num} AND market='{market}' AND date='{toDay}'"
            rows = self.select_sql(query=query)
            return len(rows)
        except Exception as e:
            self.error("selMarketAmount " + str(e))

    def setUsersAmount(self, user_num, market, amount, ins):
        toDay = utils.getTimezoneToDay()
        try:
            if self.selMarketAmount(user_num, market, toDay) > 0 or ins is False:
                usql = f"UPDATE tbl_market_amount SET amount={amount} WHERE user_num={user_num} AND market='{market}' AND date='{toDay}' "
                self.update_sql(usql)
            else:
                isql = f"INSERT INTO tbl_market_amount (user_num, market, amount, date) VALUES ({user_num}, '{market}', {amount}, '{toDay}')"
                self.insert_sql(isql)
        except Exception as e:
            self.error("setUsersAmount " + str(e))

    def setTradeOrder(self, data, types, status):
        try:
            key_str = ''
            value_str = ''
            for key, value in data.items():
                key_str += f"{key},"
                if types[key] == 'str':
                    value_str += f"'{value}',"
                else:
                    value_str += f"{value},"
            fields = key_str.rstrip(',')
            values = value_str.rstrip(',')

            sql = f"INSERT INTO tbl_trade_order ({fields}) VALUES ({values})"
            self.insert_sql(sql)
            self.updateOrderLiveStatus(data['symbol'], data['user_num'], data['market'], status)
        except Exception as e:
            self.error("setTradeOrder " + str(e))

    def updateTradeOrder(self, data, types, where, user_num=0, symbol='', market='htx', make_price=0, profit_money=0, update_time=''):
        try:
            fd = ''
            for key, value in data.items():
                if types[key] == 'str':
                    value_str = f"'{value}'"
                else:
                    value_str = f"{value}"
                fd += f"{key}={value_str},"
            fields = fd.rstrip(',')

            sql = f"UPDATE tbl_trade_order SET {fields} WHERE {where}"
            res = self.update_sql(sql)

            # 만일 한 심볼에서 비슷한 시간에 가격과 이윤이 동일한 것이 존재 하면 OK로 처리
            if user_num > 0 and make_price > 0 and profit_money > 0 and symbol != '' and update_time != '':
                query = f"SELECT order_num FROM tbl_trade_order "
                query += f" WHERE user_num={user_num} AND market='{market}' AND symbol='{symbol}' AND make_price={make_price} AND profit_money={profit_money} AND make_date LIKE'{update_time}%' "
                query += f" ORDER BY order_date DESC"
                rows = self.select_sql(query=query)
                if rows is not None and len(rows) > 1:
                    for i in range(0, len(rows)):
                        if i == 0:
                            continue
                        else:
                            row = rows[i]
                            order_num = row[0]
                            usql = f"UPDATE tbl_trade_order SET make_money='OK', profit_money='OK', fee_money='OK' WHERE order_num={order_num}"
                            self.update_sql(usql)
            return res
        except Exception as e:
            self.error("updateTradeOrder " + str(e))
            return 0

    """
    def updateOrderPosition(self, where):
        try:
            sql = f"UPDATE tbl_trade_order SET order_position=1 WHERE {where}"
            res = self.update_sql(sql)
            return res
        except Exception as e:
            self.error("updateOrderPosition " + str(e))
            return 0
    """

    def closePositionOrderStatus(self, symbol, user_num, market):
        try:
            today = utils.getTimezoneToDay()
            sql = f"UPDATE tbl_trade_order SET live_status=0 WHERE "
            sql += f"symbol='{symbol}' AND user_num={user_num} AND market='{market}' "
            sql += f"AND (SUBSTRING(order_date, 1, 10)='{today}' OR SUBSTRING(make_date, 1, 10)='{today}' OR make_date='' OR live_status > 1) "
            self.update_sql(sql)
        except Exception as e:
            self.error("closePositionOrderStatus " + str(e))

    def deleteTradeOrder(self, user_num, order_id):
        try:
            sql = f"DELETE FROM tbl_trade_order WHERE user_num={user_num} AND order_num='{order_id}' AND make_date=''"
            self.delete_sql(sql)

        except Exception as e:
            self.error("setUsersAmount " + str(e))

    def updateOrderLiveStatus(self, symbol, user_num, market, status):
        try:
            order_datetime = utils.setTimezoneDateTime().strftime("%Y-%m-%d")
            sql = f"UPDATE tbl_trade_order SET live_status={status} WHERE user_num={user_num} AND symbol='{symbol}' AND market='{market}' AND (SUBSTRING(order_date, 1, 10)='{order_datetime}' OR SUBSTRING(make_date, 1, 10)='{order_datetime}')"
            res = self.update_sql(sql)
            return res

        except Exception as e:
            self.error("updateOrderLiveStatus " + str(e))
            return 0

    def delAllCancelOrder(self, symbol, user_num, market):
        try:
            sql = f"DELETE FROM tbl_trade_order WHERE user_num={user_num} AND order_position=0 AND symbol='{symbol}' AND market='{market}'"
            self.delete_sql(sql)
        except Exception as e:
            self.error("delAllCancelOrder " + str(e))

    def updateBreakStatus(self, user_num, symbol, market, status):
        try:
            today = utils.getTimezoneToDay()
            sql = f"UPDATE tbl_trade_order SET live_status={status} "
            sql += f"WHERE user_num={user_num} AND symbol='{symbol}' AND market='{market}' "
            sql += f"AND (SUBSTRING(order_date, 1, 10)='{today}' OR SUBSTRING(make_date, 1, 10)='{today}' OR make_date='') "
            res = self.update_sql(sql)
            return res
        except Exception as e:
            self.error("updateBreakStatus " + str(e))
            return 0

    def updateReleaseBreakStatus(self, user_num, symbol, market, status):
        try:
            sql = f"UPDATE tbl_trade_order SET live_status={status} "
            sql += f"WHERE user_num={user_num} AND symbol='{symbol}' AND market='{market}' "
            sql += f"AND live_status > 1 "
            res = self.update_sql(sql)
            return res
        except Exception as e:
            self.error("updateBreakStatus " + str(e))
            return 0

    def updateOrderHoldingStatus(self, user_num, coin_num, market, status):
        try:
            sql = f"UPDATE tbl_live_coins SET hold_status={status} "
            sql += f"WHERE user_num={user_num} AND coin_num={coin_num} AND market='{market}' "
            self.update_sql(sql)
        except Exception as e:
            self.error("updateOrderHoldingStatus " + str(e))

    def updateOrderClose(self, user_num, coin_num, market):
        try:
            sql = f"UPDATE tbl_live_coins SET is_run=0, hold_status=0 "
            sql += f"WHERE user_num={user_num} AND coin_num={coin_num} AND market='{market}' "
            self.update_sql(sql)
        except Exception as e:
            self.error("updateOrderClose " + str(e))

    def selectDoubleOrder(self, user_num, market, symbol, price, datetime):
        try:
            query = f"SELECT order_num "
            query += f"FROM tbl_trade_order "
            query += f"WHERE user_num={user_num} AND market='{market}' AND symbol='{symbol}' "
            query += f"AND order_price={price} AND order_date='{datetime}'"
            rows = self.select_sql(query=query)
            return len(rows)
        except Exception as e:
            self.error("selMarketAmount " + str(e))
            return 0

    def select_sql(self, query):
        conn = connector.connect(host=self._host, database=self._database, user=self._user, password=self._password)
        try:
            _cursor = conn.cursor()

            conn.start_transaction()
            _cursor.execute(query)
            return_all = _cursor.fetchall()
            _cursor.close()
            conn.commit()

            conn.close()
            return return_all
        except connector.Error as error:
            conn.rollback()
            self.error("Failed to select sql in MySQL: {}, {}".format(query, error))
            return None

    def update_sql(self, query):
        conn = connector.connect(host=self._host, database=self._database, user=self._user, password=self._password)
        try:
            _cursor = conn.cursor()

            conn.start_transaction()
            _cursor.execute(query)
            res = _cursor.rowcount
            _cursor.close()
            conn.commit()

            conn.close()
            return res
        except connector.Error as error:
            conn.rollback()
            self.error("Failed to update sql in MySQL: {}, {}".format(query, error))
            return 0

    def insert_sql(self, query):
        conn = connector.connect(host=self._host, database=self._database, user=self._user, password=self._password)
        try:
            _cursor = conn.cursor()

            conn.start_transaction()
            _cursor.execute(query)
            return_id = _cursor.lastrowid
            _cursor.close()
            conn.commit()

            conn.close()
            return return_id
        except connector.Error as error:
            conn.rollback()
            self.error("Failed to insert sql in MySQL: {}, {}".format(query, error))
            return None

    def delete_sql(self, query):
        conn = connector.connect(host=self._host, database=self._database, user=self._user, password=self._password)
        try:
            _cursor = conn.cursor()

            conn.start_transaction()
            _cursor.execute(query)
            _cursor.close()
            conn.commit()

            conn.close()
        except connector.Error as error:
            conn.rollback()
            self.error("Failed to delete_sql in MySQL: {}, {}".format(query, error))

    def error(self, message):
        print(message)
        log(type(self).__name__, message, "error")
