# CCXT 加密货币交易套利工具

这是一个基于 CCXT 库开发的加密货币交易套利监控工具，支持多个主流交易所的现货和合约市场价差监控。

## 主要功能

1. **价差监控工具** (cex_price_diff.py)
   - 支持多个主流交易所：Binance、OKX、Gate、Bybit、Bitget
   - 实时监控现货和合约市场价格差异
   - 支持自定义代币列表过滤
   - 显示实时价差、交易量等市场数据

2. **自动套利机器人** (arb_bot.py)
   - 基于 WebSocket 实时监控订单簿数据
   - 支持现货-合约跨市场套利
   - 可配置价差阈值和交易参数
   - 自动识别正向和反向套利机会

## 环境要求

```bash
# 安装依赖
pip install -r requirements.txt
```

主要依赖：

- ccxt==4.1.13
- urllib3==1.26.6
- aiohttp_socks==0.8.4
- pyyaml==6.0.1

## 配置说明
1. 复制配置文件模板：
2. 编辑 arb.yaml 配置文件，设置：
   - 交易对
   - 交易所
   - 价差阈值
   - 交易数量限制
   - 其他套利参数

## 使用方法
1. 运行价差监控工具：

```bash
python ccxt/cex_price_diff.py [ -p PROXY_URL]
```

2. 运行套利机器人：
```bash
python ccxt/arb_bot.py [ -p PROXY_URL] [ -c CONFIG_PATH] [ -l LOG_PATH]
```

参数说明：

- -p, --proxy : 代理服务器地址（可选），例如： http://127.0.0.1:7897
- -c, --config : 配置文件路径，默认为 config/arb.yaml.example
- -l, --log : 日志文件路径，默认为 ./log/arb_bot.log

## 注意事项
1. 使用前请确保已正确配置交易所API和代理设置
2. 建议先在测试环境中验证策略
3. 请遵守交易所的交易规则和限制
4. 注意风险控制，合理设置交易参数

## 免责声明
本项目仅供学习和研究使用，作者不对使用本项目产生的任何损失负责。在使用本项目进行实际交易之前，请充分了解加密货币交易的风险。

## 许可证
本项目采用 MIT 许可证，详见 LICENSE 文件
