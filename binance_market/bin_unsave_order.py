from binance.client import Client
import utils
from config import connect_db


def unSavePositionOrders(api_key, secret_key, user_num, unclear_ids):
    try:
        client = Client(api_key, secret_key)
        utils.sync_time(client)
        for id_info in unclear_ids:
            order_symbol = id_info['symbol']
            tp_id = id_info['tp_id']
            sl_id = id_info['sl_id']

            make_amount = 0.0
            make_profit = 0.0
            make_fee = 0.0
            price = 0.0
            make_id = ''
            update_time = utils.setTimezoneDateTime().strftime("%Y-%m-%d %H:%M:%S")
            current_time = utils.setTimezoneTimestamp()
            prior_time = int(current_time) - 24 * 60 * 60 * 1000
            is_liquidation = False

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
                if tp_id != orderId and sl_id != orderId:
                    continue
                if symbol == order_symbol and profit != 0:
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
                    where = f"order_num='{order_id}' AND user_num={user_num} AND symbol='{order_symbol}' AND make_date=''"
                    connect_db.setUpdateOrder(order_data, type_data, where)
    except Exception as e:
        print(f"Binance saveClosePosition() error : {e}")
