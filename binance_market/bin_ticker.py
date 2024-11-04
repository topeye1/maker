from binance.client import Client


def getTickerPrice(api_key, secret_key, symbol):
    client = Client(api_key, secret_key)
    ticker = client.get_ticker(symbol=symbol)
    high_price = 0
    low_price = 0
    open_price = 0
    if ticker:
        high_price = ticker['highPrice']
        low_price = ticker['lowPrice']
        open_price = ticker['openPrice']
    return high_price, low_price, open_price
