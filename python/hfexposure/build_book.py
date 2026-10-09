"""Generate data/trades.csv. Rates, forward rates and MTMs come from the pricers, not hand-typed.

Fixed rates and strikes are set as offsets from par/forward/ATM so each trade starts off-market by a
chosen amount. Run from the python/ directory: py -3 -m hfexposure.build_book
"""
import csv

from . import config as cfg
from . import pricers as px
from .book import load_book, value_trade
from .market import BP, Market, load_market

MM = 1_000_000.0
RATE_DECIMALS = 5
FX_DECIMALS = {"USDJPY": 2}
DEFAULT_FX_DECIMALS = 4

# ---- Trade definitions (all synthetic) -----------------------------------------------------
# IRS: (id, ccy, position, notional USD mm, start_y, maturity_y, offset_bp in our favour: positive = starts with positive value to us); Long = pay fixed.
IRS = {
    "NS-A": [
        ("A-IRS-01", "USD", "Long", 400, 0, 5, 18), ("A-IRS-02", "USD", "Short", 250, 0, 2, -12),
        ("A-IRS-03", "USD", "Long", 300, 0, 10, 35), ("A-IRS-04", "USD", "Short", 150, 1, 6, -20),
        ("A-IRS-05", "EUR", "Long", 200, 0, 7, 25), ("A-IRS-06", "EUR", "Short", 180, 0, 3, -15),
        ("A-IRS-07", "GBP", "Long", 120, 0, 5, 30), ("A-IRS-08", "GBP", "Short", 90, 0, 10, -25),
        ("A-IRS-09", "JPY", "Long", 160, 0, 10, 40), ("A-IRS-10", "JPY", "Short", 100, 0, 5, -10),
    ],
    "NS-B": [
        ("B-IRS-01", "USD", "Long", 900, 0, 2, 8), ("B-IRS-02", "USD", "Short", 480, 0, 10, 5),
        ("B-IRS-03", "USD", "Long", 600, 0, 5, 12), ("B-IRS-04", "USD", "Short", 300, 0, 30, -6),
        ("B-IRS-05", "USD", "Long", 450, 0, 7, 20), ("B-IRS-06", "USD", "Short", 400, 0, 3, 3),
        ("B-IRS-07", "USD", "Long", 350, 2, 10, 14), ("B-IRS-08", "USD", "Short", 40, 0, 20, 4),
        ("B-IRS-09", "EUR", "Long", 500, 0, 10, 16), ("B-IRS-10", "EUR", "Short", 400, 0, 5, 4),
        ("B-IRS-11", "EUR", "Long", 300, 0, 2, 7), ("B-IRS-12", "EUR", "Short", 150, 0, 30, -5),
        ("B-IRS-13", "GBP", "Long", 350, 0, 10, 19), ("B-IRS-14", "GBP", "Short", 300, 0, 5, 5),
        ("B-IRS-15", "GBP", "Long", 200, 0, 2, 6), ("B-IRS-16", "GBP", "Short", 150, 0, 20, -4),
    ],
    "NS-C": [
        ("C-IRS-01", "USD", "Short", 120, 0, 5, -20), ("C-IRS-02", "USD", "Long", 80, 0, 3, 10),
        ("C-IRS-03", "USD", "Short", 90, 0, 7, -15), ("C-IRS-04", "EUR", "Short", 60, 0, 5, -12),
    ],
}
# FX forward: (id, pair, position, notional USD mm, maturity_y, offset % of forward in our favour); Long = long base.
FXF = {
    "NS-A": [
        ("A-FXF-01", "EURUSD", "Long", 150, 1.0, -1.2), ("A-FXF-02", "GBPUSD", "Short", 100, 0.5, 0.8),
        ("A-FXF-03", "USDJPY", "Long", 200, 1.0, -2.0), ("A-FXF-04", "AUDUSD", "Long", 80, 2.0, -1.5),
        ("A-FXF-05", "USDJPY", "Short", 120, 0.5, 1.0),
    ],
    "NS-B": [("B-FXF-01", "EURUSD", "Long", 150, 1.0, -0.4), ("B-FXF-02", "GBPUSD", "Short", 100, 2.0, 0.3)],
    "NS-C": [("C-FXF-01", "EURUSD", "Short", 40, 1.0, 0.6), ("C-FXF-02", "GBPUSD", "Long", 30, 0.5, -0.4)],
}
# FX option on XXXUSD pairs: (id, pair, position, call/put, notional USD mm, maturity_y, strike offset % of forward, vol).
FXO = {
    "NS-A": [
        ("A-FXO-01", "EURUSD", "Long", "Call", 120, 0.75, 3.0, 0.075),
        ("A-FXO-02", "GBPUSD", "Short", "Put", 80, 1.0, -2.5, 0.09),
        ("A-FXO-03", "AUDUSD", "Long", "Put", 60, 0.5, -3.0, 0.105),
    ],
    "NS-B": [],
    "NS-C": [("C-FXO-01", "EURUSD", "Long", "Put", 30, 0.5, -2.0, 0.08)],
}
# CDS: (id, name, position, notional USD mm, maturity_y, coupon bp, SA-CCR sub_category); Long = buy protection.
CDS = {
    "NS-A": [], "NS-B": [],
    "NS-C": [
        ("C-CDS-01", "DeltaRetail", "Short", 40, 5.0, 100, "BBB"),
        ("C-CDS-02", "OmegaTelecom", "Short", 35, 5.0, 100, "BBB"),
        ("C-CDS-03", "SigmaAutos", "Short", 30, 3.0, 100, "BBB"),
        ("C-CDS-04", "KappaChemicals", "Long", 25, 5.0, 100, "BBB"),
        ("C-CDS-05", "SigmaAutos", "Long", 20, 5.0, 100, "BBB"),
        ("C-CDS-06", "OmegaTelecom", "Short", 25, 7.0, 100, "BBB"),
        ("C-CDS-07", "CDX_IG", "Short", 150, 5.0, 100, "IG_Index"),
        ("C-CDS-08", "CDX_IG", "Long", 60, 3.0, 100, "IG_Index"),
        ("C-CDS-09", "CDX_HY", "Short", 80, 5.0, 500, "SubIG_Index"),
        ("C-CDS-10", "CDX_HY", "Long", 40, 3.0, 500, "SubIG_Index"),
        ("C-CDS-11", "DeltaRetail", "Long", 20, 3.0, 100, "BBB"),
        ("C-CDS-12", "KappaChemicals", "Short", 30, 3.0, 100, "BBB"),
    ],
}


def _row(**kw) -> dict:
    base = {c: "" for c in cfg.TRADE_COLUMNS}
    base[cfg.COL_OPT_TYPE] = "NA"
    base[cfg.COL_SUB_CATEGORY] = "NA"
    base[cfg.COL_STYLE] = "Linear"
    base[cfg.COL_START] = 0
    base.update(kw)
    return base


def _sgn(pos: str) -> float:
    return 1.0 if pos == "Long" else -1.0


def _fx_round(pair: str, x: float) -> float:
    return round(x, FX_DECIMALS.get(pair, DEFAULT_FX_DECIMALS))


def _fwd(m: Market, pair: str, t: float) -> float:
    return px.fx_forward_rate(m.spots[pair], m.curves[pair[:3]].df(t), m.curves[pair[3:]].df(t))


def build_rows(m: Market) -> list:
    rows = []
    for ns, items in IRS.items():
        for tid, ccy, pos, n, s, t, off in items:
            par = px.irs_par_rate(m.curves[ccy], s, t)
            rows.append(_row(**{cfg.COL_TRADE_ID: tid, cfg.COL_NETTING_SET: ns, cfg.COL_ASSET_CLASS: "IR",
                                cfg.COL_HEDGING_SET: ccy, cfg.COL_POSITION: pos, cfg.COL_NOTIONAL: n * MM,
                                cfg.COL_START: s, cfg.COL_MATURITY: t,
                                cfg.COL_FIXED_RATE: round(par - _sgn(pos) * off * BP, RATE_DECIMALS)}))
    for ns, items in FXF.items():
        for tid, pair, pos, n, t, off in items:
            rows.append(_row(**{cfg.COL_TRADE_ID: tid, cfg.COL_NETTING_SET: ns, cfg.COL_ASSET_CLASS: "FX",
                                cfg.COL_HEDGING_SET: pair, cfg.COL_POSITION: pos, cfg.COL_NOTIONAL: n * MM,
                                cfg.COL_MATURITY: t, cfg.COL_UNDERLYING: m.spots[pair],
                                cfg.COL_FIXED_RATE: _fx_round(pair, _fwd(m, pair, t) * (1 - _sgn(pos) * off / 100))}))
    for ns, items in FXO.items():
        for tid, pair, pos, typ, n, t, off, vol in items:
            rows.append(_row(**{cfg.COL_TRADE_ID: tid, cfg.COL_NETTING_SET: ns, cfg.COL_ASSET_CLASS: "FX",
                                cfg.COL_HEDGING_SET: pair, cfg.COL_POSITION: pos, cfg.COL_STYLE: "Option",
                                cfg.COL_OPT_TYPE: typ, cfg.COL_NOTIONAL: n * MM, cfg.COL_MATURITY: t,
                                cfg.COL_UNDERLYING: m.spots[pair], cfg.COL_VOL: vol,
                                cfg.COL_STRIKE: _fx_round(pair, _fwd(m, pair, t) * (1 + off / 100))}))
    for ns, items in CDS.items():
        for tid, name, pos, n, t, cpn, sub in items:
            rows.append(_row(**{cfg.COL_TRADE_ID: tid, cfg.COL_NETTING_SET: ns, cfg.COL_ASSET_CLASS: "Credit",
                                cfg.COL_HEDGING_SET: name, cfg.COL_POSITION: pos, cfg.COL_NOTIONAL: n * MM,
                                cfg.COL_MATURITY: t, cfg.COL_SUB_CATEGORY: sub, cfg.COL_COUPON_BP: cpn}))
    return rows


def _write(rows: list, path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cfg.TRADE_COLUMNS)
        w.writeheader()
        w.writerows(rows)


def _fill_mtm(rows: list, m: Market, path) -> None:
    """Write once with mtm=0 to reuse the loader, then reprice every trade and rewrite."""
    for r in rows:
        r[cfg.COL_MTM] = 0
    _write(rows, path)
    by_id = {r[cfg.COL_TRADE_ID]: r for r in rows}
    for bt in load_book(m, path, check_mtm=False):
        by_id[bt.trade.trade_id][cfg.COL_MTM] = round(value_trade(bt, m), 2)
    _write(rows, path)


def main() -> None:
    m = load_market()
    rows = build_rows(m)
    _fill_mtm(rows, m, cfg.TRADES_CSV)
    print(f"wrote {len(rows)} trades to {cfg.TRADES_CSV}")


if __name__ == "__main__":
    main()
