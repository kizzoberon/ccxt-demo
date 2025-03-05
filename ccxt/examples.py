import logging
import os

import ccxt
import json

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

if __name__ == '__main__':
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
