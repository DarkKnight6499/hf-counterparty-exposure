"""Rule-based exposure limit proposal. Every threshold comes from config; every outcome names its rule."""
from dataclasses import dataclass

from . import config as cfg

STATUS_WITHIN = "WITHIN LIMIT"
STATUS_REVIEW = "REVIEW"
STATUS_BREACH = "BREACH"
REC_APPROVE = "Approve as proposed"
REC_MORE_COLLATERAL = "Require higher initial amount / lower threshold"
REC_REDUCE = "Reduce exposure or stop new trading"


@dataclass(frozen=True)
class LimitParams:
    base_pct_nav: dict = None
    leverage_ref: float = cfg.LIMIT_LEVERAGE_REF
    leverage_slope: float = cfg.LIMIT_LEVERAGE_SLOPE
    absolute_cap: float = cfg.LIMIT_ABSOLUTE_CAP
    review_utilization: float = cfg.LIMIT_REVIEW_UTILIZATION
    breach_utilization: float = cfg.LIMIT_BREACH_UTILIZATION
    ead_review_multiple: float = cfg.LIMIT_EAD_REVIEW_MULTIPLE
    im_coverage_min: float = cfg.LIMIT_IM_COVERAGE_MIN
    cure_max_pct_nav: float = cfg.LIMIT_CURE_MAX_PCT_NAV

    def pct_nav(self, rating: str) -> float:
        return (self.base_pct_nav or cfg.LIMIT_BASE_PCT_NAV)[rating]


@dataclass(frozen=True)
class LimitInputs:
    ead: float
    simm_im: float
    worst_stressed_exposure: float
    current_exposure: float
    nav: float
    leverage: float
    rating: str
    im_held: float          # initial margin actually held, compared with SIMM IM


@dataclass(frozen=True)
class LimitProposal:
    limit: float
    base_pct_nav: float
    leverage_multiplier: float
    utilization: float
    ead_to_limit: float
    current_to_limit: float
    im_coverage: float
    status: str
    recommendation: str
    rule: str
    suggested_ia_increase: float


def propose_limit(x: LimitInputs, p: LimitParams = LimitParams()) -> LimitProposal:
    """Limit = min(NAV * base% for the rating bucket / (1 + slope * max(leverage - ref, 0)), cap).

    Rules, first match wins:
      R1  utilization > breach level: cure with higher initial amount if the shortfall is at most
          cure_max_pct_nav of NAV (R1a), otherwise reduce / stop (R1b).
      R2  utilization > review level (R2a), or EAD > multiple * limit (R2b), or IM held below
          im_coverage_min of SIMM IM (R2c): require more collateral.
      R3  otherwise approve.
    """
    base_pct = p.pct_nav(x.rating)
    lev_mult = 1.0 / (1.0 + p.leverage_slope * max(x.leverage - p.leverage_ref, 0.0))
    limit = min(x.nav * base_pct * lev_mult, p.absolute_cap)
    util = x.worst_stressed_exposure / limit
    ead_ratio = x.ead / limit
    cover = x.im_held / x.simm_im if x.simm_im > 0 else 1.0
    shortfall = max(x.worst_stressed_exposure - limit, 0.0)
    triggers = []
    if util > p.review_utilization:
        triggers.append(f"R2a stressed utilization {util:.0%} > {p.review_utilization:.0%}")
    if ead_ratio > p.ead_review_multiple:
        triggers.append(f"R2b EAD {ead_ratio:.1f}x limit > {p.ead_review_multiple:.1f}x")
    if cover < p.im_coverage_min:
        triggers.append(f"R2c IM held {cover:.0%} of SIMM < {p.im_coverage_min:.0%}")
    coverage_gap = max(p.im_coverage_min * x.simm_im - x.im_held, 0.0)

    if util > p.breach_utilization:
        status = STATUS_BREACH
        if shortfall <= p.cure_max_pct_nav * x.nav:
            rec = REC_MORE_COLLATERAL
            rule = f"R1a stressed utilization {util:.0%} > {p.breach_utilization:.0%}; shortfall within {p.cure_max_pct_nav:.1%} of NAV"
        else:
            rec = REC_REDUCE
            rule = f"R1b stressed utilization {util:.0%} > {p.breach_utilization:.0%}; shortfall above {p.cure_max_pct_nav:.1%} of NAV"
        extra = [t for t in triggers if not t.startswith("R2a")]
        rule = "; ".join([rule] + extra)
        ia_increase = shortfall
    elif triggers:
        status, rec, rule = STATUS_REVIEW, REC_MORE_COLLATERAL, "; ".join(triggers)
        ia_increase = max(x.worst_stressed_exposure - p.review_utilization * limit, coverage_gap)
    else:
        status, rec, rule, ia_increase = STATUS_WITHIN, REC_APPROVE, "R3 no review or breach trigger", 0.0
    return LimitProposal(limit, base_pct, lev_mult, util, ead_ratio, x.current_exposure / limit, cover,
                         status, rec, rule, ia_increase)
