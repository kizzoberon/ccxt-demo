import asyncio
import sys

import argparse
import ccxt.pro as ccxtpro
import logging
from typing import Optional

# 配置日志
def setup_logger():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

logger = setup_logger()

class ArbitrageBot:
    def __init__(self, proxy_url: Optional[str] = None):
        # 初始化代理设置
        if proxy_url:
            self.exchange = ccxtpro.bybit({
                'enableRateLimit': True,
                'options': {'verify': False}  # 禁用SSL验证以避免代理问题
            })
            # 设置HTTP和WebSocket代理
            self.exchange.http_proxy = proxy_url
            self.exchange.ws_proxy = proxy_url
        else:
            self.exchange = ccxtpro.binance({
                'enableRateLimit': True
            })
    
    async def watch_orderbooks(self):
        while True:
            try:
                # 同时获取现货和永续合约的订单簿
                spot_orderbook = await self.exchange.watch_order_book('BTC/USDT')
                futures_orderbook = await self.exchange.watch_order_book('BTC/USDT:USDT')
                logger.info(f"订单簿更新时间: spot:{spot_orderbook['timestamp']}, futures:{futures_orderbook['timestamp']}")
                # 打印订单簿信息
                logger.info(f"spot_orderbook: {spot_orderbook}")
                logger.info(f"futures_orderbook: {futures_orderbook}")

                # 获取买卖价格
                spot_bid = spot_orderbook['bids'][0][0] if len(spot_orderbook['bids']) > 0 else None
                spot_ask = spot_orderbook['asks'][0][0] if len(spot_orderbook['asks']) > 0 else None
                futures_bid = futures_orderbook['bids'][0][0] if len(futures_orderbook['bids']) > 0 else None
                futures_ask = futures_orderbook['asks'][0][0] if len(futures_orderbook['asks']) > 0 else None

                # 获取挂单数量
                spot_bid_volume = spot_orderbook['bids'][0][1] if len(spot_orderbook['bids']) > 0 else 0
                spot_ask_volume = spot_orderbook['asks'][0][1] if len(spot_orderbook['asks']) > 0 else 0
                futures_bid_volume = futures_orderbook['bids'][0][1] if len(futures_orderbook['bids']) > 0 else 0
                futures_ask_volume = futures_orderbook['asks'][0][1] if len(futures_orderbook['asks']) > 0 else 0

                # 计算价差
                # 现货买入 - 期货卖出的价差
                spread1 = futures_bid - spot_ask if (futures_bid and spot_ask) else None
                # 期货买入 - 现货卖出的价差
                spread2 = spot_bid - futures_ask if (spot_bid and futures_ask) else None

                # 打印订单簿信息
                logger.info(f"现货 BTC/USDT - Bid: {spot_bid} ({spot_bid_volume}) | Ask: {spot_ask} ({spot_ask_volume})")
                logger.info(f"永续 BTC/USDT - Bid: {futures_bid} ({futures_bid_volume}) | Ask: {futures_ask} ({futures_ask_volume})")
                logger.info(f"价差1 (现货买入-期货卖出): {spread1}")
                logger.info(f"价差2 (期货买入-现货卖出): {spread2}")

            except Exception as e:
                logger.error(f"发生错误: {str(e)}")
                await asyncio.sleep(1)

    async def run(self):
        try:
            await self.watch_orderbooks()
        except asyncio.CancelledError:
            logger.info("任务被取消")
        except Exception as e:
            logger.error(f"运行错误: {str(e)}")
        finally:
            await self.exchange.close()

async def run_bot():
    parser = argparse.ArgumentParser(description='交易所套利监控工具')
    parser.add_argument('-p', '--proxy',
                        help='代理服务器地址，例如：http://127.0.0.1:7897',
                        default=None)
    args = parser.parse_args()
    bot = ArbitrageBot(args.proxy)
    await bot.run()

if __name__ == '__main__':
    # 在 Windows 平台上强制使用 SelectorEventLoop
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("正在退出程序...")
    finally:
        logger.info("程序已退出")
