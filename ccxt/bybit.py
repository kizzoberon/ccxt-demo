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
        'http': 'http://127.0.0.1:7897',  # 根据你的实际代理端口修改
        'https': 'http://127.0.0.1:7897'  # 根据你的实际代理端口修改
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
    # 过滤出仅包含BTC和USDT的交易对
    market_list = [symbol for symbol in markets if 'BTC' in symbol and 'USDT' in symbol]
    while True:
        retry_count = 0
        while retry_count < max_retries:
            try:
                # 获取所有交易对的最新行情
                # 获取现货市场价格
                exchange.options['defaultType'] = 'spot'
                spot_tickers = exchange.fetch_tickers()

                # 获取合约市场价格
                exchange.options['defaultType'] = 'swap'
                perp_tickers = exchange.fetch_tickers()
                tickers = {**spot_tickers, **perp_tickers}
                # 过滤出仅包含BTC的交易对
                tickers = {symbol: ticker for symbol, ticker in tickers.items() if symbol in market_list}
                
                # 存储现货和合约的价格
                spot_prices = {}
                perp_prices = {}
                
                # 遍历所有交易对
                for symbol, ticker in tickers.items():
                    if ticker['last'] is None:  # 跳过没有最新价格的交易对
                        continue
                    
                    # 获取市场信息
                    market = markets.get(symbol)
                    if market is None:
                        continue
                        
                    # 根据市场类型分类
                    base = market['base']
                    if 'USDT' in base:  # 去除基础货币中的USDT
                        base = base.replace('USDT', '')
                    
                    if market['spot']:  # 现货市场
                        spot_prices[base] = {
                            'price': ticker['last'],
                            'symbol': symbol
                        }
                    elif market['swap']:  # 永续合约市场
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
