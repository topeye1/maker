from datetime import datetime, timedelta, timezone

import pytz

live_symbols_info = []
stop_htx_info = []
stop_bin_info = []
min_max_pro = [
    0.1,
    0.2,
    0.3,
    0.4,
    0.5,
    0.6,
    0.7,
    0.8,
    0.9,
    1.0,
    1.1,
    1.2,
    1.3,
    1.4,
    1.5,
    1.6,
    1.7,
    1.8,
    1.9,
    2.0,
    2.1,
    2.2,
    2.3,
    2.4,
    2.5,
    2.6,
    2.7,
    2.8,
    2.9,
    3.0,
]
min_max_val = [
    -0.06,
    -0.045,
    -0.030,
    -0.015,
    0.0,
    0.05,
    0.1,
    0.15,
    0.2,
    0.25,
    0.3,
    0.35,
    0.4,
    0.45,
    0.5,
    0.55,
    0.6,
    0.65,
    0.7,
    0.75,
    0.8,
    0.85,
    0.9,
    0.95,
    1.0,
    1.05,
    1.1,
    1.15,
    1.2,
    1.25,
]


def getRedisCurrentPriceKey(market, symbol):
    key_name = market.upper() + "_" + symbol.upper()
    return key_name


def getRedisMiddlePriceKey(market, symbol):
    key_name = "MA_" + market.upper() + "_" + symbol.upper()
    return key_name


def convertSymbolName(symbol):
    sval = symbol.replace('USDT', '-USDT')
    return sval


def getRoundDotDigit(val, digit):
    number = round(val, digit)
    if digit == 0:
        number = int(number)
    return number


def filterData(vals1, vals2, param1, param2):
    for val in vals1:
        if val[param1] == vals2[param1] and val[param2] == vals2[param2]:
            return False
        else:
            return True


def setCurrentTimezoneTimestamp():
    now_time = datetime.now()
    # Shanghai Timezone
    time_zone = timezone(timedelta(hours=8))
    shanghai_time = datetime(now_time.year, now_time.month, now_time.day, now_time.hour, now_time.minute, now_time.second, tzinfo=time_zone)
    timestamp = int(round(shanghai_time.timestamp() * 1000))
    return timestamp


def setTimezoneTimestamp():
    # Server Timezone
    utc_now = datetime.utcnow()
    # Shanghai Timezone
    shanghai_timezone = pytz.timezone('Asia/Shanghai')
    shanghai_time = utc_now.replace(tzinfo=pytz.utc).astimezone(shanghai_timezone)

    timestamp = int(round(shanghai_time.timestamp() * 1000))
    return timestamp


def setTimezoneDateTime():
    # Server Timezone
    utc_now = datetime.utcnow()
    # Shanghai Timezone.
    shanghai_timezone = pytz.timezone('Asia/Shanghai')
    date_time = utc_now.replace(tzinfo=pytz.utc).astimezone(shanghai_timezone)
    return date_time


def convertTimestampToDatetime(timestamp):
    utc_now = datetime.fromtimestamp(timestamp / 1000)
    shanghai_timezone = pytz.timezone('Asia/Shanghai')
    date_time = utc_now.replace(tzinfo=pytz.utc).astimezone(shanghai_timezone)
    return date_time


def getTimezoneToDay():
    utc_now = datetime.utcnow()
    shanghai_timezone = pytz.timezone('Asia/Shanghai')
    date_time = utc_now.replace(tzinfo=pytz.utc).astimezone(shanghai_timezone)
    return date_time.strftime('%Y-%m-%d')


def getTimezoneYesterDay():
    utc_now = datetime.utcnow()
    shanghai_timezone = pytz.timezone('Asia/Shanghai')
    date_time = utc_now.replace(tzinfo=pytz.utc).astimezone(shanghai_timezone)
    yesterday = date_time - timedelta(days=1)
    return yesterday.strftime('%Y-%m-%d')


def sync_time(client):
    server_time = client.get_server_time()
    client_time = setTimezoneTimestamp()
    time_diff = server_time['serverTime'] - client_time
    client.timestamp_offset = time_diff


def getCurrentMinMaxProValue(max_price, min_price, c_price):
    delta = max_price - min_price
    c_pro = (delta / c_price) * 100
    for i in range(0, len(min_max_pro)):
        if c_pro <= min_max_pro[0]:
            return min_max_val[0]
        if i > 0:
            p = i - 1
            if min_max_pro[p] < c_pro <= min_max_pro[i]:
                return min_max_val[i]
    return 0
