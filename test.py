import requests
from urllib import parse
import json
from datetime import datetime
import hmac
import base64
from hashlib import sha256
import requests
from urllib import parse
from datetime import datetime
import json
import hmac
import base64
import hashlib
from hashlib import sha256
import json
import urllib.parse
import time


class UrlParamsBuilder(object):

    def __init__(self):
        self.param_map = dict()
        self.post_map = dict()
        self.post_list = list()

    def put_url(self, name, value):
        if value is not None:
            if isinstance(value, (list, dict)):
                self.param_map[name] = value
            else:
                self.param_map[name] = str(value)

    def put_post(self, name, value):
        if value is not None:
            if isinstance(value, (list, dict)):
                self.post_map[name] = value
            else:
                self.post_map[name] = str(value)

    def build_url(self):
        if len(self.param_map) == 0:
            return ""
        encoded_param = urllib.parse.urlencode(self.param_map)
        return "?" + encoded_param

    def build_url_to_json(self):
        return json.dumps(self.param_map)


def _get_url_suffix(method: str, access_key: str, secret_key: str, host: str, path: str, params: dict) -> str:
    # it's utc time and an example is 2017-05-11T15:19:30
    timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
    # timestamp = "2022-10-15T21:05:46"
    # print("method:" + method)
    # print("host:" + host)
    # print("path:" + path)
    # print("access_key:" + access_key)
    # print("secret_key:" + secret_key)
    # print("timestamp:" + timestamp)
    builder = UrlParamsBuilder()
    if params != None and method == "GET":
        for key, value in params.items():
            builder.put_url(key, value)
    builder.put_url("AccessKeyId", access_key)
    builder.put_url("SignatureVersion", "2")
    builder.put_url("SignatureMethod", "HmacSHA256")
    builder.put_url("Timestamp", timestamp)
    # 对参数进行排序: Sort parameters
    # print(builder.param_map.keys())
    keys = sorted(builder.param_map.keys())
    # print("2:", keys)
    # 加入&  insert the "&"
    qs0 = '&'.join(['%s=%s' % (key, parse.quote(builder.param_map[key], safe='')) for key in keys])
    # print("3:", qs0)
    # 请求方法，域名，路径，参数 后加入`\n`  Request method, domain name, path, parameters and add ` \n`
    payload0 = '%s\n%s\n%s\n%s' % (method, host, path, qs0)
    dig = hmac.new(secret_key.encode('utf-8'), msg=payload0.encode('utf-8'), digestmod=hashlib.sha256).digest()
    # 进行base64编码 Base64 encoding
    s = base64.b64encode(dig).decode()
    builder.put_url("Signature", s)
    suffix = builder.build_url()
    return suffix


def get(access_key: str, secret_key: str, host: str, path: str, params: dict) -> json:
    try:
        url = 'https://{}{}{}'.format(host, path, _get_url_suffix(
            'GET', access_key, secret_key, host, path, params))
        headers = {'Content-type': 'application/x-www-form-urlencoded'}
        # params are parts of url path
        print("Full_request_Url:", url)
        data = {"data": "nicai"}
        res = requests.get(url, headers=headers)

        data = res.json()

        return data
    except Exception as e:
        print(e)
    return None


def post(access_key: str, secret_key: str, host: str, path: str, data: dict = None) -> json:
    try:
        url = 'https://{}{}{}'.format(host, path, _get_url_suffix(
            'POST', access_key, secret_key, host, path, None))
        headers = {'Accept': 'application/json',
                   'Content-type': 'application/json'}
        # json means data with json format string in http body
        res = requests.post(url, json=data, headers=headers)
        print(res)
        data = res.json()
        return data
    except Exception as e:
        print(e)
    return None


if __name__ == '__main__':
    # APIkey
    access_key = 'e72c6d95-cef32ed6-d50f56eb-qv2d5ctgbn'
    secret_key = 'f5cee9d2-893f3af0-08f6ba62-dbf31'

    # 4：逐仓获取用户当前未成交委托
    host = 'api.hbdm.com'
    path = '/linear-swap-api/v3/swap_hisorders'
    params = {
        "contract": "MASK-USDT",
        "trade_type": 0,
        "status": 0,
        "type": 1,
        "start_time": 1727284805000,
        "end_time": 1727317205000,
        "direct": "next",
        # "from_id": 1110
    }
    """
    path = '/linear-swap-api/v1/swap_order_info'
    params = {
        "contract_code": "1274902962160443392",
        "order_id": 0
    }
    """

    # print("Response:")
    response = post(access_key, secret_key, host, path, params)
    # print(json.dumps(response, indent=4, ensure_ascii=False))
    print('\nusdt-swap Response:{}\n'.format(json.dumps(response, indent=4, ensure_ascii=False)))
