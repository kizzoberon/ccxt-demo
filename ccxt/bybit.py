import ccxt
import time
from datetime import datetime
import logging

def setup_logger():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

def get_bybit_price_diff():
    logger = setup_logger()
    
    # 配置代理设置
    proxies = {
        'http': 'http://127.0.0.1:7897',
        'https': 'http://127.0.0.1:7897'
    }
    
    # 初始化ByBit交易所
    exchange = ccxt.bybit({
        'enableRateLimit': True,
        'timeout': 30000,
        'proxies': proxies,
        'options': {
            'verify': False
        }
    })
    
    max_retries = 3

    # 加载市场信息
    markets = exchange.load_markets()
    
    # 分别过滤出现货和合约的BTC交易对
    spot_symbols = [symbol for symbol in markets if 'BTC' in symbol and 'USDT' in symbol and markets[symbol]['spot']]
    perp_symbols = [symbol for symbol in markets if 'BTC' in symbol and 'USDT' in symbol and markets[symbol]['swap']]
    
    logger.info(f"Spot symbols: {spot_symbols}")
    logger.info(f"Perp symbols: {perp_symbols}")
    
    while True:
        retry_count = 0
        while retry_count < max_retries:
            try:
                # 获取现货市场价格
                exchange.options['defaultType'] = 'spot'
                start_time = time.perf_counter()
                spot_tickers = exchange.fetch_tickers(spot_symbols) if spot_symbols else {}
                spot_time = (time.perf_counter() - start_time) * 1000  # 转换为毫秒

                # 获取合约市场价格
                exchange.options['defaultType'] = 'swap'
                start_time = time.perf_counter()
                perp_tickers = exchange.fetch_tickers(perp_symbols) if perp_symbols else {}
                perp_time = (time.perf_counter() - start_time) * 1000  # 转换为毫秒
                
                logger.info(f"Fetch spot tickers time: {spot_time:.2f}ms")
                logger.info(f"Fetch perp tickers time: {perp_time:.2f}ms")
                logger.info(f"Total fetch time: {spot_time + perp_time:.2f}ms")
                
                # 存储现货和合约的价格
                spot_prices = {}
                perp_prices = {}
                
                # 处理现货价格
                for symbol, ticker in spot_tickers.items():
                    if ticker['last'] is not None:
                        base = markets[symbol]['base']
                        if 'USDT' in base:
                            base = base.replace('USDT', '')
                        spot_prices[base] = {
                            'price': ticker['last'],
                            'symbol': symbol
                        }
                
                # 处理合约价格
                for symbol, ticker in perp_tickers.items():
                    if ticker['last'] is not None:
                        base = markets[symbol]['base']
                        if 'USDT' in base:
                            base = base.replace('USDT', '')
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
                    
                    # 计算价差百分比
                    price_diff_pct = ((perp_price - spot_price) / ((spot_price + perp_price) / 2)) * 100
                    
                    print(f"{spot_symbol} {perp_symbol} {spot_price:.8f} {perp_price:.8f} {price_diff_pct:.4f}% {current_time}")
                
                # 如果成功，跳出重试循环
                break
                
            except ccxt.NetworkError as e:
                retry_count += 1
                logger.error(f"网络错误 (尝试 {retry_count}/{max_retries}): {str(e)}")
                if retry_count == max_retries:
                    logger.error("达到最大重试次数，等待下一轮")
                time.sleep(2 ** retry_count)
                
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
