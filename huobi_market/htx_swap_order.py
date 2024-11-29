import json

import requests
import urllib3

import config
import utils
from config import connect_db


class TradeSwapOrder:
    def __init__(self, api_key, secret_key, symbol, user_num, coin_num, dot_digit, min_digit):
        self.api_key = api_key
        self.secret_key = secret_key
        self.symbol = symbol
        self.user_num = user_num
        self.coin_num = coin_num
        self.dot_digit = dot_digit
        self.min_digit = min_digit
        self.order_volume = 0

    def onTradingSwapOrder(self, direction, idx, balance, amount, c_price, lever_rate, bet_limit, price, tp_price, sl_price, rate_rev, rate_liq, brokerID, coin_num=1):
        method = "POST"
        endpoint = config.api_uri.HTX_Order
        API_URL = config.api_uri.setPostApiUrl(self.api_key, self.secret_key, method, endpoint)

        volume = (amount / float(c_price)) / self.min_digit
        self.order_volume = int(volume)
        str_symbol = utils.convertSymbolName(self.symbol)
        order_price = utils.getRoundDotDigit(price, self.dot_digit)
        tp = utils.getRoundDotDigit(tp_price, self.dot_digit)
        sl = utils.getRoundDotDigit(sl_price, self.dot_digit)
        order_datetime = utils.setTimezoneDateTime().strftime("%Y-%m-%d %H:%M:%S")
        # 파라미터 설정
        if idx <= 3:
            # 정상 상태 주문 파라미터
            datas = {
                "contract_code": f'{str_symbol}',
                "direction": direction,
                "offset": "open",
                "price": order_price,
                "lever_rate": lever_rate,
                "volume": self.order_volume,
                "order_price_type": "limit",
                "tp_trigger_price": tp,
                "tp_order_price": tp,
                "tp_order_price_type": "limit",
                # "sl_trigger_price": f"{sl}",
                # "sl_order_price": f"{sl}",
                # "sl_order_price_type": "limit",
                "channel_code": f"{brokerID}"
            }
        else:
            # 홀딩 상태 주문 파라미터
            datas = {
                "contract_code": f'{str_symbol}',
                "direction": direction,
                "offset": "open",
                "price": order_price,
                "lever_rate": lever_rate,
                "volume": self.order_volume,
                "order_price_type": "limit",
                "channel_code": f"{brokerID}"
            }

        body = json.dumps(datas, separators=(',', ':'))
        headers = {
            'Content-Type': 'application/json',
        }
        # 같은 시간에 주문 된 것이 있는지 확인
        order_cnt = connect_db.checkDoubleOrder(self.user_num, 'htx', self.symbol, order_price, order_datetime)
        if order_cnt > 0:
            return False, '', 0, 0

        try:
            urllib3.disable_warnings()
            # API 호출
            response = requests.request(method, API_URL, headers=headers, data=body, verify=False)
            if response.status_code == 200:
                resp = response.json()
                if resp['status'] == "ok":
                    data = resp['data']
                    # order_id = data['order_id']
                    order_id_str = data['order_id_str']
                    order_data = {
                        'user_num': self.user_num,
                        'order_num': order_id_str,
                        'side': direction,
                        'idx': idx,
                        'coin_num': self.coin_num,
                        'symbol': self.symbol,
                        'market': 'htx',
                        'live_status': 1,
                        'order_position': 0,
                        'hold_money': balance,
                        'leverage': lever_rate,
                        'bet_limit': bet_limit,
                        'rate_rev': rate_rev,
                        'rate_liq': rate_liq,
                        'order_volume': self.order_volume,
                        'order_price': order_price,
                        'tp_price': tp,
                        # 'sl_price': sl,
                        'order_date': order_datetime
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
                        'order_price': 'double',
                        'tp_price': 'double',
                        # 'sl_price': 'double',
                        'order_date': 'str'
                    }

                    connect_db.setTradeOrder(order_data, type_data)
                    if idx > 3:
                        connect_db.setOrderHoldingStatus(self.user_num, coin_num, 'htx', 1)
                    return True, order_id_str, tp, sl
                else:
                    print(f"Error response : ' {self.user_num} {self.symbol} : {response.text}")
                    return False, '', 0, 0
            else:
                print(f"Failed to url '/linear-swap-api/v1/swap_order : ' {self.user_num} {self.symbol} : {response.text}")
                return False, '', 0, 0
        except Exception as e:
            print(f"HTX onTradingSwapOrder error : {e}")
            return False, '', 0, 0
