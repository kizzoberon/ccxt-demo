import asyncio
import json
import logging
import os

import ccxt.async_support as ccxt
import ccxt.pro as ccxtpro  # 使用ccxt pro

# 确保日志目录存在
log_dir = './log'
os.makedirs(log_dir, exist_ok=True)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('./log/examples.log'),
        logging.StreamHandler()  # 同时保持控制台输出
    ]
)

def test_http():
    proxy_url = 'http://127.0.0.1:7897'
    proxy_settings = {
        'http': proxy_url,
        'https': proxy_url
    }

    exchange = ccxt.binance({
        'proxies': proxy_settings,
    })
    order_book = exchange.fetch_order_book('BTC/USDT', 3)
    # 用漂亮的json格式打印
    print(json.dumps(order_book, indent=4))

async def example_web_sockets():
    my_ex = ccxtpro.gate({
        'options': {
            'verify': False  # 禁用SSL验证
        }
    })
    my_ex.http_proxy = 'http://127.0.0.1:7897/'
    my_ex.ws_proxy = 'http://127.0.0.1:7897/'
    await my_ex.load_markets()
    while True:
        ticker = await my_ex.watch_ticker('BTC/USDT')
        print(ticker)

async def test_ws():
    exchange = ccxtpro.kraken({'newUpdates': False})
    exchange.http_proxy = 'http://127.0.0.1:7897/'
    exchange.ws_proxy = 'http://127.0.0.1:7897/'
    while True:
        orderbook = await exchange.watch_order_book('BTC/USD')
        print(orderbook['asks'][0], orderbook['bids'][0])


if __name__ == '__main__':
    asyncio.run(example_web_sockets())