"""Per-netting-set SA-CCR EAD, SIMM IM and CSA margin call, using the vendored engines."""
import csv
from dataclasses import dataclass
from pathlib import Path

from vendor.csa.engine import MarginCallResult, compute_margin_call
from vendor.csa.terms import CSATerms
from vendor.saccr.ead import ScenarioResult, run_scenario
from vendor.saccr.engine import compute_trade_calc
from vendor.saccr.params import SupervisoryParams
from vendor.simm.engine import SIMMResult, compute_simm_im

from . import config as cfg


@dataclass(frozen=True)
class Fund:
    netting_set: str
    counterparty: str
    strategy: str
    nav: float
    leverage: float
    rating: str


@dataclass(frozen=True)
class CsaRow:
    terms: CSATerms
    margin_frequency: str
    mpor_days: int
    im_regime: str


def load_funds(path: Path = cfg.FUNDS_CSV) -> dict:
    with open(path, newline="", encoding="utf-8") as f:
        return {r[cfg.COL_NETTING_SET]: Fund(r[cfg.COL_NETTING_SET], r[cfg.COL_COUNTERPARTY], r[cfg.COL_STRATEGY],
                                             float(r[cfg.COL_NAV]), float(r[cfg.COL_LEVERAGE]), r[cfg.COL_RATING])
                for r in csv.DictReader(f)}


def load_csa(funds: dict, path: Path = cfg.CSA_CSV) -> dict:
    with open(path, newline="", encoding="utf-8") as f:
        out = {}
        for r in csv.DictReader(f):
            ns = r[cfg.COL_NETTING_SET]
            terms = CSATerms(ns, funds[ns].counterparty, float(r[cfg.COL_THRESHOLD]), float(r[cfg.COL_MTA]),
                             float(r[cfg.COL_IA]), float(r[cfg.COL_POSTED_VM]), float(r[cfg.COL_POSTED_IM]))
            out[ns] = CsaRow(terms, r[cfg.COL_MARGIN_FREQ], int(r[cfg.COL_MPOR_DAYS]), r[cfg.COL_IM_REGIME])
        return out


@dataclass
class ExposureMetrics:
    netting_set: str
    mtm: float
    simm: SIMMResult
    call: MarginCallResult
    vm_held: float              # after today's call
    im_held: float
    collateral: float
    current_exposure_gross: float   # max(V, 0)
    current_exposure_net: float     # max(V - C, 0)
    saccr: ScenarioResult


def compute_exposure(ns: str, trades: list, mtm: float, csa: CsaRow) -> ExposureMetrics:
    """trades: vendored Trade objects of the netting set; mtm: repriced netting-set value."""
    simm = compute_simm_im(trades, ns)
    model_im = simm.total_im if csa.im_regime == cfg.IM_REGIME_SIMM else 0.0
    call = compute_margin_call(mtm, model_im, csa.terms)
    vm_held = csa.terms.posted_vm + call.vm_call
    im_held = csa.terms.posted_im + call.im_call
    collateral = vm_held + im_held
    # SA-CCR MPOR: BIS floor is 10 business days for non-cleared margined sets.
    params = SupervisoryParams(mpor_floor_bd=max(10, csa.mpor_days))
    calcs = [compute_trade_calc(t, params) for t in trades]
    saccr = run_scenario("Actual - Margined", ns, calcs, v=mtm, c=collateral, th=csa.terms.threshold,
                         mta=csa.terms.mta, nica=im_held, margined=True, params=params)
    return ExposureMetrics(ns, mtm, simm, call, vm_held, im_held, collateral,
                           max(mtm, 0.0), max(mtm - collateral, 0.0), saccr)
