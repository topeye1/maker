import json
import time
import requests
import urllib3
import config
import utils
from config import connect_db


class HuobiOrderInfo:
    def __init__(self, api_key, secret_key, symbol):
        self.api_key = api_key
        self.secret_key = secret_key
        self.symbol = symbol
        self.is_create = 0

    def onCheckOrderInfo(self, order_id, user_num):
        method = "POST"
        endpoint = config.api_uri.HTX_OrderInfo
        API_URL = config.api_uri.setPostApiUrl(self.api_key, self.secret_key, method, endpoint)

        str_symbol = utils.convertSymbolName(self.symbol)
        # 파라미터 설정
        datas = {
            "order_id": f'{order_id}',
            "contract_code": f'{str_symbol}',
            "client_order_id": f'{order_id}'
        }

        body = json.dumps(datas, separators=(',', ':'))
        headers = {
            'Content-Type': 'application/json',
        }
        try:
            time.sleep(1)
            urllib3.disable_warnings()
            # API 호출
            response = requests.request(method, API_URL, headers=headers, data=body, verify=False)
            if response.status_code == 200:
                resp = response.json()
                if resp['status'] == 'error':
                    return 0
                if resp['data'] is None or resp['data'] == '':
                    return 0
                data = resp['data'][0]
                if resp['status'] == 'ok' and str(data['order_id_str']) == str(order_id):
                    status = data['status']
                    price = data['price']
                    fee = data['fee']
                    order_money = data['trade_turnover']
                    if price == 0:
                        price = data['trade_avg_price']
                    if status == 4 or status == 6:  # 주문이 체결 된 상태
                        order_data = {
                            'order_money': order_money,
                            'order_price': price,
                            'tp_id': order_id,
                            'sl_id': order_id,
                            'fee_money': fee,
                            'order_position': 1,
                            'pos_date': utils.setTimezoneDateTime().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        type_data = {
                            'order_money': 'double',
                            'order_price': 'double',
                            'tp_id': 'str',
                            'sl_id': 'str',
                            'fee_money': 'str',
                            'order_position': 'int',
                            'pos_date': 'str'
                        }
                        where = f"user_num={user_num} AND order_num='{order_id}' AND symbol='{self.symbol}'"
                        connect_db.setUpdateOrder(order_data, type_data, where)
                    return price, order_money
            return 0, 0
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            return 0, 0
        except Exception as e:
            print(f"HTX onCheckOrderInfo error : {e}")
            return 0, 0

    def onKeep_TPSL_Price(self, order_id, user_num, tp, sl):
        order_data = {
            'tp_price': tp,
            'sl_price': sl,
        }
        type_data = {
            'tp_price': 'double',
            'sl_price': 'double',
        }
        where = f"user_num={user_num} AND order_num='{order_id}' AND symbol='{self.symbol}'"
        connect_db.setUpdateOrder(order_data, type_data, where)
