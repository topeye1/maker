import json
import requests
import urllib3
import config
import utils
from config import connect_db


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
