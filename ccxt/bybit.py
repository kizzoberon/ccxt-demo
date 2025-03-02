import ccxt
import time
from datetime import datetime
import pandas as pd
from requests.exceptions import RequestException
import logging

def setup_logger():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

def get_bybit_price_diff():
    # 初始化日志
    logger = setup_logger()

    # 配置代理设置
    proxies = {
        'http': 'http://127.0.0.1:7897',  # 根据你的实际代理端口修改
        'https': 'http://127.0.0.1:7897'  # 根据你的实际代理端口修改
    }
    
    # 初始化ByBit交易所
    exchange = ccxt.bybit({
        'enableRateLimit': True,  # 启用请求频率限制
        'timeout': 10000,  # 设置超时时间为30秒
        'proxies': proxies,  # 添加代理配置
        'options': {
            'verify': False  # 如果遇到SSL证书问题，可以禁用验证
        }
    })
    
    # 设置重试次数
    max_retries = 3
    
    while True:
        retry_count = 0
        while retry_count < max_retries:
            try:
                # 获取所有交易对的最新行情
                tickers = exchange.fetch_tickers()
                
                # 存储现货和合约的价格
                spot_prices = {}
                perp_prices = {}
                
                # 遍历所有交易对
                for symbol, ticker in tickers.items():
                    if ticker['last'] is None:  # 跳过没有最新价格的交易对
                        continue
                        
                    # 区分现货和合约
                    if 'SPOT' in symbol:
                        base = symbol.replace('SPOT', '').replace('USDT', '')
                        spot_prices[base] = {
                            'price': ticker['last'],
                            'symbol': symbol
                        }
                    elif 'PERP' in symbol:
                        base = symbol.replace('PERP', '').replace('USDT', '')
                        perp_prices[base] = {
                            'price': ticker['last'],
                            'symbol': symbol
                        }
                
                # 找出同时存在于现货和合约的币对
                common_pairs = set(spot_prices.keys()) & set(perp_prices.keys())
                
                # 获取当前时间
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # 输出价格差
                for pair in common_pairs:
                    spot_symbol = spot_prices[pair]['symbol']
                    perp_symbol = perp_prices[pair]['symbol']
                    spot_price = spot_prices[pair]['price']
                    perp_price = perp_prices[pair]['price']
                    
                    print(f"{spot_symbol} {perp_symbol} {spot_price:.8f} {perp_price:.8f} {current_time}")
                
                # 如果成功，跳出重试循环
                break
                
            except ccxt.NetworkError as e:
                retry_count += 1
                logger.error(f"网络错误 (尝试 {retry_count}/{max_retries}): {str(e)}")
                if retry_count == max_retries:
                    logger.error("达到最大重试次数，等待下一轮")
                time.sleep(2 ** retry_count)  # 指数退避
                
            except ccxt.ExchangeError as e:
                logger.error(f"交易所错误: {str(e)}")
                time.sleep(5)
                break
                
            except Exception as e:
                logger.error(f"未知错误: {str(e)}")
                time.sleep(5)
                break
        
        # 主循环的等待时间
        time.sleep(1)

if __name__ == "__main__":
    get_bybit_price_diff()
