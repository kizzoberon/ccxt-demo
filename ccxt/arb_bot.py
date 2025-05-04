import argparse
import asyncio
import logging
import os
import sys
from typing import Optional

import ccxt.pro as ccxtpro

from config import parse_config

# 全局日志变量
logger = None

def setup_logger(log_file: Optional[str] = None):
    # 创建默认日志目录
    if log_file is None:
        log_file = './log/arb_bot.log'
    
    # 确保日志目录存在
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    # 配置日志格式
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # 配置文件处理器
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    
    # 配置控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # 配置根日志记录器
    global logger
    logger = logging.getLogger('arb_bot')
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

class ArbitrageBot:
    def __init__(self, config_path: str, proxy_url: Optional[str] = None):
        # 加载配置
        self.config = parse_config(config_path)
        
        # 初始化交易所连接
        exchange_options = {
            'enableRateLimit': True,
        }
        
        if proxy_url:
            exchange_options['options'] = {'verify': False}
        
        # 初始化两个交易所
        self.exchange1 = getattr(ccxtpro, self.config.market1.exchange)(exchange_options)
        self.exchange2 = getattr(ccxtpro, self.config.market2.exchange)(exchange_options)
        
        # 设置代理
        if proxy_url:
            for exchange in [self.exchange1, self.exchange2]:
                exchange.http_proxy = proxy_url
                exchange.ws_proxy = proxy_url
    
    async def watch_orderbooks(self):
        while True:
            try:
                # 获取两个市场的订单簿
                orderbook1 = await self.exchange1.watch_order_book(self.config.market1.name)
                orderbook2 = await self.exchange2.watch_order_book(self.config.market2.name)
                
                # 获取价格
                ask1 = orderbook1['asks'][0][0] if len(orderbook1['asks']) > 0 else None
                bid1 = orderbook1['bids'][0][0] if len(orderbook1['bids']) > 0 else None
                ask2 = orderbook2['asks'][0][0] if len(orderbook2['asks']) > 0 else None
                bid2 = orderbook2['bids'][0][0] if len(orderbook2['bids']) > 0 else None
                
                # 计算正向和反向价差
                if self.config.market1.direction == '+' and self.config.market2.direction == '-':
                    # 正向价差：market2(卖方bid) - market1(买方ask)
                    forward_spread = (bid2 - ask1) / ((bid2 + ask1) / 2) * 100 if (bid2 and ask1) else None
                    forward_direction = f"+{self.config.market1.exchange}({self.config.market1.name})-{self.config.market2.exchange}({self.config.market2.name})"
                    
                    # 反向价差：market1(卖方bid) - market2(买方ask)
                    reverse_spread = (bid1 - ask2) / ((bid1 + ask2) / 2) * 100 if (bid1 and ask2) else None
                    reverse_direction = f"+{self.config.market2.exchange}({self.config.market2.name})-{self.config.market1.exchange}({self.config.market1.name})"
                else:
                    # 正向价差：market1(卖方bid) - market2(买方ask)
                    forward_spread = (bid1 - ask2) / ((bid1 + ask2) / 2) * 100 if (bid1 and ask2) else None
                    forward_direction = f"+{self.config.market2.exchange}({self.config.market2.name})-{self.config.market1.exchange}({self.config.market1.name})"
                    
                    # 反向价差：market2(卖方bid) - market1(买方ask)
                    reverse_spread = (bid2 - ask1) / ((bid2 + ask1) / 2) * 100 if (bid2 and ask1) else None
                    reverse_direction = f"+{self.config.market1.exchange}({self.config.market1.name})-{self.config.market2.exchange}({self.config.market2.name})"
                
                # 输出价格信息
                logger.info(f"{self.config.market1.exchange} {self.config.market1.name} - "
                          f"Bid: {bid1} | Ask: {ask1}")
                logger.info(f"{self.config.market2.exchange} {self.config.market2.name} - "
                          f"Bid: {bid2} | Ask: {ask2}")
                
                # 输出正向和反向价差
                logger.info(f"正向价差 ({forward_direction}): {forward_spread:.4f}% (阈值: {float(self.config.priceDiff)*100}%)")
                logger.info(f"反向价差 ({reverse_direction}): {reverse_spread:.4f}% (阈值: {float(self.config.priceDiff)*100}%)")
                
                # 检查正向价差是否超过阈值
                if forward_spread and forward_spread > float(self.config.priceDiff) * 100:
                    logger.warning(f"发现正向套利机会！{forward_direction} 价差 {forward_spread:.4f}% 超过阈值")
                
                # 检查反向价差是否超过阈值
                if reverse_spread and reverse_spread > float(self.config.priceDiff) * 100:
                    logger.warning(f"发现反向套利机会！{reverse_direction} 价差 {reverse_spread:.4f}% 超过阈值")
                
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
            await self.exchange1.close()
            await self.exchange2.close()

async def run_bot(config_path: str, proxy_url: Optional[str] = None):
    bot = ArbitrageBot(config_path, proxy_url)
    await bot.run()

if __name__ == '__main__':
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='交易所套利监控工具')
    parser.add_argument('-p', '--proxy',
                      help='代理服务器地址，例如：http://127.0.0.1:7897',
                      default=None)
    parser.add_argument('-c', '--config',
                      help='配置文件路径',
                      default='config/arb.yaml')
    parser.add_argument('-l', '--log',
                      help='日志文件路径，默认为 .log/arb_bot.log',
                      default=None)
    args = parser.parse_args()
    
    # 在 Windows 平台上强制使用 SelectorEventLoop
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # 初始化日志
    setup_logger(args.log)
    
    try:
        asyncio.run(run_bot(args.config, args.proxy))
    except KeyboardInterrupt:
        logger.info("正在退出程序...")
    finally:
        logger.info("程序已退出")
