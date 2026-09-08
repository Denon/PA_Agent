## Why

当前应用的行情数据源默认依赖 MT5（MetaTrader5）和 TradingView（tvdatafeed），但用户现在无法使用这两者。`rdagent` 环境已安装 `easy-tdx`（直连通达信公开行情服务器的 TCP 库），能覆盖用户主要关注的 A股/港股行情。为摆脱对不可用数据源的依赖，改为以 `easy-tdx` 作为默认行情源，并移除 MT5 与 TradingView 的全部依赖。

## What Changes

- **新增 TDX 数据源**：新增 `pa_agent/data/tdx_source.py`，实现 `DataSource` 抽象接口，用 `easy_tdx.UnifiedTdxClient` 拉取 A股/港股 K 线并转换为项目 `KlineBar`。
- **默认数据源切换**（**BREAKING**）：默认数据源从 `mt5` 改为 `tdx`。
- **移除 MT5 依赖**（**BREAKING**）：从 `pyproject.toml` 删除 `MetaTrader5`；删除/停用 `pa_agent/data/mt5.py` 及其相关测试与工具。
- **移除 TradingView 依赖**（**BREAKING**）：从 `pyproject.toml` 删除 `tvdatafeed`；删除/停用 `tradingview*.py` 等模块及其连接性对话框与相关测试。
- **移除黄金链路**（**BREAKING**）：默认标的从黄金 `XAUUSD` 改为 A股默认标的（当前 `_DEFAULT_SYMBOLS` 中的 A股标的）。TDX 不提供现货黄金/外汇 CFD，黄金链路随之失效。
- **依赖声明固化**：在 `pyproject.toml` 增加 `easy-tdx>=1.20.6`。

## Capabilities

### New Capabilities
- `data/tdx-source`: 通过 `easy-tdx` 提供 A股/港股 K 线行情的能力，包括标的列表、时间框架支持、订阅/快照、数据源错误处理，并支持 A股复权（前复权/后复权）。

### Modified Capabilities
<!-- 现有 specs/ 目录为空，无既有能力需要增量修改 -->
（无既有 spec 需要增量修改；相应行为变更集中在 `data/tdx-source` 新能力及代码层的默认项切换。）

## Impact

- **代码**：`pa_agent/data/`（新增 `tdx_source.py`；删除 `mt5.py`、`tradingview.py`、`tradingview_connectivity.py`、`tradingview_errors.py`、`tv_symbol_lookup.py`）、`pa_agent/data/factory.py`、`pa_agent/data/market_defaults.py`、`pa_agent/data/bar_close_wait.py`、`pa_agent/config/settings.py`、`pa_agent/app_context.py`、`pa_agent/gui/main_window.py`、`pa_agent/gui/tv_connectivity_dialog.py`（删除）、`tools/probe_mt5_clock_skew.py`（删除）、`config/tv_symbol_aliases.example.json`（删除）。
- **依赖**：新增 `easy-tdx>=1.20.6`；移除 `MetaTrader5`、`tvdatafeed`。
- **测试**：新增 `tests/unit/test_tdx_source.py`（含复权、周期映射、错误重试）；调整/删除引用 MT5/TV 的测试（`test_mt5_*`、`test_tradingview_*`、`test_tv_symbol_lookup` 等）。
- **已知取舍**：不再支持现货黄金（XAUUSD）与外汇行情，这是用户明确的取舍（主要做 A股/港股）。
- **运行前提**：`easy-tdx` 连的是通达信公开行情服务器（免费、非官方 TCP），稳定性弱于专有数据源，接口层需复用项目既有 `DataSourceTransientError` 与刷新循环做失败重试。