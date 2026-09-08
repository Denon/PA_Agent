"""Unit tests for tdx_source pure helpers (no network)."""

from __future__ import annotations

import pandas as pd
import pytest
from unittest.mock import patch

from pa_agent.data.base import DataSourceTransientError
from pa_agent.data.tdx_source import (
    _SUPPORTED_TIMEFRAMES,
    _df_to_rows_asc,
    _rows_to_newest,
    resolve_tdx_symbol,
    to_period,
)

# ── resolve_tdx_symbol ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "symbol,expected",
    [
        ("000001", ("a", 0, "000001")),  # 深市
        ("600000", ("a", 1, "600000")),  # 沪市
        ("300750", ("a", 0, "300750")),  # 创业板
        ("688981", ("a", 1, "688981")),  # 科创板
        ("sh600519", ("a", 1, "600519")),
        ("00888", ("hk", None, "00888")),
    ],
)
def test_resolve_tdx_symbol(symbol, expected):
    kind, market, code = resolve_tdx_symbol(symbol)
    assert kind == expected[0]
    assert code == expected[2]
    if expected[1] is not None:
        assert market == expected[1]


def test_resolve_tdx_symbol_rejects_gold():
    with pytest.raises(DataSourceTransientError):
        resolve_tdx_symbol("XAUUSD")


# ── to_period ─────────────────────────────────────────────────────────────────


def test_to_period_maps_all_supported_timeframes():
    from easy_tdx.mac.enums import Period

    from pa_agent.data.tdx_source import _load_period_map

    pm = _load_period_map()
    expected = {
        "1m": Period.MIN_1,
        "5m": Period.MIN_5,
        "15m": Period.MIN_15,
        "30m": Period.MIN_30,
        "1h": Period.MIN_60,
        "1d": Period.DAILY,
        "1w": Period.WEEKLY,
        "1M": Period.MONTHLY,
    }
    for tf in _SUPPORTED_TIMEFRAMES:
        assert to_period(tf, pm) == expected[tf]


def test_to_period_rejects_unsupported():
    from easy_tdx.mac.enums import Period

    with pytest.raises(ValueError):
        to_period("4h", {"1h": Period.MIN_60})


# ── _df_to_rows_asc ───────────────────────────────────────────────────────────


def _make_df():
    return pd.DataFrame(
        {
            "datetime": pd.to_datetime(["2026-09-04 10:00", "2026-09-04 10:05"]),
            "open": [10.0, 10.1],
            "high": [10.2, 10.3],
            "low": [9.9, 10.05],
            "close": [10.1, 10.2],
            "vol": [100.0, 150.0],
            "amount": [1010.0, 1520.0],
        }
    )


def test_df_to_rows_asc_converts_columns():
    rows = _df_to_rows_asc(_make_df())
    assert len(rows) == 2
    r = rows[0]
    assert set(r) == {"ts_open", "open", "high", "low", "close", "volume", "amount"}
    assert r["close"] == 10.1
    assert r["volume"] == 100.0
    assert r["amount"] == 1010.0
    assert isinstance(r["ts_open"], int)


def test_df_to_rows_asc_empty():
    assert _df_to_rows_asc(pd.DataFrame()) == []
    assert _df_to_rows_asc(None) == []


# ── _rows_to_newest ───────────────────────────────────────────────────────────


def test_rows_to_newest_latest_first_all_closed_when_dead_board():
    rows_asc = [
        {
            "ts_open": 1,
            "open": 1.0,
            "high": 1.0,
            "low": 1.0,
            "close": 1.0,
            "volume": 0,
            "amount": 0,
        },
        {
            "ts_open": 2,
            "open": 2.0,
            "high": 2.0,
            "low": 2.0,
            "close": 2.0,
            "volume": 0,
            "amount": 0,
        },
        {
            "ts_open": 3,
            "open": 3.0,
            "high": 3.0,
            "low": 3.0,
            "close": 3.0,
            "volume": 0,
            "amount": 0,
        },
    ]
    with patch("pa_agent.data.tdx_source.ashare_head_bar_live", return_value=False):
        out = _rows_to_newest(rows_asc, 3, "30m")
    assert [r["ts_open"] for r in out] == [3, 2, 1]  # 最新在前
    assert all(r["closed"] for r in out)


def test_rows_to_newest_truncates_n():
    rows_asc = [
        {"ts_open": i, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 0, "amount": 0}
        for i in range(1, 8)
    ]
    with patch("pa_agent.data.tdx_source.ashare_head_bar_live", return_value=False):
        out = _rows_to_newest(rows_asc, 3, "5m")
    assert len(out) == 3
