from binance.client import Client
import utils
from config import connect_db


class BinanceOrderInfo:
    def __init__(self, api_key, secret_key, symbol, idx):
        self.api_key = api_key
        self.secret_key = secret_key
        self.symbol = symbol
        self.idx = idx
        self.client = Client(api_key, secret_key)
        utils.sync_time(self.client)
        self.is_execution = 0

    # 주문 체결 확인
    def check_order_execution(self, order_id):
        try:
            order_info = self.client.futures_get_order(symbol=self.symbol, orderId=order_id)
            if order_info is None:
                return 0
            if order_info['status'] == 'FILLED':
                if self.is_execution == 0:
                    order_data = {
                        'order_money': float(order_info['cumQuote']),
                        'order_position': 1
                    }
                    type_data = {
                        'order_money': 'double',
                        'order_position': 'int'
                    }
                    where = f"order_num='{order_id}' AND symbol='{self.symbol}'"
                    connect_db.setUpdateOrder(order_data, type_data, where)
                    self.is_execution = 1
                return 1
            return 0
        except Exception as e:
            print(f"Binance check_order_execution() error : {e}")
            return 0

    # 주문 청산 확인
    def check_position_liquidation(self, tp_id, sl_id):
        try:
            make_amount = 0.0
            make_profit = 0.0
            make_fee = 0.0
            price = 0.0
            make_id = ''
            update_time = utils.setTimezoneDateTime().strftime("%Y-%m-%d %H:%M:%S")
            current_time = utils.setTimezoneTimestamp()
            prior_time = int(current_time) - 12 * 60 * 60 * 1000
            is_liquidation = False

            all_orders = self.client.futures_account_trades(
                symbol=self.symbol, 
                startTime=prior_time, 
                endTime=current_time, 
                limit=500
            )
            for order in all_orders:
                symbol = order['symbol']
                orderId = order['orderId']
                fee = float(order['commission'])
                price = float(order['price'])
                quoteQty = float(order['quoteQty'])
                profit = float(order['realizedPnl'])
                if symbol == self.symbol and profit != 0:
                    close_id = ''
                    if str(orderId) == str(tp_id):
                        close_id = str(tp_id)
                    if str(orderId) == str(sl_id):
                        close_id = str(sl_id)
                    if close_id != '':
                        make_amount += quoteQty
                        make_profit += profit
                        make_fee += fee
                        make_id = close_id
                        is_liquidation = True
            if is_liquidation:
                order_ids = connect_db.getTradeOrderIds(make_id)
                index = 0
                for orderId in order_ids:
                    if index == 0:
                        order_data = {
                            'make_price': price,
                            'make_money': make_amount,
                            'profit_money': make_profit,
                            'fee_money': make_fee,
                            'make_date': update_time
                        }
                        type_data = {
                            'make_price': 'str',
                            'make_money': 'str',
                            'profit_money': 'str',
                            'fee_money': 'str',
                            'make_date': 'str'
                        }
                    else:
                        order_data = {
                            'make_price': price,
                            'make_money': "OK",
                            'profit_money': "OK",
                            'fee_money': "OK",
                            'make_date': update_time
                        }
                        type_data = {
                            'make_price': 'str',
                            'make_money': 'str',
                            'profit_money': 'str',
                            'fee_money': 'str',
                            'make_date': 'str'
                        }
                    where = f"order_num='{orderId}' AND symbol='{self.symbol}' AND make_date=''"
                    connect_db.setUpdateOrder(order_data, type_data, where)
                    index += 1

                return 1, make_id
            return 0, ''
        except Exception as e:
            print(f"Binance check_position_liquidation() error : {e}")
            return 0, ''
