"""Independent re-derivation of SA-CCR EAD from trades.csv (does not call the vendored SA-CCR code).

Formulas follow BIS d279: margined maturity factor 1.5 sqrt(MPOR/250), supervisory duration, IR three-bucket
aggregation with correlations 0.7/0.7/0.3, FX hedging sets by pair, credit entities netted then combined with
single-name / index correlations. Supervisory factors are typed here independently of the vendored params file.
"""
import csv
import math
from collections import defaultdict

import pytest
from pytest import approx
from scipy.stats import norm

from hfexposure import config as cfg
from hfexposure.run import run_all

SF = {"IR": 0.005, "FX": 0.04, "BBB": 0.0054, "IG_Index": 0.0038, "SubIG_Index": 0.0106}
RHO_SINGLE, RHO_INDEX = 0.5, 0.8
ALPHA, FLOOR = 1.4, 0.05


def _delta(r):
    sign = 1.0 if r[cfg.COL_POSITION] == "Long" else -1.0
    if r[cfg.COL_STYLE] == "Linear":
        return sign
    s, k, v, t = (float(r[c]) for c in (cfg.COL_UNDERLYING, cfg.COL_STRIKE, cfg.COL_VOL, cfg.COL_MATURITY))
    d1 = (math.log(s / k) + 0.5 * v * v * t) / (v * math.sqrt(t))
    if r[cfg.COL_OPT_TYPE] == "Call":
        return sign * norm.cdf(d1)
    return -sign * norm.cdf(-d1)


def independent_ead(netting_set: str, mpor_days: int, v: float, c: float, th: float, mta: float, nica: float):
    mf = 1.5 * math.sqrt(max(mpor_days, 10) / 250.0)
    ir = defaultdict(lambda: [0.0, 0.0, 0.0])
    fx = defaultdict(float)
    credit = defaultdict(float)
    credit_cat = {}
    with open(cfg.TRADES_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r[cfg.COL_NETTING_SET] != netting_set:
                continue
            n, s, e = float(r[cfg.COL_NOTIONAL]), float(r[cfg.COL_START]), float(r[cfg.COL_MATURITY])
            d = _delta(r)
            ac, hs = r[cfg.COL_ASSET_CLASS], r[cfg.COL_HEDGING_SET]
            if ac == "IR":
                sd = (math.exp(-0.05 * s) - math.exp(-0.05 * e)) / 0.05
                bucket = 0 if e < 1 else (1 if e <= 5 else 2)
                ir[hs][bucket] += d * n * sd * mf
            elif ac == "FX":
                fx[hs] += d * n * mf
            else:
                sd = (math.exp(-0.05 * s) - math.exp(-0.05 * e)) / 0.05
                credit[hs] += d * n * sd * mf
                credit_cat[hs] = r[cfg.COL_SUB_CATEGORY]
    addon = 0.0
    for b1, b2, b3 in ir.values():
        addon += SF["IR"] * math.sqrt(b1 * b1 + b2 * b2 + b3 * b3 + 1.4 * b1 * b2 + 1.4 * b2 * b3 + 0.6 * b1 * b3)
    addon += sum(SF["FX"] * abs(x) for x in fx.values())
    if credit:
        sum_rho, sum_idio = 0.0, 0.0
        for name, eff in credit.items():
            cat = credit_cat[name]
            rho = RHO_INDEX if "Index" in cat else RHO_SINGLE
            x = SF[cat] * eff
            sum_rho += rho * x
            sum_idio += (1 - rho ** 2) * x * x
        addon += math.sqrt(sum_rho ** 2 + sum_idio)
    mult = 1.0 if addon <= 0 else min(1.0, FLOOR + (1 - FLOOR) * math.exp((v - c) / (2 * (1 - FLOOR) * addon)))
    rc = max(v - c, th + mta - nica, 0.0)
    return ALPHA * (rc + mult * addon), addon


@pytest.mark.parametrize("ns", ["NS-A", "NS-B", "NS-C"])
def test_ead_matches_independent_derivation(ns):
    r = next(x for x in run_all() if x.fund.netting_set == ns)
    m, t = r.metrics, r.csa.terms
    ead, addon = independent_ead(ns, r.csa.mpor_days, m.mtm, m.vm_held + m.im_held, t.threshold, t.mta, m.im_held)
    assert m.saccr.addon.aggregate == approx(addon, rel=1e-9)
    assert m.saccr.ead == approx(ead, rel=1e-9)
