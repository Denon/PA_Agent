"""Construct :class:`DataSource` implementations by kind id."""
from __future__ import annotations

from typing import Literal

from pa_agent.data.base import DataSource
from pa_agent.data.market_defaults import A_SHARE_DEFAULT_SYMBOL

DataSourceKind = Literal[
    "tdx",
    "akshare",
    "eastmoney",
    "eastmoney_futures",
    "tushare",
]

# UI-visible sources — 可在界面下拉框直接选择。
# TDX 为默认数据源，排在首位；eastmoney 等仍可通过隐藏 kind 创建。
DATA_SOURCE_CHOICES: tuple[tuple[DataSourceKind, str], ...] = (
    ("tdx", "TDX"),
)

_HIDDEN_KINDS: frozenset[DataSourceKind] = frozenset(
    {"akshare", "tushare", "eastmoney", "eastmoney_futures"}
)

_DEFAULT_SYMBOLS: dict[DataSourceKind, str] = {
    "tdx": A_SHARE_DEFAULT_SYMBOL,
    "akshare": A_SHARE_DEFAULT_SYMBOL,
    "eastmoney": A_SHARE_DEFAULT_SYMBOL,
    "eastmoney_futures": "RB0 螺纹钢",
    "tushare": A_SHARE_DEFAULT_SYMBOL,
}


def default_tradingview_exchange() -> str:
    """Empty string = UI «（自动）» — probe all TV preset venues."""
    return ""


def normalize_data_source_kind(kind: str | None) -> DataSourceKind:
    """Return a supported data-source kind, defaulting to TDX."""
    supported = {k for k, _ in DATA_SOURCE_CHOICES} | _HIDDEN_KINDS
    if kind in supported:
        return kind  # type: ignore[return-value]
    return "tdx"


def data_source_label(kind: str | None) -> str:
    """Human-readable label for *kind*."""
    normalized = normalize_data_source_kind(kind)
    for key, label in DATA_SOURCE_CHOICES:
        if key == normalized:
            return label
    if normalized == "eastmoney":
        return "东方财富"
    if normalized == "eastmoney_futures":
        return "东方财富期货"
    if normalized == "tushare":
        return "Tushare(A股)"
    if normalized == "akshare":
        return "AkShare"
    return "TDX"


def default_symbol_for_kind(kind: str | None) -> str:
    return _DEFAULT_SYMBOLS[normalize_data_source_kind(kind)]


def create_data_source(kind: str | None) -> DataSource:
    """Instantiate a fresh data source for *kind* (not connected)."""
    normalized = normalize_data_source_kind(kind)
    if normalized == "tdx":
        from pa_agent.data.tdx_source import TDXSource

        return TDXSource()
    if normalized == "eastmoney":
        from pa_agent.data.eastmoney_source import EastMoneySource

        return EastMoneySource()
    if normalized == "eastmoney_futures":
        from pa_agent.data.eastmoney_futures_source import EastMoneyFuturesSource

        return EastMoneyFuturesSource()
    if normalized == "tushare":
        from pa_agent.config.paths import SETTINGS_JSON_PATH
        from pa_agent.config.settings import load_settings
        from pa_agent.data.tushare_source import TushareSource

        return TushareSource(settings=load_settings(SETTINGS_JSON_PATH))
    from pa_agent.data.akshare_source import AkShareSource

    return AkShareSource()
