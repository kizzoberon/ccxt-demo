import ccxt
import time
from datetime import datetime
import logging
from typing import Dict, List, Optional

def setup_logger():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

class ExchangeManager:
    def __init__(self, proxy_url: str):
        self.logger = setup_logger()
        self.proxy_settings = {
            'http': proxy_url,
            'https': proxy_url
        }
        
        # 初始化交易所
        self.exchanges = {
            'bybit': ccxt.bybit({
                'enableRateLimit': True,
                'timeout': 30000,
                'proxies': self.proxy_settings,
                'options': {'verify': False}
            }),
            'bitget': ccxt.bitget({
                'enableRateLimit': True,
                'timeout': 30000,
                'proxies': self.proxy_settings,
                'options': {'verify': False}
            })
        }
        
        # 存储市场信息
        self.markets = {}
        # 存储交易对
        self.symbols = {}
        
        self._init_markets()
    
    def _init_markets(self):
        """初始化所有交易所的市场信息"""
        for exchange_id, exchange in self.exchanges.items():
            try:
                self.markets[exchange_id] = exchange.load_markets()
                
                # 获取BTC交易对
                spot_symbols = [symbol for symbol in self.markets[exchange_id] 
                              if 'BTC' in symbol and 'USDT' in symbol 
                              and self.markets[exchange_id][symbol].get('spot')]
                perp_symbols = [symbol for symbol in self.markets[exchange_id] 
                              if 'BTC' in symbol and 'USDT' in symbol 
                              and self.markets[exchange_id][symbol].get('swap')]
                
                self.symbols[exchange_id] = {
                    'spot': spot_symbols,
                    'swap': perp_symbols
                }
                
                self.logger.info(f"{exchange_id.upper()} Spot symbols: {spot_symbols}")
                self.logger.info(f"{exchange_id.upper()} Perp symbols: {perp_symbols}")
                
            except Exception as e:
                self.logger.error(f"初始化{exchange_id}失败: {str(e)}")
    
    def fetch_tickers(self, exchange_id: str, market_type: str, symbols: List[str]) -> Dict:
        """获取指定交易所的行情数据"""
        exchange = self.exchanges[exchange_id]
        exchange.options['defaultType'] = market_type
        
        start_time = time.perf_counter()
        tickers = exchange.fetch_tickers(symbols) if symbols else {}
        fetch_time = (time.perf_counter() - start_time) * 1000
        
        self.logger.info(f"Fetch {exchange_id} {market_type} tickers time: {fetch_time:.2f}ms")
        return tickers
    
    def process_tickers(self, exchange_id: str, tickers: Dict, market_type: str) -> Dict:
        """处理ticker数据"""
        prices = {}
        markets = self.markets[exchange_id]
        
        for symbol, ticker in tickers.items():
            if ticker['last'] is not None:
                base = markets[symbol]['base']
                if 'USDT' in base:
                    base = base.replace('USDT', '')
                prices[base] = {
                    'price': ticker['last'],
                    'symbol': symbol
                }
        return prices

def get_exchange_price_diff():
    # 初始化交易所管理器
    manager = ExchangeManager('http://127.0.0.1:7897')
    max_retries = 3
    
    while True:
        retry_count = 0
        while retry_count < max_retries:
            try:
                exchange_data = {}
                
                # 获取所有交易所的数据
                for exchange_id in manager.exchanges:
                    exchange_data[exchange_id] = {
                        'spot': manager.process_tickers(
                            exchange_id,
                            manager.fetch_tickers(exchange_id, 'spot', manager.symbols[exchange_id]['spot']),
                            'spot'
                        ),
                        'swap': manager.process_tickers(
                            exchange_id,
                            manager.fetch_tickers(exchange_id, 'swap', manager.symbols[exchange_id]['swap']),
                            'swap'
                        )
                    }
                
                # 获取当前时间
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # 找出所有交易所都有的币对
                common_bases = set()
                for exchange_id in exchange_data:
                    spot_bases = set(exchange_data[exchange_id]['spot'].keys())
                    swap_bases = set(exchange_data[exchange_id]['swap'].keys())
                    if not common_bases:
                        common_bases = spot_bases & swap_bases
                    else:
                        common_bases &= (spot_bases & swap_bases)
                
                # 输出价格差
                for base in common_bases:
                    # 收集所有价格和符号
                    bybit_spot = exchange_data['bybit']['spot'][base]
                    bybit_perp = exchange_data['bybit']['swap'][base]
                    bitget_spot = exchange_data['bitget']['spot'][base]
                    bitget_perp = exchange_data['bitget']['swap'][base]
                    
                    # 收集所有价格
                    prices = [
                        bybit_spot['price'],   # price1
                        bybit_perp['price'],   # price2
                        bitget_spot['price'],  # price3
                        bitget_perp['price']   # price4
                    ]
                    
                    # 计算所有可能的价差
                    diffs = []
                    for i in range(len(prices)):
                        for j in range(i + 1, len(prices)):
                            # 始终用大的价格减去小的价格，确保价差为正
                            high_price = max(prices[i], prices[j])
                            low_price = min(prices[i], prices[j])
                            diff = ((high_price - low_price) / ((high_price + low_price) / 2)) * 100
                            
                            # 如果原始的i,j顺序产生的是负值，需要交换顺序
                            if prices[j] < prices[i]:
                                i, j = j, i
                            
                            diffs.append((diff, diff, i, j))
                    
                    # 找出最大价差
                    max_diff = max(diffs, key=lambda x: x[0])
                    
                    # 获取价差对应的交易所和市场类型
                    markets = ['BYBIT:spot', 'BYBIT:perp', 'BITGET:spot', 'BITGET:perp']
                    max_diff_desc = f"{markets[max_diff[2]]}-{markets[max_diff[3]]}"
                    
                    # 按照要求格式输出
                    print(f"BYBIT:{bybit_spot['symbol']} BYBIT:{bybit_perp['symbol']} "
                          f"BITGET:{bitget_spot['symbol']} BITGET:{bitget_perp['symbol']} "
                          f"{prices[0]:.8f} {prices[1]:.8f} {prices[2]:.8f} {prices[3]:.8f} "
                          f"MaxDiff({max_diff_desc}): {max_diff[1]:.4f}% {current_time}")
                
                break
                
            except Exception as e:
                retry_count += 1
                manager.logger.error(f"错误: {str(e)}")
                if retry_count == max_retries:
                    manager.logger.error("达到最大重试次数，等待下一轮")
                time.sleep(2 ** retry_count)
        
        time.sleep(1)

if __name__ == "__main__":
    get_exchange_price_diff()
