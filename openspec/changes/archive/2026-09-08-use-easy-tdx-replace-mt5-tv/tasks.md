## 1. 依赖调整

- [x] 1.1 在 `pyproject.toml` 的 dependencies 增加 `easy-tdx>=1.20.6`，删除 `MetaTrader5` 与 `tvdatafeed`；已在 `rdagent` 环境成功 `import easy_tdx`，`uv.lock` 已更新
- [x] 1.2 清理 README/config/README/settings.example 中 MetaTrader5、tvdatafeed、黄金 XAUUSD 相关依赖说明；`grep -ri 'MetaTrader5|tvdatafeed|XAUUSD' config/README.md` 无残留

## 2. 实现 TDXSource

- [x] 2.1 新增 `pa_agent/data/tdx_source.py`，实现 `DataSource` 全部抽象方法，内部用 `UnifiedTdxClient`；模块可导入、类可实例化
- [x] 2.2 实现标的→(市场,代码)解析（A股 6 位按前几位判沪/深/京、港股走 `ExMarket.HK_MAIN_BOARD`），黄金/无效代码抛 `DataSourceTransientError`；`test_tdx_source.py` 覆盖
- [x] 2.3 实现周期映射（1m/5m/15m/30m/1h/1d/1w/1M → `Period`），`supported_timeframes()` 返回；越界周期触发 `ValueError`；修复 `to_period` 大小写问题（1M 月线 vs 1m 分钟）
- [x] 2.4 实现 `latest_snapshot(n)`：`get_stock_kline`/`goods_kline`（复权取 `get_kline_adjust()`→`Adjust`），DataFrame 反转最新在前、`datetime`→`ts_open`(ms) 转 `KlineBar`，TTL 缓存复用 `snapshot_cache_ttl_s`；真实环境验证 `latest_snapshot` 返回非空 bars 且 `ts_open` 为 ms
- [x] 2.5 将 easy-tdx 网络/解析异常统一包装为 `DataSourceTransientError`；未连接/未订阅行为与东财源一致

## 3. 接入并设为默认

- [x] 3.1 `factory.py`：`DataSourceKind` 加 `"tdx"`，默认 kind 改为 `tdx`，`DATA_SOURCE_CHOICES` 设为 `tdx` 并置首位，`_DEFAULT_SYMBOLS`/`data_source_label` 落到 A股默认标的；`create_data_source("tdx")` 返回 `TDXSource`，`normalize_data_source_kind` 默认回落到 tdx
- [x] 3.2 `settings.py`：`DataSourceKind` Literal 加 `tdx`、删 mt5/tradingview，`last_data_source` 默认改 `tdx`，移除 `last_tradingview_exchange` 字段并清理 legacy 迁改；`test_settings_round_trip` 通过
- [x] 3.3 `market_defaults.py`：默认标的改用 A股 `000001`，`migrate_general_gold_defaults` 将 legacy mt5/tradingview/黄金状态重置为 tdx + A股默认标的；验证 `test_market_defaults` 通过、默认标的不再解析为 XAUUSD
- [x] 3.4 `app_context.py`：删除 tradingview 的 `set_exchange` 特殊分支，默认 fallback 改 `tdx`，仅按默认 kind 创建并订阅；`main_window.py` 默认回退也改 `tdx`/`000001`

## 4. 移除 MT5/TV 链路

- [x] 4.1 **完成源码删除**：删除 `pa_agent/data/mt5.py`、`tradingview.py`、`tradingview_connectivity.py`、`tradingview_errors.py`、`tv_symbol_lookup.py`、`pa_agent/gui/tv_connectivity_dialog.py`，以及 `tools/probe_mt5_clock_skew.py`、`config/tv_symbol_aliases.example.json`；并同步清理全部引用：
  - `main_window.py`：移除 TradingView 交易所下拉框 UI、`_tv_exchange_*`/`_on_tv_probe_status`/`_persist_tradingview_exchange`/`_ensure_tradingview_reachable` 等方法、`_on_fetch_data_clicked` 连通性检查、启动连通性检查、符号切换/状态提示/品种警告中的 TV/MT5 分支；`_current_data_source_kind` 默认回退由 `mt5` 改为 `tdx`。
  - `market_defaults.py`：删除全部 TV/gold/crypto 常量与函数（`TV_EXCHANGE_PRESETS`、`resolve_tv_*`、`tv_*probe_plan`、`GOLD_TV_*`、`infer_ashare_tv_exchange`、`is_partial_tv_symbol_input` 等），保留 `A_SHARE_DEFAULT_SYMBOL/TIMEFRAME`、`normalize_gold_symbol_for_kind`（仅 A股归一化）与精简后的 `migrate_general_gold_defaults`。
  - `bar_close_wait.py`：`_looks_like_ashare_symbol` 不再依赖已删的 `normalize_ashare_tv_code`。
  - 杂项注释：`base.py`/`snapshot.py`/`refresh_loop.py`/`datetime_ts.py` 中残留的 MT5/TradingView 说明改为中性表述。
  - 文档：`README.md`、`PA_Agent使用文档.md` 的数据源/品种/默认值改为 TDX + A股 `000001`。
  - 校验：`rg` 已确认 `pa_agent` 内不再引用任何已删模块或已删符号；`mv` 已确认 `tests` 内无残留引用；`py_compile` 全源码通过。
- [x] 4.2 **删除相关测试**：删除 `test_mt5_clock_skew.py`、`test_mt5_symbol_available.py`、`test_tradingview_connectivity.py`、`test_tradingview_errors.py`、`test_tradingview_socket.py`、`test_tv_symbol_lookup.py`；重写 `test_market_defaults.py` 只覆盖保留行为（A股默认、MT5/TV→tdx 迁移）。相关配置/数据源/刷新单测全部通过。

## 5. 测试与验证

- [x] 5.1 新增 `tests/unit/test_tdx_source.py`：覆盖周期映射、标的解析、DataFrame→rows 转换、`_rows_to_newest` 顺序/closed、gold 不支持；`pytest tests/unit/test_tdx_source.py` 通过
- [x] 5.2 调整 `test_data_source_factory.py`、`test_settings_round_trip.py`、`test_market_defaults.py` 中引用 mt5/tv 的断言到 `tdx`；这些测试全部通过
- [x] 5.3 数据源/配置相关单测全绿（56 passed）；全量 `pytest` 中其余 ERROR/FAIL 均为既有环境问题（`hypothesis` 未装、PyQt 环境依赖、openclaw provider/validation 等既有用例），与本变更无关。`.easy_tdx` 写目录已指向项目 `logs/.easy_tdx`。
- [x] 5.4 真实环境冒烟：`TDXSource` 对 000001(30m) 与 600519(1d) `latest_snapshot` 均返回非空 bars，`ts_open` 为毫秒时间戳，OHLCV 数值合理

## 6. 收尾

- [x] 6.1 `black` 校验新增文件 `tdx_source.py`/`test_tdx_source.py` 通过（"left unchanged"）；`ruff` 在 rdagent 环境未安装（未改动环境）。既有文件（factory/settings/market_defaults）在本变更前已非 black-clean，未做无关重排
- [x] 6.2 更新 `config/settings.json` 的 `last_data_source` → `tdx`、`last_symbol` → `000001`，并在 `settings.example.json` 同步；应用已默认以 tdx + A股标的启动