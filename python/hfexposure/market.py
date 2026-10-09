"""Market state: zero curves, FX spots, CDS par spreads; and scenario shocks applied to it."""
import json
from dataclasses import dataclass, field, replace
from pathlib import Path

from . import config as cfg
from .pricers import ZeroCurve

USD = "USD"
BP = 1e-4


@dataclass(frozen=True)
class Market:
    curves: dict                 # ccy -> ZeroCurve
    spots: dict                  # pair "EURUSD" -> quote per base
    cds: dict                    # name -> {"spread": decimal, "recovery": decimal}

    def usd_per_ccy(self, ccy: str) -> float:
        """USD value of one unit of ccy (pairs are XXXUSD or USDXXX only)."""
        if ccy == USD:
            return 1.0
        if f"{ccy}{USD}" in self.spots:
            return self.spots[f"{ccy}{USD}"]
        return 1.0 / self.spots[f"{USD}{ccy}"]


def load_market(path: Path = cfg.MARKET_JSON) -> Market:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    tenors = tuple(raw["tenors"])
    curves = {ccy: ZeroCurve(tenors, tuple(z * 0.01 for z in zs)) for ccy, zs in raw["zero_rates_pct"].items()}
    cds = {n: {"spread": v["spread_bp"] * BP, "recovery": v["recovery"]} for n, v in raw["cds"].items()}
    return Market(curves, dict(raw["spots"]), cds)


@dataclass(frozen=True)
class Scenario:
    name: str
    rates_parallel_bp: float = 0.0
    rates_curve_bp: tuple = ()        # ((tenor, bp), ...)
    usd_pct: float = 0.0
    spread_bp: float = 0.0

    def scaled(self, k: float, name: str = None) -> "Scenario":
        return Scenario(name or self.name, self.rates_parallel_bp * k,
                        tuple((t, b * k) for t, b in self.rates_curve_bp), self.usd_pct * k, self.spread_bp * k)


def scenario_from_dict(d: dict) -> Scenario:
    curve = tuple(sorted(d.get("rates_curve_bp", {}).items()))
    return Scenario(d["name"], d.get("rates_parallel_bp", 0.0), curve, d.get("usd_pct", 0.0), d.get("spread_bp", 0.0))


def _curve_shock_fn(sc: Scenario):
    pts = sc.rates_curve_bp

    def shock(t: float) -> float:
        bp = sc.rates_parallel_bp
        if pts:
            if t <= pts[0][0]:
                bp += pts[0][1]
            elif t >= pts[-1][0]:
                bp += pts[-1][1]
            else:
                for (t0, b0), (t1, b1) in zip(pts, pts[1:]):
                    if t0 <= t <= t1:
                        bp += b0 + (b1 - b0) * (t - t0) / (t1 - t0)
                        break
        return bp * BP
    return shock


def _shock_fx_spot(pair: str, spot: float, usd_pct: float) -> float:
    """USD up x%: quote-per-base falls for XXXUSD (USD is the quote), rises for USDXXX."""
    if usd_pct == 0.0:
        return spot
    return spot / (1.0 + usd_pct) if pair.endswith(USD) else spot * (1.0 + usd_pct)


def _shock_spread(spread: float, shock_bp: float) -> float:
    if shock_bp == 0.0:
        return spread
    floor = min(spread, cfg.MIN_SPREAD_BP * BP)
    return max(spread + shock_bp * BP, floor)


def apply_scenario(m: Market, sc: Scenario) -> Market:
    fn = _curve_shock_fn(sc)
    curves = {c: cv.shifted(fn) for c, cv in m.curves.items()}
    spots = {p: _shock_fx_spot(p, s, sc.usd_pct) for p, s in m.spots.items()}
    cds = {n: {**v, "spread": _shock_spread(v["spread"], sc.spread_bp)} for n, v in m.cds.items()}
    return replace(m, curves=curves, spots=spots, cds=cds)
