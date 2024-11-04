import json
import requests
import urllib3
import config
import utils
from config import connect_db
from huobi_market import htx_url_builder


class CancelOrder:
    def __init__(self, api_key, secret_key, user_num):
        self.api_key = api_key
        self.secret_key = secret_key
        self.user_num = user_num

    def onCancelOrder(self, order_id, symbol, bSub=False):
        method = "POST"
        endpoint = config.api_uri.HTX_CancelOrder
        API_URL = config.api_uri.setPostApiUrl(self.api_key, self.secret_key, method, endpoint)

        str_symbol = utils.convertSymbolName(symbol)
        # 파라미터 설정
        datas = {
            "contract_code": f'{str_symbol}',
            "order_id": order_id
        }

        body = json.dumps(datas, separators=(',', ':'))
        headers = {
            'Content-Type': 'application/json',
        }

        urllib3.disable_warnings()
        # API 호출
        response = requests.request(method, API_URL, headers=headers, data=body, verify=False)
        if response.status_code == 200:
            resp = response.json()
            if resp['status'] == "ok":
                data = resp['data']
                successes = data['successes']
                if successes == '':
                    return False
                else:
                    if bSub is False:
                        connect_db.delCancelOrder(self.user_num, order_id)
                    return True
            else:
                return False
        else:
            print("Failed to url '/linear-swap-api/v1/swap_cancel' :", response.text)
            return False

    def onCancelAllTrade(self, symbol, market):
        method = "POST"
        endpoint = config.api_uri.HTX_CancelAllOrder
        API_URL = config.api_uri.setPostApiUrl(self.api_key, self.secret_key, method, endpoint)

        str_symbol = utils.convertSymbolName(symbol)
        # 파라미터 설정
        datas = {
            "contract_code": f'{str_symbol}'
        }

        body = json.dumps(datas, separators=(',', ':'))
        headers = {
            'Content-Type': 'application/json',
        }

        urllib3.disable_warnings()
        # API 호출
        response = requests.request(method, API_URL, headers=headers, data=body, verify=False)
        if response.status_code == 200:
            resp = response.json()
            if resp['status'] == "ok":
                connect_db.delAllCancelOrder(symbol, self.user_num, market)
                return True
            else:
                return False
        else:
            print(f"Failed to huobi onCancelAllTrade {self.user_num}, {symbol} : {response.text}")
            return False

    def onClosePositionOrder(self, user_num, symbol, direction, ids):
        if direction == 'sell':
            side = 'buy'
        else:
            side = 'sell'

        method = "POST"
        endpoint = config.api_uri.HTX_ClosePosition
        API_URL = config.api_uri.setPostApiUrl(self.api_key, self.secret_key, method, endpoint)

        str_symbol = utils.convertSymbolName(symbol)
        timestamp = utils.setTimezoneTimestamp()
        # 파라미터 설정
        datas = {
            "contract_code": f'{str_symbol}',
            "direction": side,
            "client_order_id": timestamp,
            "order_price_type": 'market',
        }

        body = json.dumps(datas, separators=(',', ':'))
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }

        urllib3.disable_warnings()
        # API 호출
        response = requests.request(method, API_URL, headers=headers, data=body, verify=False)
        if response.status_code == 200:
            resp = response.json()
            if resp['status'] == "ok":
                order_id = resp['data']['order_id_str']
                order_data = {
                    'tp_id': order_id,
                    'sl_id': order_id
                }
                type_data = {
                    'tp_id': 'str',
                    'sl_id': 'str'
                }
                where = f"user_num={user_num} AND symbol='{symbol}' AND "
                if len(ids) > 0:
                    where += f"("
                    i = 0
                    for o_id in ids:
                        if i == 0:
                            where += f"order_num='{o_id}' "
                        else:
                            where += f" OR order_num='{o_id}'"
                        i += 1
                    where += f") AND "
                where += f"side='{direction}' AND make_date=''"
                connect_db.setUpdateOrder(order_data, type_data, where)
                return order_id
            else:
                return ''
        else:
            print(f"Failed to huobi close position {self.user_num}, {symbol} : {response.text}")
            return ''

    def closeAllOrderHistory(self, user_num, symbol, order_id, close_id, b_closed=False):
        endpoint = config.api_uri.HTX_OrderHistory
        str_symbol = utils.convertSymbolName(symbol)
        current_time = utils.setTimezoneTimestamp()
        start_time = int(current_time) - 40 * 60 * 60 * 1000
        end_time = int(current_time) + 60 * 60 * 1000
        is_liquidation = False

        host = config.api_uri.HTX_Uri
        # 파라미터 설정
        params = {
            "contract": f'{str_symbol}',
            "trade_type": 0,
            "status": 0,
            "type": 1,
            "start_time": start_time,
            "end_time": end_time,
            "direct": "prev",
        }

        try:
            urllib3.disable_warnings()
            # API 호출
            response = htx_url_builder.post(self.api_key, self.secret_key, host, endpoint, params)
            if response['code'] == 200:
                make_amount = 0.0
                make_profit = 0.0
                make_fee = 0.0
                price = 0.0
                update_time = utils.setTimezoneDateTime().strftime("%Y-%m-%d %H:%M:%S")
                res_data = response['data']
                if res_data is None or len(res_data) == 0:
                    return 0
                for data in res_data:
                    offset = data['offset']
                    order_id_str = data['order_id_str']

                    if offset == 'close' and str(close_id) == str(order_id_str):
                        price = data['price']
                        if price == 0:
                            price = float(data['trade_avg_price'])
                        trade_turnover = float(data['trade_turnover'])
                        real_profit = float(data['real_profit'])
                        fee = float(data['fee'])

                        make_amount += trade_turnover
                        make_profit += real_profit
                        make_fee += fee
                        is_liquidation = True
                if is_liquidation:
                    order_data = {
                        'order_position': 2,
                        'make_price': price,
                        'make_money': make_amount,
                        'profit_money': make_profit,
                        'fee_money': make_fee,
                        'make_date': update_time
                    }
                    if b_closed:
                        order_data = {
                            'order_position': 2,
                            'make_price': price,
                            'make_money': "OK",
                            'profit_money': "OK",
                            'fee_money': "OK",
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
                    where = f"user_num={user_num} AND (order_num='{order_id}' AND tp_id='{close_id}')"
                    connect_db.setUpdateOrder(order_data, type_data, where)
                    return 1
            return 0
        except Exception as e:
            print(f"HTX closeAllOrderHistory error {user_num}, {symbol}: {e}")
            return 0
