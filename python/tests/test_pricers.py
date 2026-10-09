"""Pricers against closed-form or hand-computed values."""
import math

import pytest
from pytest import approx

from hfexposure import pricers as px

E = math.exp


def flat(rate: float) -> px.ZeroCurve:
    return px.ZeroCurve((0.25, 30.0), (rate, rate))


def test_zero_curve_linear_interpolation_and_flat_extrapolation():
    c = px.ZeroCurve((1.0, 3.0), (0.02, 0.04))
    assert c.zero(2.0) == approx(0.03)
    assert c.zero(0.1) == 0.02 and c.zero(10.0) == 0.04
    assert c.df(2.0) == approx(E(-0.06))


def test_irs_zero_rates_hand_value():
    # DF = 1 everywhere, so the float leg is worth 0 and the fixed leg is 2 x 4% x 1m.
    assert px.irs_value_payer(1e6, 0.04, 0, 2, flat(0.0)) == approx(-80_000.0)


def test_irs_flat_curve_hand_value():
    # 3y, 5% flat continuous: float 1m*(1-e^-0.15) minus fixed 40k*(e^-.05+e^-.1+e^-.15).
    assert px.irs_value_payer(1e6, 0.04, 0, 3, flat(0.05)) == approx(30_621.03, abs=0.01)


@pytest.mark.parametrize("start,mat", [(0, 5), (0, 10), (2, 7), (1, 30)])
def test_par_swap_has_zero_value_and_receiver_is_negative_payer(start, mat):
    curve = px.ZeroCurve((0.25, 1, 5, 10, 30), (0.03, 0.035, 0.04, 0.042, 0.04))
    par = px.irs_par_rate(curve, start, mat)
    assert px.irs_value_payer(5e7, par, start, mat, curve) == approx(0.0, abs=1e-6)
    pay = px.irs_value_payer(5e7, par + 0.001, start, mat, curve)
    assert pay < 0 < px.irs_value_payer(5e7, par - 0.001, start, mat, curve)


def test_irs_rejects_fractional_accrual_length():
    with pytest.raises(ValueError):
        px.irs_value_payer(1e6, 0.04, 0, 2.5, flat(0.03))


def test_fx_forward_covered_interest_parity_hand_value():
    base, quote = flat(0.03), flat(0.05)
    assert px.fx_forward_rate(1.10, base.df(1), quote.df(1)) == approx(1.10 * E(0.02))
    v = px.fx_forward_value_quote(1e6, 1.10, 1.10, 1.0, base, quote)
    assert v == approx(21_137.72, abs=0.01)
    k = 1.10 * E(0.02)
    assert px.fx_forward_value_quote(1e6, k, 1.10, 1.0, base, quote) == approx(0.0, abs=1e-6)


def test_garman_kohlhagen_atm_zero_rates_closed_form():
    # S = K, r = 0: call = put = S * (2 N(sigma sqrt(T) / 2) - 1) = 0.0796557 for sigma 20%, T 1.
    c = px.garman_kohlhagen_value_quote(1.0, True, 1.0, 1.0, 0.2, 1.0, flat(0.0), flat(0.0))
    p = px.garman_kohlhagen_value_quote(1.0, False, 1.0, 1.0, 0.2, 1.0, flat(0.0), flat(0.0))
    assert c == approx(0.07965567, abs=1e-8) and p == approx(c)


def test_garman_kohlhagen_put_call_parity_equals_forward_value():
    base, quote = flat(0.02), flat(0.05)
    args = (1.2, 1.15, 0.1, 1.5, base, quote)
    c = px.garman_kohlhagen_value_quote(1e6, True, *args)
    p = px.garman_kohlhagen_value_quote(1e6, False, *args)
    fwd = px.fx_forward_value_quote(1e6, 1.15, 1.2, 1.5, base, quote)
    assert c - p == approx(fwd, rel=1e-10)


def test_cds_zero_rates_closed_form():
    # r = 0: protection leg telescopes to (1-R)(1-Q(T)); annuity is a quarterly geometric sum.
    h, rec, mat = 0.03, 0.4, 5.0
    curve = flat(0.0)
    assert px.cds_protection_leg(h, rec, mat, curve) == approx((1 - rec) * (1 - E(-h * mat)), rel=1e-12)
    geo = 0.25 * sum(E(-h * 0.25 * i) for i in range(1, 21))
    assert px.cds_risky_annuity(h, mat, curve) == approx(geo, rel=1e-12)


def test_cds_hazard_calibration_round_trip_and_credit_triangle():
    curve = flat(0.04)
    h = px.cds_calibrate_hazard(0.012, 0.4, 5.0, curve)
    assert px.cds_par_spread(h, 0.4, 5.0, curve) == approx(0.012, abs=1e-12)
    assert h == approx(0.012 / 0.6, rel=0.03)    # credit triangle s ~ (1-R) * hazard


def test_cds_value_identity_sign_and_par_zero():
    curve = flat(0.04)
    s, c, rec, mat = 0.015, 0.01, 0.4, 5.0
    h = px.cds_calibrate_hazard(s, rec, mat, curve)
    v = px.cds_value_buyer(1e7, c, s, rec, mat, curve)
    assert v == approx(1e7 * (s - c) * px.cds_risky_annuity(h, mat, curve), rel=1e-9)
    assert v > 0                                   # protection bought below market spread
    assert px.cds_value_buyer(1e7, s, s, rec, mat, curve) == approx(0.0, abs=1e-6)
    assert px.cds_value_buyer(1e7, c, 0.02, rec, mat, curve) > v   # wider market spread, more value
