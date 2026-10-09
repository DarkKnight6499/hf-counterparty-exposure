"""Scenario mechanics, invariants and the MPOR gap exposure against a hand-computed example."""
import math

import pytest
from pytest import approx

from hfexposure import config as cfg
from hfexposure import pricers as px
from hfexposure.book import BookTrade, load_book, netting_set_value, value_trade
from hfexposure.market import Market, Scenario, apply_scenario, load_market
from hfexposure.stress import exposure_after_collateral, run_stress
from vendor.saccr.trades import Trade

ZERO = Scenario("zero")


@pytest.fixture(scope="module")
def market():
    return load_market()


@pytest.fixture(scope="module")
def book(market):
    return load_book(market)


def netting_sets(book):
    out = {}
    for bt in book:
        out.setdefault(bt.trade.netting_set, []).append(bt)
    return out


def test_zero_shock_gives_zero_pnl_for_every_trade_and_netting_set(market, book):
    shocked = apply_scenario(market, ZERO)
    for bt in book:
        assert value_trade(bt, shocked) == approx(value_trade(bt, market), abs=1e-6)
    assert netting_set_value(book, shocked) == approx(netting_set_value(book, market), abs=1e-4)


def _payer_swap(market, mat=5):
    t = Trade("T1", "NS-T", "IR", "USD", "Long", "Linear", None, 1e8, 0, mat, None, None, None, 0.0, "NA")
    par = px.irs_par_rate(market.curves["USD"], 0, mat)
    return BookTrade(t, par, 0.0, 1e8)


def test_opposite_rate_shocks_have_opposite_sign_for_a_payer_swap(market):
    bt = _payer_swap(market)
    up = value_trade(bt, apply_scenario(market, Scenario("u", rates_parallel_bp=200)))
    dn = value_trade(bt, apply_scenario(market, Scenario("d", rates_parallel_bp=-200)))
    assert up > 0 > dn and value_trade(bt, market) == approx(0.0, abs=1e-4)


def test_usd_strength_hurts_long_eur_forward_and_helps_long_usdjpy(market):
    eur = BookTrade(Trade("F1", "NS-T", "FX", "EURUSD", "Long", "Linear", None, 1e7, 0, 1, 1.085, 1.09, None, 0, "NA"),
                    1.09, 0, 1e7 / 1.09)
    jpy = BookTrade(Trade("F2", "NS-T", "FX", "USDJPY", "Long", "Linear", None, 1e7, 0, 1, 148, 148, None, 0, "NA"),
                    148.0, 0, 1e7)
    strong = apply_scenario(market, Scenario("s", usd_pct=0.10))
    assert value_trade(eur, strong) < value_trade(eur, market)
    assert value_trade(jpy, strong) > value_trade(jpy, market)
    assert strong.spots["EURUSD"] == approx(1.085 / 1.1) and strong.spots["USDJPY"] == approx(148 * 1.1)


def test_steepener_shock_interpolates_and_applies_to_curve(market):
    sc = Scenario("st", rates_curve_bp=((0.25, -50.0), (2.0, -25.0), (10.0, 50.0), (30.0, 75.0)))
    shocked = apply_scenario(market, sc)
    usd0, usd1 = market.curves["USD"], shocked.curves["USD"]
    assert usd1.zero(0.25) - usd0.zero(0.25) == approx(-0.0050)
    assert usd1.zero(10.0) - usd0.zero(10.0) == approx(0.0050)
    # tenor 7 sits on the 2y-10y segment, 5/8 of the way up
    assert usd1.zero(7.0) - usd0.zero(7.0) == approx((-25 + (50 + 25) * 5 / 8) * 1e-4)


def test_spread_shock_floor_and_zero_shock_identity(market):
    cheap = Market(market.curves, market.spots, {"X": {"spread": 0.0010, "recovery": 0.4}})
    tight = apply_scenario(cheap, Scenario("t", spread_bp=-100)).cds["X"]["spread"]
    assert tight == approx(cfg.MIN_SPREAD_BP * 1e-4)
    assert apply_scenario(cheap, ZERO).cds["X"]["spread"] == 0.0010


def test_exposure_never_negative_and_netting_applied_in_every_scenario(market, book):
    for ns_book in netting_sets(book).values():
        for vm, im in [(0.0, 0.0), (5e6, 10e6), (-3e6, 0.0)]:
            for r in run_stress(ns_book, market, vm, im, 20):
                assert r.exposure >= 0.0 and r.exposure_before_im >= 0.0
                assert r.collateral_held == approx(vm + im)
                assert r.exposure == approx(max(r.stressed_mtm - vm - im, 0.0))


def test_netting_reduces_exposure_versus_sum_of_trades(market, book):
    for ns_book in netting_sets(book).values():
        rows = run_stress(ns_book, market, 0.0, 0.0, 10)
        row = next(r for r in rows if r.scenario == "Rates +200bp parallel")
        shocked = apply_scenario(market, Scenario("x", rates_parallel_bp=200))
        gross = sum(max(value_trade(bt, shocked), 0.0) for bt in ns_book)
        assert row.exposure <= gross + 1e-6
    # the rates-RV book has offsetting trades, so the inequality is strict there
    ns_b = netting_sets(book)["NS-B"]
    shocked = apply_scenario(market, Scenario("x", rates_parallel_bp=-200))
    assert max(netting_set_value(ns_b, shocked), 0) < sum(max(value_trade(bt, shocked), 0) for bt in ns_b)


def test_mpor_gap_exposure_hand_computed(monkeypatch):
    # One 5y payer swap on a flat 4% curve, MPOR 40 days: shock scaled by sqrt(40/10) = 2, so the
    # +/-100bp combined axis becomes +/-200bp. The payer gains when rates rise.
    flat_curve = px.ZeroCurve((0.25, 30.0), (0.04, 0.04))
    m = Market({"USD": flat_curve}, {}, {})
    par = px.irs_par_rate(flat_curve, 0, 5)
    t = Trade("T1", "NS-T", "IR", "USD", "Long", "Linear", None, 1e8, 0, 5, None, None, None, 0.0, "NA")
    bt = BookTrade(t, par, 0.0, 1e8)
    monkeypatch.setattr(cfg, "SCENARIOS", [])
    monkeypatch.setattr(cfg, "COMBINED_AXES",
                        {"rates_parallel_bp": (100.0, -100.0), "usd_pct": (0.0,), "spread_bp": (0.0,)})
    rows = run_stress([bt], m, vm_held=3e6, im_held=1e6, mpor_days=40)
    gap = next(r for r in rows if r.scenario == cfg.GAP_NAME)
    z = 0.06   # 4% + 200bp
    annuity = sum(math.exp(-z * k) for k in range(1, 6))
    expected_mtm = 1e8 * ((1 - math.exp(-z * 5)) - par * annuity)
    assert gap.stressed_mtm == approx(expected_mtm, rel=1e-12)
    assert gap.exposure == approx(max(expected_mtm - 4e6, 0.0), rel=1e-12)
    assert gap.exposure_before_im == approx(expected_mtm - 3e6, rel=1e-12)
    combined = next(r for r in rows if r.scenario == cfg.COMBINED_NAME)
    assert combined.stressed_mtm < gap.stressed_mtm        # MPOR of 40 days scales the shock up
    assert "rates_parallel_bp=+100" in combined.detail


def test_exposure_floor_helper():
    assert exposure_after_collateral(-5.0, 1.0) == 0.0 and exposure_after_collateral(5.0, 1.0) == 4.0
