import time

from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceOrderException

import utils
from config import connect_db


class CancelOrder:
    def __init__(self, api_key, secret_key, user_num):
        self.api_key = api_key
        self.secret_key = secret_key
        self.user_num = user_num

    def onCancelOrder(self, order_id, symbol):
        try:
            client = Client(self.api_key, self.secret_key)
            utils.sync_time(client)
            client.futures_cancel_order(
                symbol=symbol,
                orderId=order_id,
                recvWindow=5000
            )
            connect_db.delCancelOrder(self.user_num, order_id)
            return True
        except Exception as e:
            print(f"Binance Cancel error {order_id}, {symbol} : {e}")
            return False

    def onCancelAllOrder(self, symbol, market):
        try:
            client = Client(self.api_key, self.secret_key)
            client.futures_cancel_all_open_orders(symbol=symbol)
            connect_db.delAllCancelOrder(symbol, self.user_num, market)
            return True
        except Exception as e:
            print(f"Binance All Orders Cancel error : {e}")
            return False

    def onCloseAllPosition(self, order_symbol, market):
        try:
            close_id = ''
            client = Client(self.api_key, self.secret_key)
            utils.sync_time(client)
            positions = client.futures_position_information()
            for position in positions:
                symbol = position['symbol']
                position_amt = float(position['positionAmt'])
                if order_symbol != symbol:
                    continue
                # 포지션이 0이 아닌 경우 (열려있는 포지션)
                if position_amt != 0:
                    # 포지션 방향 결정 (롱 -> 숏, 숏 -> 롱)
                    side = 'SELL' if position_amt > 0 else 'BUY'
                    positionSide = 'LONG' if side == 'SELL' else 'SHORT'
                    closeSide = 'buy' if side == 'SELL' else 'sell'

                    # 마켓 주문을 통해 포지션 청산
                    order = client.futures_create_order(
                        symbol=symbol,
                        side=side,
                        positionSide=positionSide,
                        type=Client.FUTURE_ORDER_TYPE_MARKET,
                        quantity=abs(position_amt),
                        recvWindow=5000
                    )
                    close_id = str(order['orderId'])
                    order_data = {
                        'tp_id': close_id,
                        'sl_id': close_id,
                        'live_status': 0,
                    }
                    type_data = {
                        'tp_id': 'str',
                        'sl_id': 'str',
                        'live_status': 'int',
                    }
                    where = f"symbol='{symbol}' AND user_num={self.user_num} AND market='{market}' AND side='{closeSide.lower()}' "
                    where += f"AND order_position = 1 AND make_date=''"
                    connect_db.setUpdateOrder(order_data, type_data, where)
            return close_id
        except BinanceAPIException as e:
            print(f"Binance API Exception 발생: {e}")
            return ''
        except BinanceOrderException as e:
            print(f"Binance Order Exception 발생: {e}")
            return ''
        except Exception as e:
            print(f"기타 예외 발생: {e}")
            return ''

    def saveClosePosition(self, order_symbol, close_id):
        try:
            make_amount = 0.0
            make_profit = 0.0
            make_fee = 0.0
            price = 0.0
            make_id = ''
            update_time = utils.setTimezoneDateTime().strftime("%Y-%m-%d %H:%M:%S")
            current_time = utils.setTimezoneTimestamp()
            prior_time = int(current_time) - 24 * 60 * 60 * 1000
            is_liquidation = False

            client = Client(self.api_key, self.secret_key)
            utils.sync_time(client)
            all_orders = client.futures_account_trades(
                symbol=order_symbol,
                startTime=prior_time,
                endTime=current_time,
                limit=500
            )
            for order in all_orders:
                symbol = order['symbol']
                orderId = str(order['orderId'])
                fee = float(order['commission'])
                quoteQty = float(order['quoteQty'])
                price = float(order['price'])
                profit = float(order['realizedPnl'])
                if symbol == order_symbol and profit != 0 and close_id == orderId:
                    make_amount += quoteQty
                    make_profit += profit
                    make_fee += fee
                    make_id = orderId
                    is_liquidation = True
            if is_liquidation:
                order_ids = connect_db.getTradeOrderIds(make_id)
                index = 0
                for order_id in order_ids:
                    if index == 0:
                        order_data = {
                            'make_price': price,
                            'make_money': make_amount,
                            'profit_money': make_profit,
                            'fee_money': make_fee,
                            'make_date': update_time,
                            'live_status': 0,
                            'order_position': 1
                        }
                        type_data = {
                            'make_price': 'str',
                            'make_money': 'str',
                            'profit_money': 'str',
                            'fee_money': 'str',
                            'make_date': 'str',
                            'live_status': 'int',
                            'order_position': 'int'
                        }
                    else:
                        order_data = {
                            'make_price': price,
                            'make_money': "OK",
                            'profit_money': "OK",
                            'fee_money': "OK",
                            'make_date': update_time,
                            'live_status': 0,
                            'order_position': 1,
                        }
                        type_data = {
                            'make_price': 'str',
                            'make_money': 'str',
                            'profit_money': 'str',
                            'fee_money': 'str',
                            'make_date': 'str',
                            'live_status': 'int',
                            'order_position': 'int'
                        }
                    where = f"order_num='{order_id}' AND user_num={self.user_num} AND symbol='{order_symbol}' AND make_date=''"
                    connect_db.setUpdateOrder(order_data, type_data, where)

        except Exception as e:
            print(f"Binance saveClosePosition() error : {e}")

    def onForceClosePosition(self, order_symbol, market, direction):
        try:
            close_id = ''
            client = Client(self.api_key, self.secret_key)
            utils.sync_time(client)
            positions = client.futures_position_information()
            for position in positions:
                symbol = position['symbol']
                position_amt = float(position['positionAmt'])
                if order_symbol != symbol:
                    continue
                # 포지션이 0이 아닌 경우 (열려있는 포지션)
                if position_amt != 0:
                    # 포지션 방향 결정 (롱 -> 숏, 숏 -> 롱)
                    if direction == 'sell':
                        side = 'BUY'
                    else:
                        side = 'SELL'
                    positionSide = 'LONG' if side == 'SELL' else 'SHORT'

                    # 마켓 주문을 통해 포지션 청산
                    order = client.futures_create_order(
                        symbol=symbol,
                        side=side,
                        positionSide=positionSide,
                        type=Client.FUTURE_ORDER_TYPE_MARKET,
                        quantity=abs(position_amt),
                        recvWindow=5000
                    )
                    close_id = str(order['orderId'])
                    order_data = {
                        'tp_id': close_id,
                        'sl_id': close_id,
                        'live_status': 0,
                    }
                    type_data = {
                        'tp_id': 'str',
                        'sl_id': 'str',
                        'live_status': 'int',
                    }
                    where = f"symbol='{symbol}' AND user_num={self.user_num} AND market='{market}' AND side='{direction.lower()}' "
                    where += f"AND order_position = 1 AND make_date=''"

                    connect_db.setUpdateOrder(order_data, type_data, where)
            return close_id
        except BinanceAPIException as e:
            print(f"Binance API Exception 발생: {e}")
            return ''
        except BinanceOrderException as e:
            print(f"Binance Order Exception 발생: {e}")
            return ''
        except Exception as e:
            print(f"기타 예외 발생: {e}")
            return ''