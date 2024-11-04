import json
import time

import requests
import urllib3
import config
import utils
from config import connect_db
from huobi_market import htx_url_builder


def unSavePositionOrders(api_key, secret_key, user_num, unclear_ids):
    for id_info in unclear_ids:
        order_symbol = id_info['symbol']
        tp_id = id_info['tp_id']
        sl_id = id_info['sl_id']

        endpoint = config.api_uri.HTX_OrderHistory
        str_symbol = utils.convertSymbolName(order_symbol)
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
            time.sleep(0.3)
            urllib3.disable_warnings()
            # API 호출
            response = htx_url_builder.post(api_key, secret_key, host, endpoint, params)
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
                    order_id = data['order_id_str']
                    if tp_id != order_id and sl_id != order_id:
                        continue
                    if offset.lower() == 'close':
                        price = data(['price'])
                        if price == 0:
                            price = data['trade_avg_price']
                        trade_turnover = float(data['trade_turnover'])
                        real_profit = float(data['real_profit'])
                        fee = float(data['fee'])

                        make_amount += trade_turnover
                        make_profit += real_profit
                        make_fee += fee
                        is_liquidation = True
                if is_liquidation:
                    order_data = {
                        'live_status': 0,
                        'order_position': 2,
                        'make_price': price,
                        'make_money': make_amount,
                        'profit_money': make_profit,
                        'fee_money': make_fee,
                        'make_date': update_time
                    }
                    type_data = {
                        'live_status': 'int',
                        'order_position': 'int',
                        'make_price': 'str',
                        'make_money': 'str',
                        'profit_money': 'str',
                        'fee_money': 'str',
                        'make_date': 'str'
                    }
                    where = f"user_num={user_num} AND tp_id='{tp_id}' AND order_position = 1"
                    connect_db.setUpdateOrder(order_data, type_data, where)
        except Exception as e:
            print(f"HTX unSavePositionOrders error user_num={user_num}, symbol={order_symbol}: {e}")
