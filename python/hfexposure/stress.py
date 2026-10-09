"""Full-revaluation stress tests per netting set, including the MPOR gap scenario."""
import itertools
import math
from dataclasses import dataclass

from . import config as cfg
from .book import netting_set_value
from .market import Market, Scenario, apply_scenario, scenario_from_dict


@dataclass(frozen=True)
class StressRow:
    scenario: str
    detail: str                 # which sign combination was binding, if any
    stressed_mtm: float
    pnl: float
    collateral_held: float
    exposure: float             # max(stressed MTM - collateral, 0), netted at netting-set level
    exposure_before_im: float   # same, but with only VM counted as collateral (informational)


def _combo_scenarios(scale: float, prefix: str) -> list:
    axes = cfg.COMBINED_AXES
    names = list(axes)
    out = []
    for combo in itertools.product(*(axes[n] for n in names)):
        kw = dict(zip(names, combo))
        label = ", ".join(f"{n}={v:+g}" for n, v in kw.items())
        out.append(Scenario(f"{prefix} [{label}]", **kw).scaled(scale))
    return out


def exposure_after_collateral(mtm: float, collateral: float) -> float:
    return max(mtm - collateral, 0.0)


def _row(name: str, detail: str, mtm: float, base_mtm: float, vm: float, im: float) -> StressRow:
    return StressRow(name, detail, mtm, mtm - base_mtm, vm + im,
                     exposure_after_collateral(mtm, vm + im), exposure_after_collateral(mtm, vm))


def run_stress(ns_book: list, base: Market, vm_held: float, im_held: float, mpor_days: int) -> list:
    """Stress rows for one netting set. Collateral is held fixed at its last-call level in every
    scenario (the shock is assumed to land between margin calls); the gap scenario scales the
    combined shock by sqrt(MPOR/10)."""
    base_mtm = netting_set_value(ns_book, base)
    rows = []
    for spec in cfg.SCENARIOS:
        sc = scenario_from_dict(spec)
        rows.append(_row(sc.name, "", netting_set_value(ns_book, apply_scenario(base, sc)), base_mtm, vm_held, im_held))

    def worst(scenarios: list, name: str) -> StressRow:
        cands = [_row(name, sc.name.split("[", 1)[1].rstrip("]"),
                      netting_set_value(ns_book, apply_scenario(base, sc)), base_mtm, vm_held, im_held)
                 for sc in scenarios]
        return max(cands, key=lambda r: (r.exposure, r.stressed_mtm))

    rows.append(worst(_combo_scenarios(1.0, "combined"), cfg.COMBINED_NAME))
    gap_scale = math.sqrt(mpor_days / cfg.GAP_REFERENCE_DAYS)
    rows.append(worst(_combo_scenarios(gap_scale, "gap"), cfg.GAP_NAME))
    return rows


def worst_row(rows: list) -> StressRow:
    return max(rows, key=lambda r: r.exposure)
