"""Trade book: loads trades.csv, values each trade with the analytic pricers, nets by netting set."""
import csv
from dataclasses import dataclass
from pathlib import Path

from vendor.saccr.trades import Trade, load_trades

from . import config as cfg
from .market import BP, Market, USD
from . import pricers as px


@dataclass(frozen=True)
class BookTrade:
    trade: Trade                 # vendored SA-CCR/SIMM trade (carries the CSV MTM)
    contract_rate: float         # IRS fixed rate, FX forward rate, or unused
    coupon: float                # CDS running coupon (decimal)
    local_notional: float        # IRS notional in trade currency, FX base-currency amount, or CDS notional


def _sign(t: Trade) -> float:
    return 1.0 if t.position == "Long" else -1.0


def _local_notional(t: Trade, contract_rate: float, m: Market) -> float:
    if t.asset_class == "IR":
        return t.notional / m.usd_per_ccy(t.hedging_set)
    if t.asset_class == "FX":
        base, quote = t.hedging_set[:3], t.hedging_set[3:]
        if base == USD:
            return t.notional
        ref = t.underlying_price if t.style == "Option" else contract_rate
        return t.notional / ref   # notional is USD, so base amount = USD / (USD per base)
    return t.notional


def load_book(m: Market, trades_csv: Path = cfg.TRADES_CSV, check_mtm: bool = True) -> list:
    trades = load_trades(str(trades_csv))
    with open(trades_csv, newline="", encoding="utf-8") as f:
        extras = {r[cfg.COL_TRADE_ID]: r for r in csv.DictReader(f)}
    book = []
    for t in trades:
        row = extras[t.trade_id]
        rate = float(row[cfg.COL_FIXED_RATE]) if row[cfg.COL_FIXED_RATE] else 0.0
        coupon = float(row[cfg.COL_COUPON_BP]) * BP if row[cfg.COL_COUPON_BP] else 0.0
        book.append(BookTrade(t, rate, coupon, _local_notional(t, rate, m)))
    if check_mtm:
        for bt in book:
            fresh = value_trade(bt, m)
            if abs(fresh - bt.trade.mtm) > cfg.PRICING_TOLERANCE_USD:
                raise ValueError(f"{bt.trade.trade_id}: CSV mtm {bt.trade.mtm} != repriced {fresh:.4f}")
    return book


def value_trade(bt: BookTrade, m: Market) -> float:
    """USD value to us (the dealer) of the trade under market state m."""
    t = bt.trade
    s = _sign(t)
    if t.asset_class == "IR":
        ccy = t.hedging_set
        v_local = px.irs_value_payer(bt.local_notional, bt.contract_rate, t.start_s, t.maturity_m, m.curves[ccy])
        return s * v_local * m.usd_per_ccy(ccy)
    if t.asset_class == "FX":
        pair = t.hedging_set
        base, quote = pair[:3], pair[3:]
        spot = m.spots[pair]
        if t.style == "Linear":
            v_quote = px.fx_forward_value_quote(bt.local_notional, bt.contract_rate, spot, t.maturity_m,
                                                m.curves[base], m.curves[quote])
        else:
            v_quote = px.garman_kohlhagen_value_quote(bt.local_notional, t.opt_type == "Call", spot, t.strike,
                                                      t.vol, t.maturity_m, m.curves[base], m.curves[quote])
        return s * v_quote * m.usd_per_ccy(quote)
    if t.asset_class == "Credit":
        q = m.cds[t.hedging_set]
        v = px.cds_value_buyer(t.notional, bt.coupon, q["spread"], q["recovery"], t.maturity_m, m.curves[USD])
        return s * v
    raise ValueError(f"unsupported asset class {t.asset_class}")


def netting_set_value(book: list, m: Market) -> float:
    return sum(value_trade(bt, m) for bt in book)


def by_netting_set(book: list) -> dict:
    out: dict = {}
    for bt in book:
        out.setdefault(bt.trade.netting_set, []).append(bt)
    return out
