## Purpose

通过 `easy-tdx`（通达信公开行情服务器）为系统提供 A股与港股的 K 线行情数据能力，替代原先依赖 MT5 与 TradingView 的行情接入，成为可用的默认数据源。

## Requirements

### Requirement: TDX 数据源可连接与断开
系统 SHALL 能够建立并释放与通达信行情服务器的连接，连接失败或中断时不阻塞应用启动，仅记录并可通过既有重试机制恢复。

#### Scenario: 初始化连接
- **WHEN** 应用启动并选定 TDX 为数据源
- **THEN** 系统建立行情连接并订阅当前默认标的与周期；若连接失败则记录告警而不中断启动

#### Scenario: 连接/订阅失败
- **WHEN** 通达信服务器不可达或返回空数据
- **THEN** 系统将此类可恢复故障归为瞬态错误（transient error），交由刷新/重试流程处理

### Requirement: 拉取 A股/港股 K 线
系统 SHALL 支持通过 TDX 数据源拉取 A股与港股的 K 线，按序号排列（索引 0 为最新、包含当前未收盘的一根），并映射为标准 bar 结构（ts_open、open、high、low、close、volume、amount）。

#### Scenario: 返回最近 N 根 bar
- **WHEN** 请求某 A股/港股标的在指定周期的最近 N 根 K 线
- **THEN** 返回恰为 N 根的 bar 列表，索引 0 为最新、按时间倒序，ohclv 与成交额齐全

#### Scenario: 标准 bar 字段
- **WHEN** 交易日 bar 从数据源返回
- **THEN** 每根 bar 的时间戳为 bar 开始时刻（ms），并携带 open/high/low/close/volume/amount，且 low ≤ close ≤ high

### Requirement: 支持的时间框架
系统 SHALL 支持 1、5、15、30、60 分钟以及日、周、月定期 K 线周期。

#### Scenario: 周期映射到指定周期
- **WHEN** 请求 1m/5m/15m/30m/60m/1d/1w/1mo 中任一周期
- **THEN** 返回对应周期的 K 线，并正确标注周期标识

### Requirement: A股复权处理
系统 SHALL 根据设定的复权方式（前复权 QFQ / 后复权 HFQ / 不复权 NONE）返回对应价格的日线与分钟线，复权设置对 A股有效。

#### Scenario: 前复权日线
- **WHEN** 复权设置为前复权并拉取某 A股日线
- **THEN** 返回的收盘价已按除权除息修正，连续价格平滑可比

#### Scenario: 不复权
- **WHEN** 复权设置为不复权
- **THEN** 返回交易所原始价格，不进行除权修正

### Requirement: 不支持的标的类型
系统 SHALL 对当前 TDX 数据源不覆盖的标的（现货黄金 XAUUSD、外汇 CFD 等）给出明确的“标的不可用”标识，而不是返回空或错误行情。

#### Scenario: 请求黄金标的
- **WHEN** 用户请求现货黄金（XAUUSD）等非 A股/港股标的
- **THEN** 系统返回该标的不可用/不支持，且不会将其作为默认标的自动订阅

### Requirement: 默认标的与周期
系统 SHALL 在未显式指定时，为 TDX 数据源提供 A股默认标的与默认周期。

#### Scenario: 默认情况下订阅默认 A股标的
- **WHEN** 用户未配置标的而选定 TDX 数据源
- **THEN** 系统使用 A股默认标的（而非黄金）作为初始订阅对象

### Requirement: 标的列表
系统 SHALL 能返回当前 TDX 数据源可用的标的集合或说明，供调用方查询与校验标的标识。

#### Scenario: 查询可用标的
- **WHEN** 调用方查询可选标的
- **THEN** 系统返回可用的标的清单或覆盖范围说明（A股/港股等），不返回原有的 MT5/TV 专用标的列表