"""Tests for data source factory and settings."""
from __future__ import annotations

from pa_agent.config.settings import GeneralSettings
from pa_agent.data.factory import (
    DATA_SOURCE_CHOICES,
    create_data_source,
    default_symbol_for_kind,
    default_tradingview_exchange,
    normalize_data_source_kind,
)
from pa_agent.data.eastmoney_source import EastMoneySource
from pa_agent.data.tdx_source import TDXSource
from pa_agent.data.tushare_source import TushareSource


def test_normalize_data_source_kind_defaults_unknown():
    assert normalize_data_source_kind("invalid") == "tdx"
    assert normalize_data_source_kind(None) == "tdx"
    # legacy MT5 / TradingView 一律回退到 TDX
    assert normalize_data_source_kind("mt5") == "tdx"
    assert normalize_data_source_kind("tradingview") == "tdx"


def test_normalize_data_source_kind_hidden_sources():
    assert normalize_data_source_kind("akshare") == "akshare"
    assert normalize_data_source_kind("eastmoney") == "eastmoney"
    assert normalize_data_source_kind("tushare") == "tushare"


def test_tdx_in_ui_choices():
    """TDX 为默认数据源, 必须在 UI 可选列表中且排首位。"""
    ui_kinds = {k for k, _ in DATA_SOURCE_CHOICES}
    assert "tdx" in ui_kinds
    assert DATA_SOURCE_CHOICES[0][0] == "tdx"
    # eastmoney / AkShare / tushare 仍是隐藏源
    assert "eastmoney" not in ui_kinds
    assert "akshare" not in ui_kinds
    assert "tushare" not in ui_kinds


def test_tushare_not_in_ui_choices():
    ui_kinds = {k for k, _ in DATA_SOURCE_CHOICES}
    assert "tushare" not in ui_kinds


def test_create_data_source_returns_expected_types():
    assert isinstance(create_data_source("tdx"), TDXSource)
    assert isinstance(create_data_source("mt5"), TDXSource)  # legacy → tdx
    assert isinstance(create_data_source("tradingview"), TDXSource)  # legacy → tdx
    assert isinstance(create_data_source("eastmoney"), EastMoneySource)
    assert isinstance(create_data_source("tushare"), TushareSource)


def test_default_symbols_per_kind():
    assert default_symbol_for_kind("tdx") == "000001"
    assert default_symbol_for_kind("eastmoney") == "000001"
    assert default_symbol_for_kind("tushare") == "000001"


def test_default_tradingview_exchange_is_auto():
    assert default_tradingview_exchange() == ""


def test_general_settings_last_data_source_default():
    g = GeneralSettings()
    assert g.last_data_source == "tdx"
    assert g.last_symbol == "000001"