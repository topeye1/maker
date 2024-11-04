import hashlib
import hmac
import time
import requests
from urllib.parse import urlencode

import urllib3

import config.api_uri


def getBinanceFutureBalance(api_key, secret_key):
    headers = {
        'X-MBX-APIKEY': api_key
    }
    base_url = config.api_uri.BIN_Uri
    endpoint = config.api_uri.BIN_Balance
    url = base_url + endpoint

    query_string = urlencode({
        'timestamp': int(time.time() * 1000)
    })
    signature = hmac.new(secret_key.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()

    query_string += f'&signature={signature}'

    urllib3.disable_warnings()
    response = requests.get(url + '?' + query_string, headers=headers, verify=False)

    balance = 0
    if response.status_code == 200:
        datas = response.json()
        if len(datas) == 0:
            return balance
        for data in datas:
            if data['asset'] == 'USDT':
                balance = data['balance']
                break
        return balance
    else:
        print('bin_balance.py Failed to binance balance:', response.text)
        return 0
