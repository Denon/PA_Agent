"""Default A-share identifiers and legacy gold/MT5/TV migration."""
from __future__ import annotations

# MT5（MetaTrader5）与 TradingView（tvdatafeed）链路已由 TDX 取代，黄金/外汇/加密货币
# 相关标识与探测逻辑随源码删除；此处仅保留 A股默认项与 legacy 状态迁移。

A_SHARE_DEFAULT_SYMBOL = "000001"
A_SHARE_DEFAULT_TIMEFRAME = "1h"


def _looks_like_ashare_code(code: str) -> bool:
    c = (code or "").strip().lower()
    if len(c) == 6 and c.isdigit():
        return True
    return c.startswith(("sh", "sz")) and len(c) >= 8 and c[2:].isdigit()


def normalize_gold_symbol_for_kind(kind: str, symbol: str) -> str:
    """Map a legacy/unknown name to the A-share default identifier for *kind*."""
    from pa_agent.data.ashare_common import normalize_ashare_symbol

    sym = (symbol or "").strip()
    code = normalize_ashare_symbol(sym)
    if not code or not _looks_like_ashare_code(code):
        return A_SHARE_DEFAULT_SYMBOL
    return code


def migrate_general_gold_defaults(general: dict) -> None:
    """In-place migration: gold/MT5/TV legacy state → TDX + A-share default."""
    kind = str(general.get("last_data_source", "tdx"))
    if kind in ("mt5", "tradingview", "mt5_hk", "tradingview_hk"):
        # MT5 / TradingView（含黄金）已由 TDX 替代：重置到 A股默认品种
        general["last_data_source"] = "tdx"
        general["last_symbol"] = A_SHARE_DEFAULT_SYMBOL
        general["last_timeframe"] = A_SHARE_DEFAULT_TIMEFRAME
        return
    sym = str(general.get("last_symbol", ""))
    general["last_symbol"] = normalize_gold_symbol_for_kind(kind, sym)