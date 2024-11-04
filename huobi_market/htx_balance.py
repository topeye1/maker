import base64
import hashlib
import hmac
import requests
from datetime import datetime
from urllib.parse import urlencode

import urllib3

import config.api_uri


def getHuobiFutureBalance(api_key, secret_key):
    # 시간 생성
    timestamp = str(datetime.utcnow().isoformat())[0:19]
    params = urlencode({'AccessKeyId': api_key,
                        'SignatureMethod': 'HmacSHA256',
                        'SignatureVersion': '2',
                        'Timestamp': timestamp
                        })
    # 서명 생성
    method = "POST"
    endpoint = config.api_uri.HTX_Balance
    base_uri = config.api_uri.HTX_Uri

    pre_signed_text = method + '\n' + base_uri + '\n' + endpoint + '\n' + params
    hash_code = hmac.new(secret_key.encode(), pre_signed_text.encode(), hashlib.sha256).digest()
    signature = urlencode({'Signature': base64.b64encode(hash_code).decode()})
    url = 'https://' + base_uri + endpoint + '?' + params + '&' + signature
    urllib3.disable_warnings()
    response = requests.request(method, url, verify=False)

    balance = 0
    # 응답 처리
    if response.status_code == 200:
        resp = response.json()
        if resp['data'] is None:
            return balance
        datas = resp['data']
        for data in datas:
            if data['margin_asset'] == 'USDT':
                balance = data['margin_balance']
                break
        return balance
    else:
        print("Failed to url '/linear-swap-api/v3/unified_account_info':", response.text)
        return None
