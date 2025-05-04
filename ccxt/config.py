import yaml
from dataclasses import dataclass
from typing import Literal

@dataclass
class MarketConfig:
    type: str
    name: str
    exchange: str
    direction: Literal["+", "-"]
    multiple: str

@dataclass
class ArbitrageConfig:
    times: str
    maxSize: float
    perSize: float
    priceDiff: str
    market1: MarketConfig
    market2: MarketConfig
    stop: bool

def parse_config(config_path: str) -> ArbitrageConfig:
    """解析YAML配置文件为配置对象
    
    Args:
        config_path: YAML配置文件的路径
        
    Returns:
        ArbitrageConfig: 解析后的配置对象
    """
    # 读取并解析YAML文件
    with open(config_path, 'r', encoding='utf-8') as f:
        config_dict = yaml.safe_load(f)
    
    # 创建市场配置对象
    market1 = MarketConfig(**config_dict['market1'])
    market2 = MarketConfig(**config_dict['market2'])
    
    # 创建并返回完整配置对象
    return ArbitrageConfig(
        times=config_dict['times'],
        maxSize=float(config_dict['maxSize']),
        perSize=float(config_dict['perSize']),
        priceDiff=config_dict['priceDiff'],
        market1=market1,
        market2=market2,
        stop=config_dict['stop']
    )