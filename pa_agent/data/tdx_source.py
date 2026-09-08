"""TDX (通达信) K-line data source built on ``easy-tdx``.

Provides A-share / HK K lines over free 通达信 public quote servers (MAC
protocol). No broker account or API key required. Network flakiness is mapped
to :class:`DataSourceTransientError` so the refresh loop can retry.

Market codes follow ``easy_tdx.models.enums.Market``: SZ=0, SH=1, BJ=2.
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any

from pa_agent.data.ashare_common import (
    PRESET_SYMBOLS as _PRESET_SYMBOLS,
    ashare_head_bar_live,
    normalize_ashare_symbol,
)
from pa_agent.data.base import DataSource, DataSourceTransientError
from pa_agent.data.kline_adjust import get_kline_adjust
from pa_agent.data.refresh_policy import snapshot_cache_ttl_s

logger = logging.getLogger(__name__)

# easy-tdx Market: 0=深圳(SZ), 1=上海(SH), 2=北京(BJ)
_SZ_MARKET, _SH_MARKET, _BJ_MARKET = 0, 1, 2

_SUPPORTED_TIMEFRAMES: tuple[str, ...] = (
    "1m",
    "5m",
    "15m",
    "30m",
    "1h",
    "1d",
    "1w",
    "1M",
)

_PRESET_SYMBOLS = _PRESET_SYMBOLS  # 000001 平安银行 / 600519 贵州茅台 / 指数

# easy-tdx write dir: keep out of the user's home and writable in sandbox.
_CONFIG_SUBDIR = os.path.join("logs", ".easy_tdx")


def tdx_config_dir() -> str:
    """A writable project-scoped dir for easy-tdx host cache (env override wins)."""
    return os.environ.get("EASY_TDX_CONFIG_DIR") or os.path.normpath(
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), _CONFIG_SUBDIR)
    )


# ── symbol → (market, code) ──────────────────────────────────────────────────


def resolve_tdx_symbol(symbol: str) -> tuple[str, int, str]:
    """Map a user *symbol* to (kind, market, code).

    kind ``a`` -> A-share ``get_stock_kline``; kind ``hk`` -> ``goods_kline``.
    Raises :class:`DataSourceTransientError` for gold / unsupported symbols.
    """
    sym = normalize_ashare_symbol(symbol)
    digits = re.sub(r"\D", "", sym)
    if len(digits) == 6:
        code = digits
        if code.startswith(("6", "5", "9")):
            return "a", _SH_MARKET, code
        if code.startswith(("0", "3", "2")):
            return "a", _SZ_MARKET, code
        if code.startswith(("4", "8", "920")):
            return "a", _BJ_MARKET, code
        raise DataSourceTransientError(f"TDX 不支持的 A股代码: {symbol!r}")
    if 1 <= len(digits) <= 5:
        from easy_tdx.mac.enums import ExMarket

        return "hk", int(ExMarket.HK_MAIN_BOARD), f"{int(digits):05d}"
    raise DataSourceTransientError(
        f"TDX 暂不支持标的 {symbol!r}（仅 A股 / 港股；黄金·外汇不在覆盖范围）"
    )


# ── period / adjust mapping ──────────────────────────────────────────────────


def _load_period_map() -> dict[str, Any]:
    from easy_tdx.mac.enums import Period

    return {
        "1m": Period.MIN_1,
        "5m": Period.MIN_5,
        "15m": Period.MIN_15,
        "30m": Period.MIN_30,
        "1h": Period.MIN_60,
        "1d": Period.DAILY,
        "1w": Period.WEEKLY,
        "1M": Period.MONTHLY,
    }


def _load_adjust_map() -> dict[str, Any]:
    from easy_tdx.mac.enums import Adjust

    return {"qfq": Adjust.QFQ, "hfq": Adjust.HFQ, "none": Adjust.NONE}


def to_period(timeframe: str, period_map: dict[str, Any]) -> Any:
    tf = (timeframe or "").strip()
    if tf not in period_map:
        raise ValueError(
            f"Unsupported timeframe: {timeframe!r}. Use one of {list(_SUPPORTED_TIMEFRAMES)}"
        )
    return period_map[tf]


# ── DataFrame → bars ─────────────────────────────────────────────────────────


def _df_to_rows_asc(df: Any) -> list[dict[str, Any]]:
    """Convert easy-tdx OHLCV DataFrame (ascending) to bar dict rows."""
    if df is None or getattr(df, "empty", True):
        return []
    time_col = "datetime" if "datetime" in df.columns else "date"
    from pa_agent.data.ashare_common import row_time_to_ts_ms

    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        rows.append(
            {
                "ts_open": int(row_time_to_ts_ms(row[time_col])),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row.get("vol", 0.0) or 0.0),
                "amount": float(row.get("amount", 0.0) or 0.0),
            }
        )
    return rows


def _rows_to_newest(rows_asc: list[dict[str, Any]], n: int, timeframe: str) -> list[dict[str, Any]]:
    rows = list(reversed(rows_asc[-n:]))
    live = ashare_head_bar_live(timeframe)
    for i, row in enumerate(rows):
        row["closed"] = not (i == 0 and live)
    return rows


# ── source ───────────────────────────────────────────────────────────────────


class TDXSource(DataSource):
    """A-share / HK K-line quotes via easy-tdx (通达信)."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout
        self._client: Any = None
        self._symbol: str = ""
        self._timeframe: str = ""
        self._connected: bool = False
        self._cache_key: tuple[str, str, str] | None = None
        self._cache_ts: float = 0.0
        self._cache_value: list[Any] = []

    # -- DataSource contract --------------------------------------------------

    def connect(self) -> None:
        try:
            from easy_tdx import UnifiedTdxClient  # noqa: F401
        except ImportError as exc:  # pragma: no cover - hard dependency in pyproject
            raise DataSourceTransientError("未安装 easy-tdx，请执行: pip install easy-tdx") from exc
        os.makedirs(tdx_config_dir(), exist_ok=True)
        os.environ["EASY_TDX_CONFIG_DIR"] = tdx_config_dir()
        self._connected = True
        logger.info("TDXSource connected (easy-tdx, config=%s)", tdx_config_dir())

    def disconnect(self) -> None:
        try:
            if self._client is not None:
                self._client.close()
        except Exception as exc:  # noqa: BLE001
            logger.debug("TDXSource close: %s", exc)
        self._client = None
        self._connected = False
        logger.info("TDXSource disconnected")

    def list_symbols(self) -> list[str]:
        return list(_PRESET_SYMBOLS)

    def supported_timeframes(self) -> list[str]:
        return list(_SUPPORTED_TIMEFRAMES)

    def subscribe(self, symbol: str, timeframe: str) -> None:
        period_map = _load_period_map()
        to_period(timeframe, period_map)  # validate timeframe first
        _kind, _market, code = resolve_tdx_symbol(symbol)
        self._symbol = code
        # 保留大小写以区分 1m(分钟) / 1M(月线)
        self._timeframe = (timeframe or "").strip()
        self._cache_key = None
        logger.info("TDXSource subscribed: %s %s", self._symbol, self._timeframe)

    def unsubscribe(self) -> None:
        self._symbol = ""
        self._timeframe = ""
        self._cache_key = None
        logger.info("TDXSource unsubscribed")

    def latest_snapshot(self, n: int) -> list[Any]:
        from pa_agent.data.ashare_common import rows_to_kline_bars

        if not self._connected:
            raise DataSourceTransientError("TDX 未连接")
        if not self._symbol or not self._timeframe:
            raise DataSourceTransientError("TDX 未订阅品种/周期")

        adjust = get_kline_adjust()
        cache_key = (self._symbol, self._timeframe, adjust)
        ttl = snapshot_cache_ttl_s(self._timeframe)
        now = time.monotonic()
        if (
            self._cache_key == cache_key
            and now - self._cache_ts < ttl
            and len(self._cache_value) >= n
        ):
            return self._cache_value[:n]

        period_map = _load_period_map()
        adjust_map = _load_adjust_map()
        period = to_period(self._timeframe, period_map)
        aadjust = adjust_map[adjust]

        fetch_n = max(n + 5, 30)
        try:
            kind, market, code = resolve_tdx_symbol(self._symbol)
            df = self._fetch_kline(kind, market, code, period, aadjust, fetch_n)
        except DataSourceTransientError:
            raise
        except Exception as exc:  # easy-tdx TdxError family → transient
            logger.warning("TDX fetch failed (%s): %s", self._symbol, exc)
            raise DataSourceTransientError(f"TDX 拉取失败: {exc}") from exc

        rows_asc = _df_to_rows_asc(df)
        if not rows_asc:
            raise DataSourceTransientError(f"TDX 未返回数据: {self._symbol} {self._timeframe}")
        rows_new = _rows_to_newest(rows_asc, fetch_n, self._timeframe)
        bars = rows_to_kline_bars(rows_new, n)

        self._cache_key = cache_key
        self._cache_ts = now
        self._cache_value = bars
        return bars[:n]

    # -- helpers --------------------------------------------------------------

    def _ensure_client(self) -> Any:
        from easy_tdx import UnifiedTdxClient

        if self._client is None:
            self._client = UnifiedTdxClient(timeout=self._timeout)
            self._client.connect()
        return self._client

    def _fetch_kline(
        self, kind: str, market: int, code: str, period: Any, aadjust: Any, n: int
    ) -> Any:
        client = self._ensure_client()
        if kind == "a":
            return client.get_stock_kline(market, code, period, count=n, adjust=aadjust)
        return client.goods_kline(market, code, period, count=n, adjust=aadjust)
