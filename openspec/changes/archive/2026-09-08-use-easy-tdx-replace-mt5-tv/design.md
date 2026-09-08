## Context

见 proposal.md 的 Why/What。现有数据层已是一层抽象：`DataSource` 定义了 8 个抽象方法（`connect/disconnect/list_symbols/supported_timeframes/subscribe/unsubscribe/latest_snapshot`），并由 `pa_agent/data/factory.py` 按 kind 实例化；`EastMoneySource`（东财 A股源）是这套接口的完整参考实现（连接、周期映射、快照缓存、`DataSourceTransientError` 重试都在里面）。默认数据源当前是 `mt5`，默认标的是黄金 `XAUUSD`，`app_context.bootstrap` 会为 tradingview 额外走 `set_exchange` 分支。`kline_adjust.py` 提供全局复权偏好（`qfq/hfq/none`）。

目标是把默认源替换成 `easy-tdx`（纯 A股/港股覆盖，无黄金/外汇），并彻底移除 MT5 与 TradingView 两条链路。

## Goals / Non-Goals

**Goals:**
- 新增 `TDXSource`，用 `easy_tdx.UnifiedTdxClient` 提供 A股/港股 K 线，完整实现 `DataSource` 接口。
- 把默认数据源切换为 `tdx`，默认标的切到 A股默认标的。
- 移除 MT5、TradingView 相关代码、依赖与测试。
- 固话 `easy-tdx` 依赖并同步 `uv.lock`。

**Non-Goals:**
- 不做实时 tick 推送：沿用现有基于 `latest_snapshot` 的轮询刷新（`refresh_loop`）即可。
- 不做 4h 重采样、Baostock 兜底、盘口/现价补 forming bar——`easy-tdx` 自带历史与当日 bar，直接可用；不复制东财源的这些复杂度。
- 不做回测/实时引擎（`easy_tdx.realtime/backtest`）的封装。
- 不做离线文件缓存与 GUI 界面的重新设计（只调整数据源下拉列表）。

## Decisions

- **客户端选型：用 `UnifiedTdxClient`（同步）**。`UnifiedTdxClient` 自动把 A股请求路由到 MacClient、港股/扩展市场路由到 MacExClient，内部还自带“选最佳服务器 + 失败重连”。相比手动管理 `TdxClient`/`MacClient`/主机列表更省事、更稳。`connect()`/`close()` 生命周期正好映射到 `DataSource.connect()/disconnect()`。
  - 备选：直接用 `TdxClient`（标准协议）+ `ExTdxClient`（扩展）自行路由——更底层但重复造统一路由轮子，放弃。
- **标的→(市场, 代码) 解析**：A股用 6 位数字代码，按前两位判市场（`6`/`68`/`51`/`50` → 上交所市场 0；`0`/`3` → 深交所市场 1；北交所 `4`/`8` 暂按深所做或报“暂不支持”）；港股用 `ExMarket.HK_MAIN_BOARD` 走 `goods_kline`。解析失败抛 `DataSourceTransientError`（“标的不可用”）。`list_symbols()` 返回 A股预设清单（复用 `ashare_common` 的预设），绝不阻塞网络。
- **周期映射**：`"1m"→MIN_1`、`"5m"→MIN_5`、`"15m"→MIN_15`、`"30m"→MIN_30`、`"1h"→MIN_60`、`"1d"→DAILY`、`"1w"→WEEKLY`、`"1M"→MONTHLY`（对照 spec 的“支持的时间框架”）。不支持 `4h`——TDX 原生无此周期，明确定义在 `supported_timeframes()` 之外。
- **DataFrame → `KlineBar`**：`easy-tdx` 返回按时间升序的 DataFrame（`datetime`/`date`、`open/high/low/close/vol/amount`）。在 `latest_snapshot` 内取最近 N 根后**反转**为最新在前（索引 0 为最新，含当日未收盘的 forming bar）；用 `datetime`/`date` 转 `ts_open`（ms，上海时区，与 bar 开始时间语义一致，见 spec“标准 bar 字段”）；`vol`→`volume`、`amount`→`amount`。
- **复权**：读 `get_kline_adjust()`，把 `qfq/hfq/none` 映射到 `easy_tdx.Adjust` 的 `QFQ/HFQ/NONE`，传给 `get_stock_kline/goods_kline` 的 `adjust` 参数。这使 spec 的“前复权/后复权/不复权”要求落到具体实现。
- **快照缓存与重试**：复用东财源的模式——`snapshot_cache_ttl_s(timeframe)` 做 TTL 缓存、`]n` 一致才命中；把 `easy_tdx` 异常（`TdxError` 家族）统一包装为 `DataSourceTransientError` 交给上层刷新循环重试。免费行情服务器抖动多，缓存+瞬态错误是必要的。
- **默认值与默认标的迁移**：`factory.py` 默认 kind 改为 `tdx` 并置于 `DATA_SOURCE_CHOICES` 首位（UI 可见“TDX”）；`settings.py` 里 `last_data_source` 默认与继承迁改都落到 `tdx`，移除 `last_tradingview_exchange` 字段；`market_defaults` 移除 `GOLD_MT5_SYMBOL/GOLD_TV_SYMBOL` 及黄金迁移逻辑（`migrate_general_gold_defaults`），默认标的改用 A股默认标的，避免再被迁移脚本拉回黄金。

## Risks / Trade-offs

- **免费通达信行情服务器不稳定/偶发空响应** → 复用 `DataSourceTransientError` + 快照缓存 + 上层刷新重试；做不到的静默降级不引入。
- **分钟级历史深度有限（尤其 1m/5m）** → 在 `latest_snapshot` 对分钟周期设一个合理的拉取上限并按可用条数截断；文档注明。
- **沙箱无法验证真实行情**（TRAE 沙箱拦截外网，返回伪造响应） → 落地后必须在用户真实运行环境（`rdagent` 环境下启动 PA_Agent）实测一次 A股日线与分钟线。
- **黄金/外汇链路随 MT5/TV 移除而失效** → 用户既定取舍（主做 A股/港股），spec“默认标的与周期”“不支持的标的类型”已锁定默认 A股标的，且对 XAUUSD 返回“标的不可用”。
- **`easy-tdx` 未声明在项目依赖里** → 在 pyproject + uv.lock 固化 `easy-tdx>=1.20.6`，避免换环境丢库。
- **删除面广，牵动既有测试** → 用 tasks.md 把“删除//停用→改引用→改测试”拆成小步，逐项跑 pytest 归因。

## Migration Plan

1. 依赖层：`pyproject.toml` 增 `easy-tdx>=1.20.6`，删 `MetaTrader5`、`tvdatafeed`；生成本地 `uv.lock`（在 `rdagent` 环境，遵循既有版本同步约定）。
2. 实现层：新增 `pa_agent/data/tdx_source.py`（`TDXSource`）；`factory.py`/`settings.py` 注册 `tdx`、设为默认；`market_defaults.py` 移除黄金默认迁移；`app_context.py` 删除 tradingview `set_exchange` 分支。
3. 删除层：删除 `mt5.py`、`tradingview*.py`、`tv_symbol_lookup.py`、`tools/probe_mt5_clock_skew.py`、`gui/tv_connectivity_dialog.py` 及其在 `main_window.py`/`util/logging.py` 的引用。
4. 测试层：删 `test_mt5_*`/`test_tradingview_*`/`test_tv_symbol_lookup*`；改 `test_data_source_factory`/`test_settings_round_trip`/`test_market_defaults`/`test_bar_close_wait` 到 `tdx`；新增 `tests/unit/test_tdx_source.py`。
5. 全量 `pytest`（`rdagent` 环境）+ 真实环境冒烟验证默认 A股标的日线/分钟线。
   回滚：保留 git 历史，误删可用 `git checkout` 恢复；未 commit 前不删工作区无关文件。

## Open Questions

- 港股代码（如 `00700`）前缀/市场号的完整规则是否需要覆盖所有分支（如北交所 `4/8`）？——不阻塞：默认只保证 A股（沪/深）与港股主板，其余在 `list_symbols` 明示“暂不支持”，后续按需扩展。