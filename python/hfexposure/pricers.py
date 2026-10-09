"""Analytic pricers used for full-revaluation stress tests (independent of the SA-CCR engine).

Simplifications (all intentional, see README):
- Zero curves: continuously compounded zero rates, linear interpolation on zero rates, flat extrapolation.
- IRS: single-curve discounting, annual fixed leg, float leg valued at par at the reset date
  (valuation date is treated as a reset date, so remaining accrual length must be whole years).
- FX: covered interest parity forwards; Garman-Kohlhagen options with constant vol.
- CDS: flat hazard rate, quarterly premium, no accrual on default, protection discounted at period midpoints.
"""
import math
from dataclasses import dataclass
from typing import Callable

from scipy.optimize import brentq
from scipy.stats import norm

CDS_PAYMENTS_PER_YEAR = 4
WHOLE_YEAR_TOL = 1e-9


@dataclass(frozen=True)
class ZeroCurve:
    tenors: tuple
    zeros: tuple

    def zero(self, t: float) -> float:
        ts, zs = self.tenors, self.zeros
        if t <= ts[0]:
            return zs[0]
        if t >= ts[-1]:
            return zs[-1]
        for i in range(len(ts) - 1):
            if ts[i] <= t <= ts[i + 1]:
                w = (t - ts[i]) / (ts[i + 1] - ts[i])
                return zs[i] * (1 - w) + zs[i + 1] * w
        raise ValueError("unreachable")

    def df(self, t: float) -> float:
        return math.exp(-self.zero(t) * t)

    def shifted(self, shock_fn: Callable[[float], float]) -> "ZeroCurve":
        """Add shock_fn(tenor) (decimal rate) to every pillar zero rate."""
        return ZeroCurve(self.tenors, tuple(z + shock_fn(t) for t, z in zip(self.tenors, self.zeros)))


def irs_payment_times(start: float, maturity: float) -> list:
    n = round(maturity - start)
    if n < 1 or abs((maturity - start) - n) > WHOLE_YEAR_TOL:
        raise ValueError(f"IRS accrual length must be a whole number of years, got {maturity - start}")
    return [start + i for i in range(1, n + 1)]


def irs_annuity(curve: ZeroCurve, start: float, maturity: float) -> float:
    return sum(curve.df(t) for t in irs_payment_times(start, maturity))


def irs_par_rate(curve: ZeroCurve, start: float, maturity: float) -> float:
    return (curve.df(start) - curve.df(maturity)) / irs_annuity(curve, start, maturity)


def irs_value_payer(notional: float, fixed_rate: float, start: float, maturity: float, curve: ZeroCurve) -> float:
    """Value to the fixed-rate payer: float leg N*(DF(S)-DF(T)) minus fixed leg N*K*annuity."""
    float_leg = notional * (curve.df(start) - curve.df(maturity))
    fixed_leg = notional * fixed_rate * irs_annuity(curve, start, maturity)
    return float_leg - fixed_leg


def fx_forward_rate(spot: float, df_base: float, df_quote: float) -> float:
    """Covered interest parity; spot is quote per 1 base."""
    return spot * df_base / df_quote


def fx_forward_value_quote(base_amount: float, strike: float, spot: float, t: float,
                           curve_base: ZeroCurve, curve_quote: ZeroCurve) -> float:
    """Value, in quote currency, of buying base_amount of base at `strike` on date t."""
    fwd = fx_forward_rate(spot, curve_base.df(t), curve_quote.df(t))
    return base_amount * (fwd - strike) * curve_quote.df(t)


def garman_kohlhagen_value_quote(base_amount: float, is_call: bool, spot: float, strike: float, vol: float,
                                 t: float, curve_base: ZeroCurve, curve_quote: ZeroCurve) -> float:
    """Garman-Kohlhagen value, in quote currency, of a long option on base_amount of base."""
    df_b, df_q = curve_base.df(t), curve_quote.df(t)
    r_b, r_q = -math.log(df_b) / t, -math.log(df_q) / t
    d1 = (math.log(spot / strike) + (r_q - r_b + 0.5 * vol ** 2) * t) / (vol * math.sqrt(t))
    d2 = d1 - vol * math.sqrt(t)
    if is_call:
        per_unit = spot * df_b * norm.cdf(d1) - strike * df_q * norm.cdf(d2)
    else:
        per_unit = strike * df_q * norm.cdf(-d2) - spot * df_b * norm.cdf(-d1)
    return base_amount * per_unit


def cds_grid(maturity: float) -> list:
    """Quarterly premium dates up to maturity (last period may be short)."""
    step = 1.0 / CDS_PAYMENTS_PER_YEAR
    n = math.ceil(maturity / step - WHOLE_YEAR_TOL)
    return [min(step * i, maturity) for i in range(1, n + 1)]


def cds_risky_annuity(hazard: float, maturity: float, curve: ZeroCurve) -> float:
    """Premium leg PV per unit running coupon and unit notional (no accrual on default)."""
    pv, prev = 0.0, 0.0
    for t in cds_grid(maturity):
        pv += (t - prev) * math.exp(-hazard * t) * curve.df(t)
        prev = t
    return pv


def cds_protection_leg(hazard: float, recovery: float, maturity: float, curve: ZeroCurve) -> float:
    """Protection leg PV per unit notional: (1-R) * sum of default-in-period probability * DF(midpoint)."""
    pv, prev = 0.0, 0.0
    for t in cds_grid(maturity):
        default_prob = math.exp(-hazard * prev) - math.exp(-hazard * t)
        pv += default_prob * curve.df(0.5 * (prev + t))
        prev = t
    return (1.0 - recovery) * pv


def cds_par_spread(hazard: float, recovery: float, maturity: float, curve: ZeroCurve) -> float:
    return cds_protection_leg(hazard, recovery, maturity, curve) / cds_risky_annuity(hazard, maturity, curve)


def cds_calibrate_hazard(par_spread: float, recovery: float, maturity: float, curve: ZeroCurve) -> float:
    """Flat hazard rate that reprices the market par spread (decimal, e.g. 0.012)."""
    return brentq(lambda h: cds_par_spread(h, recovery, maturity, curve) - par_spread, 1e-8, 5.0, xtol=1e-14)


def cds_value_buyer(notional: float, coupon: float, market_spread: float, recovery: float,
                    maturity: float, curve: ZeroCurve) -> float:
    """Value to the protection buyer: N * (protection leg - coupon * risky annuity)."""
    h = cds_calibrate_hazard(market_spread, recovery, maturity, curve)
    return notional * (cds_protection_leg(h, recovery, maturity, curve)
                       - coupon * cds_risky_annuity(h, maturity, curve))
