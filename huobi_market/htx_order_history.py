import urllib3
import config
import utils
from config import connect_db
from huobi_market import htx_url_builder


class HuobiOrderHistory:
    def __init__(self, api_key, secret_key, symbol):
        self.api_key = api_key
        self.secret_key = secret_key
        self.symbol = symbol

    def getHuobiOrderHistory(self, order_id, user_num, tp, sl, side):
        endpoint = config.api_uri.HTX_OrderHistory
        str_symbol = utils.convertSymbolName(self.symbol)
        current_time = utils.setTimezoneTimestamp()
        start_time = int(current_time) - 45 * 60 * 60 * 1000
        end_time = int(current_time) + 60 * 60 * 1000

        host = config.api_uri.HTX_Uri
        # 파라미터 설정
        params = {
            "contract": f'{str_symbol}',
            "trade_type": 0,
            "status": 0,
            "type": 2,
            "start_time": start_time,
            "end_time": end_time,
            "direct": "prev",
        }

        try:
            urllib3.disable_warnings()
            # API 호출
            response = htx_url_builder.post(self.api_key, self.secret_key, host, endpoint, params)
            if response['code'] == 200:
                res_data = response['data']
                if res_data is None or len(res_data) == 0:
                    return 'open', ''
                _offset = 'open'
                close_order_id = ''
                index = 0

                for data in res_data:
                    offset = data['offset']
                    direction = data['direction']
                    price = data['price']
                    order_source = data['order_source']
                    # if price == 0:
                    #    price = data['trade_avg_price']
                    if offset.lower() == 'open' or float(price) == 0 or direction.lower() != side.lower():
                        continue
                    make_money = utils.getRoundDotDigit(data['trade_turnover'], 6)
                    profit = utils.getRoundDotDigit(data['profit'], 6)
                    if profit == 0:
                        profit = utils.getRoundDotDigit(data['real_profit'], 6)

                    fee = utils.getRoundDotDigit(data['fee'], 6)
                    update_time = utils.setTimezoneDateTime().strftime("%Y-%m-%d %H:%M:%S")
                    symbol = data['symbol']

                    s_times = update_time.split(':')
                    split_time = s_times[0]

                    is_matching = False
                    delta_tp = abs(float(tp) - float(price))
                    delta_sl = abs(float(sl) - float(price))
                    if delta_tp <= 0.000001 or delta_sl <= 0.000001:
                        is_matching = True
                    elif tp == price or sl == price:
                        is_matching = True
                    elif str(tp) == str(price) or str(sl) == str(price):
                        is_matching = True
                    if index == 0 and order_source == 'risk':
                        if side == 'sell':
                            if price >= tp or price <= sl:
                                is_matching = True
                        else:
                            if price >= sl or price <= tp:
                                is_matching = True
                    if is_matching is True:
                        if abs(float(profit)) < 0.000001:
                            close_order_id = str(data['order_id'])
                            order_data = {
                                'tp_id': f"{close_order_id}",
                                'sl_id': f"{close_order_id}"
                            }
                            type_data = {
                                'tp_id': 'str',
                                'sl_id': 'str'
                            }
                            where = f"order_num='{order_id}' AND user_num={user_num} AND symbol LIKE'{symbol}%' AND make_date=''"
                            connect_db.setUpdateOrder(order_data, type_data, where)
                        else:
                            order_data = {
                                'order_position': 2,
                                'make_price': price,
                                'make_money': make_money,
                                'profit_money': profit,
                                'fee_money': fee,
                                'make_date': update_time
                            }
                            type_data = {
                                'order_position': 'int',
                                'make_price': 'str',
                                'make_money': 'str',
                                'profit_money': 'str',
                                'fee_money': 'str',
                                'make_date': 'str'
                            }
                            where = f"order_num='{order_id}' AND user_num={user_num} AND symbol LIKE'{symbol}%' AND make_date=''"
                            res = connect_db.setUpdateOrder(order_data, type_data, where, user_num, symbol, 'htx', price, profit, split_time)
                            if res > 0:
                                _offset = 'close'
                                break
                    index += 1
                return _offset, close_order_id
            else:
                return '', ''
        except Exception as e:
            print(f"HTX get_order_history error {user_num} {self.symbol}: {e}")
            return '', ''

    def getHuobiOrderIDHistory(self, user_num, close_order_id, current_time):
        endpoint = config.api_uri.HTX_OrderHistory
        str_symbol = utils.convertSymbolName(self.symbol)
        start_time = int(current_time) - 2 * 60 * 60 * 1000
        end_time = int(current_time) + 42 * 60 * 60 * 1000

        host = config.api_uri.HTX_Uri
        # 파라미터 설정
        params = {
            "contract": f'{str_symbol}',
            "trade_type": 0,
            "status": 0,
            "type": 2,
            "start_time": start_time,
            "end_time": end_time,
            "direct": "prev",
        }

        try:
            urllib3.disable_warnings()
            # API 호출
            response = htx_url_builder.post(self.api_key, self.secret_key, host, endpoint, params)
            if response['code'] == 200:
                res_data = response['data']
                if res_data is None or len(res_data) == 0:
                    return 'open'
                _offset = 'open'
                status = 0
                for data in res_data:
                    status = data['status']
                    offset = data['offset']
                    price = data['price']
                    order_id = data['order_id']
                    if offset.lower() == 'open' or status < 6:
                        continue
                    make_money = utils.getRoundDotDigit(data['trade_turnover'], 6)
                    profit = utils.getRoundDotDigit(data['profit'], 6)
                    if profit == 0:
                        profit = utils.getRoundDotDigit(data['real_profit'], 6)

                    fee = utils.getRoundDotDigit(data['fee'], 6)
                    update_time = utils.setTimezoneDateTime().strftime("%Y-%m-%d %H:%M:%S")
                    symbol = data['symbol']

                    s_times = update_time.split(':')
                    split_time = s_times[0]

                    is_matching = False

                    if str(close_order_id) == str(order_id):
                        is_matching = True
                    if is_matching is True:
                        if status == 7:
                            break
                        else:
                            order_data = {
                                'order_position': 2,
                                'make_price': price,
                                'make_money': make_money,
                                'profit_money': profit,
                                'fee_money': fee,
                                'make_date': update_time
                            }
                            type_data = {
                                'order_position': 'int',
                                'make_price': 'str',
                                'make_money': 'str',
                                'profit_money': 'str',
                                'fee_money': 'str',
                                'make_date': 'str'
                            }
                            where = f"tp_id='{close_order_id}' AND user_num={user_num} AND symbol LIKE'{symbol}%' AND make_date=''"
                            res = connect_db.setUpdateOrder(order_data, type_data, where, user_num, symbol, 'htx', price, profit, split_time)
                            if res > 0:
                                _offset = 'close'
                                break
                return _offset, status
            else:
                return '', 0
        except Exception as e:
            print(f"HTX getHuobiOrderIDHistory error {user_num} {self.symbol} : {e}")
            return '', 0

    def getHuobiOrderRiskHistory(self, user_num, close_order_id):
        endpoint = config.api_uri.HTX_OrderHistory
        str_symbol = utils.convertSymbolName(self.symbol)
        current_time = utils.setTimezoneTimestamp()
        start_time = int(current_time) - 2 * 60 * 60 * 1000
        end_time = int(current_time) + 60 * 60 * 1000

        host = config.api_uri.HTX_Uri
        # 파라미터 설정
        params = {
            "contract": f'{str_symbol}',
            "trade_type": 0,
            "status": 0,
            "type": 2,
            "start_time": start_time,
            "end_time": end_time,
            "direct": "prev",
        }

        try:
            urllib3.disable_warnings()
            # API 호출
            response = htx_url_builder.post(self.api_key, self.secret_key, host, endpoint, params)
            if response['code'] == 200:
                res_data = response['data']
                if res_data is None or len(res_data) == 0:
                    return 'open'
                _offset = 'open'
                data = res_data[0]
                order_source = data['order_source']
                offset = data['offset']
                if offset == 'close' and order_source == 'risk':
                    price = data['price']
                    order_id = data['order_id']
                    make_money = utils.getRoundDotDigit(data['trade_turnover'], 6)
                    profit = utils.getRoundDotDigit(data['profit'], 6)
                    if profit == 0:
                        profit = utils.getRoundDotDigit(data['real_profit'], 6)

                    fee = utils.getRoundDotDigit(data['fee'], 6)
                    update_time = utils.setTimezoneDateTime().strftime("%Y-%m-%d %H:%M:%S")
                    symbol = data['symbol']

                    s_times = update_time.split(':')
                    split_time = s_times[0]

                    order_data = {
                        'tp_id': f"{order_id}",
                        'sl_id': f"{order_id}",
                        'order_position': 2,
                        'make_price': price,
                        'make_money': make_money,
                        'profit_money': profit,
                        'fee_money': fee,
                        'make_date': update_time
                    }
                    type_data = {
                        'tp_id': 'str',
                        'sl_id': 'str',
                        'order_position': 'int',
                        'make_price': 'str',
                        'make_money': 'str',
                        'profit_money': 'str',
                        'fee_money': 'str',
                        'make_date': 'str'
                    }
                    where = f"tp_id='{close_order_id}' AND user_num={user_num} AND symbol LIKE'{symbol}%' AND make_date=''"
                    res = connect_db.setUpdateOrder(order_data, type_data, where, user_num, symbol, 'htx', price, profit, split_time)
                    if res > 0:
                        _offset = 'close'
                return _offset
            else:
                return ''
        except Exception as e:
            print(f"HTX getHuobiOrderRiskHistory error {user_num} {self.symbol} : {e}")
            return ''
