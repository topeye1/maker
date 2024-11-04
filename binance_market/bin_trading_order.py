import time
from binance.client import Client
from binance.error import ClientError
from binance.exceptions import BinanceAPIException

import utils
from config import connect_db


class BinanceTradeOrder:
    def __init__(self, api_key, secret_key, symbol, user_num, coin_num, dot_digit, min_digit):
        self.api_key = api_key
        self.secret_key = secret_key
        self.symbol = symbol
        self.user_num = user_num
        self.coin_num = coin_num
        self.dot_digit = dot_digit
        self.min_digit = min_digit
        self.client = Client(api_key, secret_key)
        self.limit_price = 0
        self.quantity = 0
        self.order_time = 0

    def set_leverage(self, lever_rate):
        try:
            self.client.futures_change_leverage(symbol=self.symbol, leverage=lever_rate, recvWindow=60000)
        except ClientError as e:
            print(f'Binance set_leverage() error : {e}')

    def get_margin_type(self):
        try:
            position_risk = self.client.futures_position_information(symbol=self.symbol)
            for position in position_risk:
                if position['symbol'] == self.symbol:
                    margin_type = position['marginType']
                    return margin_type
            return 'cross'
        except BinanceAPIException as e:
            print("Binance get_margin_type() error : ", e)
            return 'cross'

    def set_margin_type(self):
        marginType = 'ISOLATED'
        try:
            m_type = self.get_margin_type()
            if m_type.upper() != marginType:
                self.client.futures_change_margin_type(symbol=self.symbol, marginType=marginType)
        except BinanceAPIException as e:
            print("Binance set_margin_type() error : ", e)

    def get_qty_precision(self):
        resp = self.client.futures_exchange_info()['symbols']
        for elem in resp:
            if elem['symbol'] == self.symbol:
                return elem['quantityPrecision']

    def set_quantity(self, price, volume):
        try:
            qty_precision = self.get_qty_precision()
            qty = round(volume / price, qty_precision)
            return qty
        except Exception as e:
            print(f"Binance set_quantity error : {e}")
            return 0

    def saveData(self, order_limit, idx, balance, volume, lever_rate, bet_limit, rate_rev, rate_liq):
        order_id = ''
        try:
            if order_limit is not None:
                order_id = str(order_limit['orderId'])
                side = str(order_limit['side']).lower()
                price = order_limit['price']
                origQty = order_limit['origQty']
                amount = float(price) * float(origQty)
                update_time = utils.setTimezoneDateTime().strftime("%Y-%m-%d %H:%M:%S")
            else:
                return False, ''

            order_data = {
                'user_num': self.user_num,
                'order_num': f'{order_id}',
                'side': side,
                'idx': idx,
                'coin_num': self.coin_num,
                'symbol': self.symbol,
                'market': 'bin',
                'live_status': 1,
                'order_position': 0,
                'hold_money': balance,
                'leverage': lever_rate,
                'bet_limit': bet_limit,
                'rate_rev': rate_rev,
                'rate_liq': rate_liq,
                'order_volume': volume,
                'order_money': amount,
                'order_price': price,
                'order_date': update_time
            }
            type_data = {
                'user_num': 'int',
                'order_num': 'str',
                'side': 'str',
                'idx': 'int',
                'coin_num': 'int',
                'symbol': 'str',
                'market': 'str',
                'live_status': 'int',
                'order_position': 'int',
                'hold_money': 'double',
                'leverage': 'int',
                'bet_limit': 'int',
                'rate_rev': 'float',
                'rate_liq': 'float',
                'order_volume': 'double',
                'order_money': 'double',
                'order_price': 'double',
                'order_date': 'str'
            }

            connect_db.setTradeOrder(order_data, type_data)
            return True, order_id, price
        except Exception as e:
            print(f'Binance save_db error : {e}')
            return False, order_id, 0

    def binanceOpenLimitOrder(self, direction, idx, balance, volume, c_price, lever_rate, bet_limit, price, rate_rev, rate_liq):
        self.set_leverage(lever_rate)
        self.set_margin_type()
        self.quantity = self.set_quantity(c_price, volume)
        if self.quantity == 0:
            self.quantity = volume
        order_id = ''
        self.limit_price = utils.getRoundDotDigit(price, self.dot_digit)
        self.order_time = int(time.time() * 1000)
        try:
            if direction == 'buy':
                limit_side = Client.SIDE_BUY
                positionSide = 'LONG'
            else:
                limit_side = Client.SIDE_SELL
                positionSide = 'SHORT'

            # limit
            order_limit = self.client.futures_create_order(
                symbol=self.symbol,
                type=Client.FUTURE_ORDER_TYPE_LIMIT,
                side=limit_side,
                positionSide=positionSide,
                timeInForce=Client.TIME_IN_FORCE_GTC,
                quantity=self.quantity,
                price=self.limit_price,
                timestamp=self.order_time
            )
            order_id = str(order_limit['orderId'])
            return self.saveData(order_limit, idx, balance, volume, lever_rate, bet_limit, rate_rev, rate_liq)
        except Exception as e:
            print(f"Binance binanceOpenLimitOrder() error : {e}")
            return False, order_id, 0

    def binanceOpenTpSlOrder(self, direction, order_id, tp, sl, pre_ids):
        try:
            if direction == 'buy':
                trigger_side = Client.SIDE_SELL
                positionSide = 'LONG'
            else:
                trigger_side = Client.SIDE_BUY
                positionSide = 'SHORT'

            sl_price = utils.getRoundDotDigit(sl, self.dot_digit)
            tp_price = utils.getRoundDotDigit(tp, self.dot_digit)

            # stop loss
            order_sl = self.client.futures_create_order(
                symbol=self.symbol,
                type=Client.FUTURE_ORDER_TYPE_STOP_MARKET,
                side=trigger_side,
                positionSide=positionSide,
                timeInForce=Client.TIME_IN_FORCE_GTC,
                quantity=self.quantity,
                closePosition='true',
                stopPrice=sl_price,
                timestamp=self.order_time
            )
            sl_id = str(order_sl['orderId'])

            # take profit
            order_tp = self.client.futures_create_order(
                symbol=self.symbol,
                type=Client.FUTURE_ORDER_TYPE_TAKE_PROFIT_MARKET,
                side=trigger_side,
                positionSide=positionSide,
                timeInForce=Client.TIME_IN_FORCE_GTC,
                quantity=self.quantity,
                closePosition='true',
                stopPrice=tp_price,
                timestamp=self.order_time
            )
            tp_id = str(order_tp['orderId'])

            self.saveTpSlData(order_id, tp_id, sl_id, tp_price, sl_price, pre_ids)

            return tp_id, sl_id
        except Exception as e:
            print(f"Binance binanceOpenTpSlOrder() error : {e}")
            return '', ''

    def saveTpSlData(self, order_id, tp_id, sl_id, tp_price, sl_price, pre_ids):
        try:
            order_data = {
                'tp_id': tp_id,
                'sl_id': sl_id,
                'tp_price': tp_price,
                'sl_price': sl_price
            }
            type_data = {
                'tp_id': 'str',
                'sl_id': 'str',
                'tp_price': 'double',
                'sl_price': 'double'
            }

            where = f"user_num={self.user_num} AND (order_num='{order_id}'"
            """
            if len(pre_ids) > 0:
                for pre_id in pre_ids:
                    where += f" OR order_num='{pre_id}'"
            """
            where += f") AND symbol='{self.symbol}'"
            connect_db.setUpdateOrder(order_data, type_data, where)
        except Exception as e:
            print(f'Binance saveTpSlData error : {e}')
