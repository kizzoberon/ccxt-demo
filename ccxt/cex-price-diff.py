import ccxt
import time
from datetime import datetime
import logging
from typing import Dict, List, Optional
import concurrent.futures

# 在文件开头添加颜色常量
GREEN = '\033[32m'
RESET = '\033[0m'

def setup_logger():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

logger = setup_logger()

class ExchangeManager:
    def __init__(self, proxy_url: str):
        self.proxy_settings = {
            'http': proxy_url,
            'https': proxy_url
        }
        
        # 初始化交易所
        self.exchanges = {
            'bybit': ccxt.bybit({
                'enableRateLimit': True,
                'timeout': 10000,
                'proxies': self.proxy_settings,
                'options': {'verify': False}
            }),
            'bitget': ccxt.bitget({
                'enableRateLimit': True,
                'timeout': 10000,
                'proxies': self.proxy_settings,
                'options': {'verify': False}
            }),
            'binance': ccxt.binance({
                'enableRateLimit': True,
                'timeout': 10000,
                'proxies': self.proxy_settings,
                'options': {'verify': False}
            }),
            'okx': ccxt.okx({
                'enableRateLimit': True,
                'timeout': 10000,
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
                
                logger.info(f"{exchange_id.upper()} Spot symbols count: {len(spot_symbols)}")
                logger.info(f"{exchange_id.upper()} Perp symbols count: {len(perp_symbols)}")
                
            except Exception as e:
                logger.error(f"初始化{exchange_id}失败: {str(e)}")
    
    def fetch_tickers(self, exchange_id: str, market_type: str, symbols: List[str]) -> Dict:
        """获取指定交易所的行情数据"""
        exchange = self.exchanges[exchange_id]
        exchange.options['defaultType'] = market_type
        
        start_time = time.perf_counter()
        tickers = {}
        
        def fetch_batch(batch_symbols):
            try:
                return exchange.fetch_tickers(batch_symbols)
            except Exception as e:
                logger.error(f"获取{exchange_id}数据失败: {str(e)}")
                return {}
    
        # 需要分批获取数据
        batch_size = 200
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [
                executor.submit(fetch_batch, symbols[i:i + batch_size])
                for i in range(0, len(symbols), batch_size)
            ]
            for future in concurrent.futures.as_completed(futures):
                tickers.update(future.result())
        
        fetch_time = (time.perf_counter() - start_time) * 1000
        logger.info(f"Fetch {exchange_id} {market_type} tickers time: {fetch_time:.2f}ms")
        
        return tickers
    
    def process_tickers(self, exchange_id: str, tickers: Dict) -> Dict:
        """处理ticker数据"""
        prices = {}
        markets = self.markets[exchange_id]
        
        for symbol, ticker in tickers.items():
            if ticker['last'] is not None:
                base = markets[symbol]['base']
                if 'USDT' in base:
                    base = base.replace('USDT', '')
                if base == '':
                    continue
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
            'BYBIT:spot': {'taker': 0.001},   # 0.1%
            'BYBIT:perp': {'taker': 0.0006},  # 0.06%
            'BITGET:spot': {'taker': 0.001},  # 0.1%
            'BITGET:perp': {'taker': 0.0006}, # 0.06%
            'BINANCE:spot': {'taker': 0.001}, # 0.1%
            'BINANCE:perp': {'taker': 0.0004},# 0.04%
            'OKX:spot': {'taker': 0.001},     # 0.1%
            'OKX:perp': {'taker': 0.0005}     # 0.05%
        }
        
        market1_fee = fees[market1]['taker']
        market2_fee = fees[market2]['taker']
        
        # 判断是否为合约套利
        is_perp_arb = ':perp' in market1 and ':perp' in market2
        
        if is_perp_arb:
            # 合约套利：开仓+平仓 (共4笔费用)
            return (market1_fee + market2_fee) * 2 * 100  # 转换为百分比
        elif ':perp' in market1 or ':perp' in market2:
            # 合约+现货，开仓+平仓 (共4笔费用)
            return (market1_fee + market2_fee) * 2 * 100
        else:
            # 现货套利：现货一次买入一次卖出+合约套保 (共4笔费用)
            return (market1_fee + market2_fee + market2_fee * 2) * 100  # 转换为百分比

def is_valid_arb_direction(market1: str, market2: str) -> bool:
    """
    检查套利方向是否有效
    market1: 买入市场
    market2: 卖出市场
    """
    if market1 == market2:
        return False

    # 如果是买入合约卖出现货的组合，返回False
    if ':perp' in market1 and ':spot' in market2:
        return False
    return True

def get_exchange_price_diff():
    try:
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
                                manager.fetch_tickers(exchange_id, 'spot', manager.symbols[exchange_id]['spot'])
                            ),
                            'swap': manager.process_tickers(
                                exchange_id,
                                manager.fetch_tickers(exchange_id, 'swap', manager.symbols[exchange_id]['swap'])
                            )
                        }

                    # 获取当前时间
                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    # 存储所有币对的最大价差信息
                    all_diffs = []
                    # 用于记录已经处理过的 market1 和 market2 组合
                    processed_pairs = set()

                    # 找出所有可能的两个交易所组合
                    exchange_ids = list(manager.exchanges.keys())
                    for i in range(len(exchange_ids)):
                        for j in range(i, len(exchange_ids)):
                            exchange1 = exchange_ids[i]
                            exchange2 = exchange_ids[j]

                            # 找出这两个交易所的共同币对
                            spot_bases1 = set(exchange_data[exchange1]['spot'].keys())
                            swap_bases1 = set(exchange_data[exchange1]['swap'].keys())
                            all_bases1 = spot_bases1.union(swap_bases1)

                            spot_bases2 = set(exchange_data[exchange2]['spot'].keys())
                            swap_bases2 = set(exchange_data[exchange2]['swap'].keys())
                            all_bases2 = spot_bases2.union(swap_bases2)

                            common_bases = all_bases1.intersection(all_bases2)

                            # 计算这些共同币对的价差
                            for base in common_bases:
                                markets_data = [
                                    {'name': f'{exchange1.upper()}:spot', 'data': exchange_data[exchange1]['spot'].get(base)},
                                    {'name': f'{exchange1.upper()}:perp', 'data': exchange_data[exchange1]['swap'].get(base)},
                                    {'name': f'{exchange2.upper()}:spot', 'data': exchange_data[exchange2]['spot'].get(base)},
                                    {'name': f'{exchange2.upper()}:perp', 'data': exchange_data[exchange2]['swap'].get(base)}
                                ]

                                # 计算所有可能的价差组合
                                for k in range(len(markets_data)):
                                    for l in range(len(markets_data)):
                                        if k != l:  # 不同市场之间比较
                                            market_k = markets_data[k]
                                            market_l = markets_data[l]

                                            # 检查交易方向是否有效
                                            if not is_valid_arb_direction(market_k['name'], market_l['name']):
                                                continue

                                            # 使用ask和bid价格计算价差
                                            if market_k['data'] and market_l['data']:
                                                ask_price = market_k['data']['ask']
                                                bid_price = market_l['data']['bid']

                                                # 检查价格是否为None或者0
                                                if ask_price is not None and bid_price is not None and ask_price > 0 and bid_price > 0:
                                                    # 计算可交易数量和对应的USDT价值
                                                    tradeable_value_usdt = min(
                                                        market_k['data']['askVolume'] * market_k['data']['ask'],
                                                        market_l['data']['bidVolume'] * market_l['data']['bid']
                                                    )

                                                    # 只处理流动性大于100 USDT的交易对
                                                    if tradeable_value_usdt >= 100:
                                                        # 计算价差
                                                        diff = ((bid_price - ask_price) / ((ask_price + bid_price) / 2)) * 100

                                                        # 生成 market1 和 market2 的组合名称
                                                        pair_name = f"{base}{market_k['name']}_{market_l['name']}"
                                                        if pair_name not in processed_pairs:
                                                            if 0 < diff < 100:
                                                                diff_info = {
                                                                    'base': base,
                                                                    'diff': diff,
                                                                    'market1': market_k['name'],
                                                                    'market2': market_l['name'],
                                                                    'ask_price': ask_price,
                                                                    'bid_price': bid_price,
                                                                    'ask_volume': market_k['data']['askVolume'],
                                                                    'bid_volume': market_l['data']['bidVolume'],
                                                                    'tradeable_value_usdt': tradeable_value_usdt,
                                                                    'symbols': {
                                                                        'market1': market_k['data']['symbol'],
                                                                        'market2': market_l['data']['symbol']
                                                                    }
                                                                }
                                                                all_diffs.append(diff_info)
                                                                processed_pairs.add(pair_name)

                    # 按价差降序排序并获取前10个
                    top_diffs = sorted(all_diffs, key=lambda x: x['diff'], reverse=True)[:10]

                    # 为相同币种的不同套利路径添加标识
                    symbol_count = {}
                    for diff_info in top_diffs:
                        base = diff_info['base']
                        if base not in symbol_count:
                            symbol_count[base] = 0
                        else:
                            symbol_count[base] += 1
                            diff_info['base'] = f"{base}({symbol_count[base]})"

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
                        market1_exchange = diff_info['market1'].split(':')[0].lower()
                        market1_type = 'spot' if ':spot' in diff_info['market1'] else 'swap'
                        market1_data = exchange_data[market1_exchange][market1_type].get(diff_info['base'].split('(')[0])

                        market2_exchange = diff_info['market2'].split(':')[0].lower()
                        market2_type = 'spot' if ':spot' in diff_info['market2'] else 'swap'
                        market2_data = exchange_data[market2_exchange][market2_type].get(diff_info['base'].split('(')[0])

                        # 计算手续费
                        total_fees = manager.calculate_fees(diff_info['market1'], diff_info['market2'])

                        # 计算净利润
                        net_profit = diff_info['diff'] - total_fees

                        # 计算交易量（USDT）
                        volume_usdt = diff_info['tradeable_value_usdt']

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
                    break  # 跳出重试循环

                except Exception as e:
                    retry_count += 1
                    logger.error(f"错误: {str(e)}", exc_info=True)
                    if retry_count == max_retries:
                        logger.error("达到最大重试次数，等待下一轮")
                    time.sleep(2 ** retry_count)

            time.sleep(1)  # 成功执行后等待1秒

    except KeyboardInterrupt:
        logger.info("正在退出程序...")
    finally:
        logger.info("程序已退出")

if __name__ == "__main__":
    get_exchange_price_diff()
