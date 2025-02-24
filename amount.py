import base64
import hashlib
import hmac
import json
import time
from datetime import datetime
from urllib.parse import urlencode
import requests
import urllib3

import utils
from config import connect_db


# Huobi 선물 계정 잔고 조회
def getHoubiFutureBalance(api_key, secret_key):
    # 시간 생성
    timestamp = str(datetime.utcnow().isoformat())[0:19]
    params = urlencode({'AccessKeyId': api_key,
                        'SignatureMethod': 'HmacSHA256',
                        'SignatureVersion': '2',
                        'Timestamp': timestamp
                        })
    # 서명 생성
    method = "POST"
    endpoint = '/linear-swap-api/v3/unified_account_info'
    base_uri = 'api.hbdm.com'

    pre_signed_text = method + '\n' + base_uri + '\n' + endpoint + '\n' + params
    hash_code = hmac.new(secret_key.encode(), pre_signed_text.encode(), hashlib.sha256).digest()
    signature = urlencode({'Signature': base64.b64encode(hash_code).decode()})
    url = 'https://' + base_uri + endpoint + '?' + params + '&' + signature
    urllib3.disable_warnings()
    response = requests.request(method, url, verify=False)

    # 응답 처리
    if response.status_code == 200:
        resp = response.json()
        balance = 0
        try:
            if resp['data'] is None:
                balance = 0
            datas = resp['data']
            for data in datas:
                if data['margin_asset'] == 'USDT':
                    balance = data['margin_balance']
                    break
            return balance
        except Exception as e:
            print(e)
            return 0
    else:
        print("Failed to url '/linear-swap-api/v3/unified_account_info' :", response.text)
        return 0


# Binance 선물 계정 잔고 조회
def getBinanceFutureBalance(api_key, secret_key):
    headers = {
        'X-MBX-APIKEY': api_key
    }
    base_url = 'https://fapi.binance.com'
    endpoint = '/fapi/v2/balance'
    url = base_url + endpoint

    # 서명에 포함될 쿼리스트링 생성
    query_string = urlencode({
        'timestamp': int(time.time() * 1000)
    })
    # 서명 생성
    signature = hmac.new(secret_key.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()

    # 서명 및 요청 시간 추가
    query_string += f'&signature={signature}'

    urllib3.disable_warnings()
    # 요청 보내기
    response = requests.get(url + '?' + query_string, headers=headers, verify=False)
    # 응답 처리
    if response.status_code == 200:
        datas = response.json()
        balance = 0
        try:
            if len(datas) == 0:
                balance = 0
            for data in datas:
                if data['asset'] == 'USDT':
                    balance = data['balance']
                    break
        except Exception as e:
            print(e)
        return balance
    else:
        print('amount.py Failed to binance balance:', response.text)
        return 0


def getAccountType(api_key, secret_key):
    # 시간 생성
    timestamp = str(datetime.utcnow().isoformat())[0:19]
    params = urlencode({'AccessKeyId': api_key,
                        'SignatureMethod': 'HmacSHA256',
                        'SignatureVersion': '2',
                        'Timestamp': timestamp
                        })
    # 서명 생성
    method = "POST"
    endpoint = '/linear-swap-api/v3/swap_unified_account_type'
    base_uri = 'api.hbdm.com'

    pre_signed_text = method + '\n' + base_uri + '\n' + endpoint + '\n' + params
    hash_code = hmac.new(secret_key.encode(), pre_signed_text.encode(), hashlib.sha256).digest()
    signature = urlencode({'Signature': base64.b64encode(hash_code).decode()})
    url = 'https://' + base_uri + endpoint + '?' + params + '&' + signature
    urllib3.disable_warnings()
    response = requests.request(method, url, verify=False)

    # 응답 처리
    if response.status_code == 200:
        resp = response.json()
        try:
            if resp['code'] == 200:
                data = resp['data']
                account_type = data['account_type']
                return account_type
        except Exception as e:
            print(e)
            return 0
    else:
        print("Failed to url '/linear-swap-api/v3/unified_account_info' :", response.text)
        return 0


def setAccountType(api_key, secret_key):
    # 시간 생성
    timestamp = str(datetime.utcnow().isoformat())[0:19]
    params = urlencode({'AccessKeyId': api_key,
                        'SignatureMethod': 'HmacSHA256',
                        'SignatureVersion': '2',
                        'Timestamp': timestamp
                        })
    # 서명 생성
    method = "POST"
    endpoint = '/linear-swap-api/v3/swap_switch_account_type'
    base_uri = 'api.hbdm.com'

    pre_signed_text = method + '\n' + base_uri + '\n' + endpoint + '\n' + params
    hash_code = hmac.new(secret_key.encode(), pre_signed_text.encode(), hashlib.sha256).digest()
    signature = urlencode({'Signature': base64.b64encode(hash_code).decode()})
    url = 'https://' + base_uri + endpoint + '?' + params + '&' + signature

    datas = {
        "account_type": 2
    }
    body = json.dumps(datas, separators=(',', ':'))
    headers = {
        'Content-Type': 'application/json',
    }

    urllib3.disable_warnings()
    response = requests.request(method, url, headers=headers, data=body, verify=False)

    # 응답 처리
    if response.status_code == 200:
        resp = response.json()
        try:
            if resp['code'] == 200:
                data = resp['data']
                account_type = data['account_type']
                return account_type
        except Exception as e:
            print(e)
            return 0
    else:
        print("Failed to url '/linear-swap-api/v3/unified_account_info' :", response.text)
        return 0


def getUserAmount():
    keys = connect_db.getApiKeys()
    for key in keys:
        total_amount = 0
        if key['market'] == 'htx':
            account_type = getAccountType(key['api_key'], key['secret_key'])
            if account_type is None:
                continue
            if account_type > 0 and account_type == 1:
                setAccountType(key['api_key'], key['secret_key'])
            total_amount = getHoubiFutureBalance(key['api_key'], key['secret_key'])
        # else:
        #    total_amount = getBinanceFutureBalance(key['api_key'], key['secret_key'])
        connect_db.setUsersAmount(key['user_num'], key['market'], utils.getRoundDotDigit(float(total_amount), 2), True)
        time.sleep(0.5)


def main():
    while True:
        getUserAmount()
        time.sleep(60)


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    main()
