"""A-share default symbol / legacy MT5-TradingView migration."""
from __future__ import annotations

from pa_agent.data.market_defaults import (
    A_SHARE_DEFAULT_SYMBOL,
    A_SHARE_DEFAULT_TIMEFRAME,
    migrate_general_gold_defaults,
    normalize_gold_symbol_for_kind,
)


def test_crypto_symbol_migrates_to_ashare_default():
    # 非 A股/空输入一律回退到 A股默认品种（无所谓数据源 kind）
    assert normalize_gold_symbol_for_kind("tdx", "BTCUSD") == A_SHARE_DEFAULT_SYMBOL
    assert normalize_gold_symbol_for_kind("tdx", "") == A_SHARE_DEFAULT_SYMBOL
    assert normalize_gold_symbol_for_kind("akshare", "XAUUSD") == A_SHARE_DEFAULT_SYMBOL
    assert normalize_gold_symbol_for_kind("tdx", "600519") == "600519"


def test_ashare_default_constants():
    assert A_SHARE_DEFAULT_SYMBOL == "000001"
    assert A_SHARE_DEFAULT_TIMEFRAME == "1h"


def test_migrate_legacy_mt5_and_tradingview_map_to_tdx():
    # MT5 / TradingView（含黄金）已由 TDX 替代：重置为 A股默认品种
    general = {
        "last_data_source": "tradingview",
        "last_symbol": "XAUUSD",
    }
    migrate_general_gold_defaults(general)
    assert general["last_data_source"] == "tdx"
    assert general["last_symbol"] == A_SHARE_DEFAULT_SYMBOL
    assert general["last_timeframe"] == A_SHARE_DEFAULT_TIMEFRAME

    general = {
        "last_data_source": "mt5",
        "last_symbol": "XAUUSDm",
    }
    migrate_general_gold_defaults(general)
    assert general["last_data_source"] == "tdx"
    assert general["last_symbol"] == A_SHARE_DEFAULT_SYMBOL


def test_migrate_tdx_garbage_symbol_falls_back_to_ashare_default():
    general = {"last_data_source": "tdx", "last_symbol": "XAUUSD"}
    migrate_general_gold_defaults(general)
    assert general["last_data_source"] == "tdx"
    assert general["last_symbol"] == A_SHARE_DEFAULT_SYMBOL


def test_migrate_tdx_valid_ashare_symbol_preserved():
    general = {"last_data_source": "tdx", "last_symbol": "600519"}
    migrate_general_gold_defaults(general)
    assert general["last_symbol"] == "600519"
    assert general["last_data_source"] == "tdx"