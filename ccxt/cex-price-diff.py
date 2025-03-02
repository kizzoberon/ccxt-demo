import ccxt
import time
from datetime import datetime
import logging
from typing import Dict, List, Optional

# 在文件开头添加颜色常量
GREEN = '\033[32m'
RESET = '\033[0m'

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
                
                # 获取所有USDT交易对
                spot_symbols = [symbol for symbol in self.markets[exchange_id] 
                              if 'USDT' in symbol 
                              and self.markets[exchange_id][symbol].get('spot')]
                perp_symbols = [symbol for symbol in self.markets[exchange_id] 
                              if 'USDT' in symbol 
                              and self.markets[exchange_id][symbol].get('swap')]
                
                self.symbols[exchange_id] = {
                    'spot': spot_symbols,
                    'swap': perp_symbols
                }
                
                self.logger.info(f"{exchange_id.upper()} Spot symbols count: {len(spot_symbols)}")
                self.logger.info(f"{exchange_id.upper()} Perp symbols count: {len(perp_symbols)}")
                
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
                    'symbol': symbol,
                    'bid': ticker['bid'],
                    'ask': ticker['ask'],
                    'bidVolume': ticker['bidVolume'],
                    'askVolume': ticker['askVolume'],
                    'baseVolume': ticker['baseVolume']  # 24小时交易量
                }
        return prices

    def calculate_fees(self, market1: str, market2: str) -> float:
        """计算套利手续费"""
        # 费率表 - 使用taker费率
        fees = {
            'BYBIT:spot': {'taker': 0.001},  # 0.1%
            'BYBIT:perp': {'taker': 0.0006}, # 0.06%
            'BITGET:spot': {'taker': 0.001}, # 0.1%
            'BITGET:perp': {'taker': 0.0006} # 0.06%
        }
        
        market1_fee = fees[market1]['taker']
        market2_fee = fees[market2]['taker']
        
        # 判断是否为合约套利
        is_perp_arb = ':perp' in market1 or ':perp' in market2
        
        if is_perp_arb:
            # 合约套利：开仓+平仓 (共4笔费用)
            return (market1_fee + market2_fee) * 2 * 100  # 转换为百分比
        else:
            # 现货套利：一次买入一次卖出 (共2笔费用)
            return (market1_fee + market2_fee) * 100  # 转换为百分比

def is_valid_arb_direction(market1: str, market2: str) -> bool:
    """
    检查套利方向是否有效
    market1: 买入市场
    market2: 卖出市场
    """
    # 如果是买入合约卖出现货的组合，返回False
    if ':perp' in market1 and ':spot' in market2:
        return False
    return True

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
                
                # 存储所有币对的最大价差信息
                max_diffs_by_base = {}
                
                # 计算所有币对的价差
                for base in common_bases:
                    markets_data = [
                        {'name': 'BYBIT:spot', 'data': exchange_data['bybit']['spot'][base]},
                        {'name': 'BYBIT:perp', 'data': exchange_data['bybit']['swap'][base]},
                        {'name': 'BITGET:spot', 'data': exchange_data['bitget']['spot'][base]},
                        {'name': 'BITGET:perp', 'data': exchange_data['bitget']['swap'][base]}
                    ]
                    
                    max_diff_info = None
                    max_diff_value = -1
                    
                    # 计算所有可能的价差组合
                    for i in range(len(markets_data)):
                        for j in range(len(markets_data)):
                            if i != j:  # 不同市场之间比较
                                market_i = markets_data[i]
                                market_j = markets_data[j]
                                
                                # 检查交易方向是否有效
                                if not is_valid_arb_direction(market_i['name'], market_j['name']):
                                    continue
                                
                                # 使用ask和bid价格计算价差
                                ask_price = market_i['data']['ask']
                                bid_price = market_j['data']['bid']
                                
                                if ask_price > 0 and bid_price > 0:
                                    # 计算可交易数量和对应的USDT价值
                                    tradeable_volume = min(
                                        market_i['data']['askVolume'],
                                        market_j['data']['bidVolume']
                                    )
                                    tradeable_value_usdt = tradeable_volume * ask_price
                                    
                                    # 只处理流动性大于1000 USDT的交易对
                                    if tradeable_value_usdt >= 1000:
                                        # 计算价差
                                        diff = ((bid_price - ask_price) / ask_price) * 100
                                        
                                        if diff > max_diff_value and diff > 0:
                                            max_diff_value = diff
                                            max_diff_info = {
                                                'base': base,
                                                'diff': diff,
                                                'market1': market_i['name'],
                                                'market2': market_j['name'],
                                                'ask_price': ask_price,
                                                'bid_price': bid_price,
                                                'ask_volume': market_i['data']['askVolume'],
                                                'bid_volume': market_j['data']['bidVolume'],
                                                'tradeable_volume': tradeable_volume,
                                                'tradeable_value_usdt': tradeable_value_usdt,
                                                'symbols': {
                                                    'market1': market_i['data']['symbol'],
                                                    'market2': market_j['data']['symbol']
                                                }
                                            }
                    
                    # 只存储有效的价差信息
                    if max_diff_info:
                        max_diffs_by_base[base] = max_diff_info
                
                # 按价差降序排序并获取前10个
                top_diffs = sorted(max_diffs_by_base.values(), key=lambda x: x['diff'], reverse=True)[:10]
                
                # 清屏
                print('\033[2J\033[H', end='')
                print(f"Top 10 Price Differences - {current_time}")
                print("-" * 220)  # 增加分隔线长度
                print(f"{'Symbol':<10} {'Market1':<15} {'Bid1/Ask1':<25} {'Market2':<15} {'Bid2/Ask2':<25} "
                      f"{'MaxDiff':<12} {'Volume(USDT)':<15} {'Fees':<10} {'Net Profit':<12}")
                print("-" * 220)
                
                # 输出前10个最大价差
                for diff_info in top_diffs:
                    # 获取两个市场的完整数据
                    market1_data = next(m['data'] for m in markets_data if m['name'] == diff_info['market1'])
                    market2_data = next(m['data'] for m in markets_data if m['name'] == diff_info['market2'])
                    
                    # 计算手续费
                    total_fees = manager.calculate_fees(diff_info['market1'], diff_info['market2'])
                    
                    # 计算净利润
                    net_profit = diff_info['diff'] - total_fees
                    
                    # 计算交易量（USDT）
                    volume_usdt = diff_info['tradeable_volume'] * diff_info['ask_price']
                    
                    # 使用不同颜色显示净利润
                    profit_color = GREEN if net_profit > 0 else '\033[31m'
                    
                    print(f"{diff_info['base']:<10} "
                          f"{diff_info['market1']:<15} "
                          f"{market1_data['bid']:<12.8f}/{market1_data['ask']:<12.8f} "
                          f"{diff_info['market2']:<15} "
                          f"{market2_data['bid']:<12.8f}/{market2_data['ask']:<12.8f} "
                          f"{profit_color}{diff_info['diff']:>7.4f}%{RESET} "
                          f"${volume_usdt:<14,.2f} "
                          f"{total_fees:>7.4f}% "
                          f"{profit_color}{net_profit:>7.4f}%{RESET}")
                
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
