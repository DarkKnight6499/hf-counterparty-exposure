"""Every status and recommendation of the limit rule is reachable; arithmetic is explicit."""
import pytest
from pytest import approx

from hfexposure import limits as lm

NAV = 1_000_000_000.0


def inputs(**kw):
    base = dict(ead=1e6, simm_im=10e6, worst_stressed_exposure=10e6, current_exposure=0.0, nav=NAV,
                leverage=2.0, rating="RB2", im_held=10e6)
    base.update(kw)
    return lm.LimitInputs(**base)


P = lm.LimitParams(base_pct_nav={"RB1": 0.06, "RB2": 0.04, "RB3": 0.02, "RB4": 0.01}, leverage_ref=3.0,
                   leverage_slope=0.1, absolute_cap=1e9, review_utilization=0.75, breach_utilization=1.0,
                   ead_review_multiple=3.0, im_coverage_min=0.5, cure_max_pct_nav=0.02)


def test_limit_formula_with_and_without_leverage_penalty():
    assert lm.propose_limit(inputs(), P).limit == approx(40e6)                    # 4% of NAV, no penalty at 2x
    p = lm.propose_limit(inputs(leverage=13.0), P)
    assert p.leverage_multiplier == approx(0.5) and p.limit == approx(20e6)      # 1 / (1 + 0.1 * 10)


def test_absolute_cap_binds():
    capped = lm.LimitParams(base_pct_nav=P.base_pct_nav, absolute_cap=25e6)
    assert lm.propose_limit(inputs(), capped).limit == 25e6


def test_within_limit():
    r = lm.propose_limit(inputs(worst_stressed_exposure=20e6), P)
    assert (r.status, r.recommendation) == (lm.STATUS_WITHIN, lm.REC_APPROVE) and r.rule.startswith("R3")
    assert r.utilization == approx(0.5)


def test_review_on_stressed_utilization():
    r = lm.propose_limit(inputs(worst_stressed_exposure=32e6), P)   # 80% of 40m
    assert r.status == lm.STATUS_REVIEW and r.recommendation == lm.REC_MORE_COLLATERAL and r.rule.startswith("R2a")
    assert r.suggested_ia_increase == approx(32e6 - 0.75 * 40e6)


def test_review_on_ead_multiple():
    r = lm.propose_limit(inputs(ead=130e6), P)                       # 3.25x the 40m limit
    assert r.status == lm.STATUS_REVIEW and r.rule.startswith("R2b")


def test_review_on_thin_im_coverage():
    r = lm.propose_limit(inputs(im_held=4e6), P)                     # 40% of SIMM
    assert r.status == lm.STATUS_REVIEW and r.rule.startswith("R2c")
    assert r.suggested_ia_increase == approx(0.5 * 10e6 - 4e6)


def test_breach_curable_with_collateral():
    r = lm.propose_limit(inputs(worst_stressed_exposure=50e6), P)    # shortfall 10m, at most 2% of NAV (20m)
    assert r.status == lm.STATUS_BREACH and r.recommendation == lm.REC_MORE_COLLATERAL and r.rule.startswith("R1a")
    assert r.suggested_ia_increase == approx(10e6)


def test_breach_requires_reduction_when_shortfall_is_large():
    r = lm.propose_limit(inputs(worst_stressed_exposure=100e6), P)   # shortfall 60m > 20m
    assert r.status == lm.STATUS_BREACH and r.recommendation == lm.REC_REDUCE and r.rule.startswith("R1b")


def test_exact_boundary_utilization_is_review_not_breach():
    assert lm.propose_limit(inputs(worst_stressed_exposure=40e6), P).status == lm.STATUS_REVIEW


def test_unknown_rating_raises():
    with pytest.raises(KeyError):
        lm.propose_limit(inputs(rating="RB9"), P)
