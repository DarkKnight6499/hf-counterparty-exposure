# Hedge Fund Counterparty Exposure Monitor

A Python tool for monitoring counterparty credit exposure to hedge fund clients on an OTC derivatives book.
For each netting set it computes SA-CCR exposure at default, ISDA SIMM initial margin and the CSA margin call,
runs full-revaluation stress tests (including a margin-period-of-risk gap scenario), and proposes a
risk limit with a status and a recommendation, written up as a one-page memo per counterparty plus an Excel summary.

**All data in this repository is synthetic.** The funds, trades, market data and CSA terms are invented for
illustration; none of it reflects real quotes, positions or counterparties.

## What it does

1. Loads a synthetic book (3 hedge fund netting sets, 55 trades: interest rate swaps, FX forwards, FX options, CDS).
2. Values every trade with simple analytic pricers (independent of the SA-CCR engine) and checks the book MTM in
   `data/trades.csv` against a fresh repricing.
3. Computes per netting set: SA-CCR EAD, SIMM IM, today's CSA margin call, and the resulting collateral held.
4. Revalues each netting set under stress scenarios and computes exposure after collateral.
5. Applies a transparent, rule-based limit function and writes memos (`outputs/memo_*.md`) and a workbook
   (`outputs/exposure_summary.xlsx`).

## Run

```
py -3 python/run_monitor.py                  # Windows launcher; use python3 elsewhere
py -3 python/run_monitor.py --update-readme  # also rewrites the two generated tables in this README
cd python && py -3 -m pytest                 # full test suite
cd python && py -3 -m hfexposure.build_book  # regenerate data/trades.csv (rates, strikes and MTMs come from the pricers)
```

Requires Python 3.10+, `numpy`, `scipy`, `openpyxl`, `pytest`.

All user-adjustable inputs (paths, column-name constants, scenario shocks, MPOR reference horizon, limit-rule
parameters) are in `python/hfexposure/config.py`. CSA terms, MPOR days, fund NAV, leverage and rating buckets are in
`data/csa_terms.csv` and `data/funds.csv`; market data is in `data/market_data.json`.

## Layout

```
data/                  synthetic book (trades.csv), funds.csv, csa_terms.csv, market_data.json
python/hfexposure/     config, pricers, market (scenario shocks), book, exposure, stress, limits, memo, report_xlsx, run
python/vendor/         vendored SA-CCR (saccr), SIMM (simm) and CSA (csa) modules, with their own tests
python/tests/          tests for this project; tests/vendored holds the vendored modules' tests
outputs/               generated memos and exposure_summary.xlsx
```

## Method

### Counterparties (synthetic)

| Netting set | Counterparty | Strategy | NAV (USD m) | Gross leverage | Rating bucket | Trades | CSA |
|---|---|---|---|---|---|---|---|
| NS-A | Meridian Global Macro Fund | Global macro | 2,500 | 4.0x | RB2 | 18 | TH 5m, MTA 0.5m, IA 10m, daily, MPOR 10d, SIMM IM |
| NS-B | Halcyon Rates Relative Value Fund | Rates relative value | 600 | 14.0x | RB3 | 18 | TH 0, MTA 0.25m, IA 20m, weekly, MPOR 15d, IA only |
| NS-C | Cinder Credit Long/Short Fund | Credit long/short | 1,200 | 3.0x | RB4 | 19 | TH 2m, MTA 0.25m, IA 5m, daily, MPOR 20d, IA only |

"IM regime" `SIMM` means the margin call uses max(SIMM, initial amount). `IA_ONLY` means the fund is treated as outside
regulatory IM scope, so the call uses the contractual initial amount only; SIMM is still computed and reported, and the
limit rule compares IM held with it. Margin calls are two-way with a symmetric threshold (as implemented in the vendored
CSA module); the fund posts all IM. Rating buckets RB1 (best) to RB4 are internal and invented.

### Positions and valuation convention

MTM is the value to the dealer. Trade `position` is the dealer's: for swaps `Long` = pay fixed; for FX `Long` = long the
base currency of the pair; for CDS `Long` = buy protection. Notionals are USD equivalents at the valuation date.

### Pricers (`pricers.py`)

- **Zero curves.** Continuously compounded zero rates at pillars (0.25y to 30y), linear interpolation on zero rates, flat
  extrapolation; DF(t) = exp(-z(t) t). One curve per currency (USD, EUR, GBP, JPY, AUD).
- **Interest rate swap.** Single-curve discounting. Annual fixed leg; the float leg is valued at par from the reset date:
  float = N (DF(S) - DF(T)), fixed = N K sum DF(t_i). Value to the payer = float - fixed. The valuation date is treated as a
  reset date, so remaining accrual length T - S must be whole years (enforced). Par rate = (DF(S) - DF(T)) / annuity.
- **FX forward.** Covered interest parity: F = S DF_base(T) / DF_quote(T). Value in quote currency of buying base amount A
  at K: A (F - K) DF_quote(T), converted to USD at spot. Pairs are XXXUSD or USDJPY.
- **FX option.** Garman-Kohlhagen with constant vol, using continuously compounded rates implied by the two curves;
  options are on XXXUSD pairs only.
- **CDS.** Flat hazard rate calibrated (root-find) to the market par spread for a given recovery; quarterly premium dates;
  no accrual on default; protection leg discounted at period midpoints.
  Value to the buyer = N (protection leg - coupon x risky annuity). Hazard is recalibrated under each spread shock.

### SA-CCR (vendored `vendor/saccr`, per BIS d279)

EAD = alpha (RC + PFE), alpha = 1.4. For a margined netting set RC = max(V - C, TH + MTA - NICA, 0). PFE = multiplier x
AddOn with multiplier = min(1, 0.05 + 0.95 exp((V - C) / (2 x 0.95 x AddOn))). The margined maturity factor is
1.5 sqrt(MPOR / 250) with MPOR = max(10, CSA MPOR in business days). V is the netting-set MTM, C = VM held + IM held and
NICA = IM held, all after today's call. Add-ons use supervisory duration, supervisory delta (Black-Scholes N(d1) for
options), IR maturity buckets and hedging sets by currency, FX by currency pair, credit by reference entity. Supervisory
factors and correlations are those in `vendor/saccr/params.py` (IR 0.5%, FX 4%, credit BBB single name 0.54%, IG index
0.38%, sub-IG index 1.06%); they were not re-verified against the BIS text in this project.

### SIMM (vendored `vendor/simm`, ISDA SIMM v2.6 public methodology)

Delta and vega margin for the interest-rate and FX risk classes only: weighted sensitivities, concentration risk factors,
within-bucket and cross-bucket aggregation, delta/vega combination and IR-FX risk-class correlation. Sensitivities are
proxies from notional and supervisory duration (PV01 split over at most two tenor vertices), not full risk-system
ladders; the tenor correlation is a closed-form approximation and the concentration thresholds are illustrative (see the
vendored module docstrings). Credit, equity, commodity and curvature margin are not implemented, so CDS trades add no SIMM.

### CSA margin call (vendored `vendor/csa`)

Required VM = V - TH if V > TH (symmetric below -TH, else 0); a call fires when the change versus VM already held is at
least the MTA. Required IM = max(model IM, initial amount), subject to the same MTA test.

### Stress scenarios (`stress.py`, shocks in `config.py`)

Each scenario fully revalues every trade, sums to the netting-set value, and reports stressed MTM, collateral held and
exposure = max(stressed MTM - collateral held, 0). Collateral is the VM and IM held after today's call and is **held
fixed in every scenario** (the shock lands between margin calls, with no re-margining). The column "Exposure, VM only"
in memos counts VM alone, showing the cover the initial margin provides.

| Scenario | Definition |
|---|---|
| Rates +/-200bp parallel | added to every pillar zero rate, all currencies |
| Curve steepener / flattener | pillar shocks of -50, -25, +50, +75bp at 0.25, 2, 10, 30y (reverse for flattener), linear in tenor |
| USD +10% / -10% | every non-USD currency moves 10% against USD (EURUSD divided by 1.10, USDJPY multiplied by 1.10, for +10%) |
| Credit spread +300bp | added to every CDS par spread |
| Combined adverse | rates +/-100bp, USD +/-5%, spreads +150/-50bp; all 8 sign combinations are revalued and the one with the largest exposure for that netting set is reported (the binding combination is shown). For a netting set with no CDS the spread leg has no effect |
| MPOR gap | the same 8 combinations with every shock multiplied by sqrt(MPOR / 10); MPOR is the CSA's MPOR in days. The fund is assumed to default with collateral only as current as the last call |

Spreads that tighten are floored at 5bp (or their current level if lower). Vols are not shocked.
The combined shock is calibrated as a 10-day move, so it is smaller than the stand-alone instantaneous scenarios.

### Limit proposal (`limits.py`)

```
limit       = min( NAV x base%(rating) / (1 + slope x max(leverage - ref, 0)), absolute cap )
utilization = worst stressed exposure / limit
```

Base % of NAV by bucket: RB1 6.0%, RB2 4.5%, RB3 3.0%, RB4 1.5%; leverage reference 3.0x, slope 0.10; cap USD 150m.
Rules, first match wins:

| Rule | Condition | Status | Recommendation |
|---|---|---|---|
| R1a | utilization > 100% and shortfall (stressed exposure - limit) <= 2% of NAV | BREACH | Require higher initial amount / lower threshold |
| R1b | utilization > 100% and shortfall > 2% of NAV | BREACH | Reduce exposure or stop new trading |
| R2a | utilization > 75% | REVIEW | Require higher initial amount / lower threshold |
| R2b | SA-CCR EAD > 3.0x limit | REVIEW | Require higher initial amount / lower threshold |
| R2c | IM held < 50% of SIMM IM | REVIEW | Require higher initial amount / lower threshold |
| R3 | none of the above | WITHIN LIMIT | Approve as proposed |

Beyond the specified inputs (EAD, SIMM IM, worst stressed exposure, current exposure, NAV, leverage, rating), the rule
also takes the IM actually held, for R2c. All thresholds are in `config.py`. The limit parameters are illustrative
judgement settings, not calibrated to any institution's policy.

## Results

Generated by `py -3 python/run_monitor.py --update-readme` (checked against a fresh run by the test suite).

<!-- RESULTS:START -->
| Counterparty | Trades | MTM | Current exposure (net) | SA-CCR EAD | SIMM IM | Worst stressed exposure | Worst scenario | Limit | Utilization | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| Meridian Global Macro Fund | 18 | 13.70 | 0.00 | 3.45 | 49.41 | 42.45 | Rates +200bp parallel | 102.27 | 42% | WITHIN LIMIT |
| Halcyon Rates Relative Value Fund | 18 | 24.33 | 0.00 | 8.17 | 38.96 | 52.16 | Rates -200bp parallel | 8.57 | 609% | BREACH |
| Cinder Credit Long/Short Fund | 19 | 1.23 | 0.00 | 5.93 | 6.39 | 22.90 | MPOR gap | 18.00 | 127% | BREACH |

All amounts in USD millions.
<!-- RESULTS:END -->

<!-- STRESS:START -->
| Scenario | Meridian Global Macro Fund | Halcyon Rates Relative Value Fund | Cinder Credit Long/Short Fund |
|---|---|---|---|
| Current exposure (net of collateral) | 0.00 | 0.00 | 0.00 |
| Rates +200bp parallel | 42.45 | 0.00 | 0.00 |
| Rates -200bp parallel | 0.00 | 52.16 | 21.30 |
| Curve steepener | 0.00 | 0.00 | 0.00 |
| Curve flattener | 0.00 | 24.38 | 0.00 |
| USD +10% vs all | 0.00 | 0.00 | 0.00 |
| USD -10% vs all | 0.00 | 0.00 | 0.00 |
| Credit spread +300bp | 0.00 | 0.00 | 0.00 |
| Combined adverse (worst of 8 sign combinations) | 7.67 | 7.66 | 15.21 |
| MPOR gap (combined shock x sqrt(MPOR/10)) | 7.67 | 17.08 | 22.90 |
| Binding sign combination, combined | rates bp=+100, usd=-0.05, spread bp=+150 | rates bp=-100, usd=-0.05, spread bp=+150 | rates bp=-100, usd=+0.05, spread bp=-50 |
| Binding sign combination, gap | rates bp=+100, usd=-0.05, spread bp=+150 | rates bp=-100, usd=-0.05, spread bp=+150 | rates bp=-100, usd=+0.05, spread bp=-50 |

Stressed exposure in USD millions, netted at netting-set level, after VM and IM held.
<!-- STRESS:END -->

Reading the numbers: stand-alone shocks of +/-200bp are far larger than the 10-day horizon behind SA-CCR's calibration,
so stressed exposure is much larger than EAD for the books with real rate risk. Current exposure net of collateral is zero
for all three funds because VM is posted to the threshold-adjusted MTM and initial margin sits on top.

## Tests

Run from `python/`: `py -3 -m pytest`. Current result: **84 passed**.

| File | Tests | Covers |
|---|---|---|
| `tests/test_pricers.py` | 14 | each pricer against closed-form or hand values: zero-rate and flat-curve swap values, par swap has zero value, CIP forward, Garman-Kohlhagen ATM closed form and put-call parity, CDS zero-rate closed form, hazard calibration round trip, credit triangle |
| `tests/test_stress.py` | 9 | zero shock gives zero P&L, opposite shocks have opposite signs, steepener interpolation, spread floor, exposure never negative, netting applied at netting-set level and strictly reduces exposure versus summing trades, MPOR gap exposure against a hand-computed example |
| `tests/test_limits.py` | 10 | limit arithmetic, cap, and every status and rule branch (R1a, R1b, R2a, R2b, R2c, R3) plus boundary and error cases |
| `tests/test_saccr_independent.py` | 3 | SA-CCR add-on and EAD for all three netting sets re-derived from `trades.csv` with separate code and separately typed supervisory factors |
| `tests/test_end_to_end.py` | 9 | CSV MTM equals repricing (and a tampered MTM is rejected), hand-computed SA-CCR EAD through the full exposure path at two MPORs, collateral bookkeeping, the README tables equal a fresh run, workbook formatting and author property, memo structure, no em or en dashes in repository text |
| `tests/vendored/` | 39 | the vendored SA-CCR, SIMM, CSA and CRIF tests, unchanged apart from import paths |

## Limitations

- Synthetic data; fictitious valuation date; no market data feed.
- Simplified pricing: continuously compounded zero curves with linear interpolation on zero rates, single-curve
  discounting for every swap (no OIS/projection split, no basis), IRS valued at a reset date with whole-year accrual, no
  day counts or calendars, constant FX vols with no smile, flat-hazard CDS without accrual on default, no upfront
  conventions.
- SIMM covers IR and FX delta and vega only, with proxy sensitivities and approximated tenor correlations; credit
  trades carry no SIMM margin, so the credit fund's IM understates a full-scope SIMM. No curvature.
- SA-CCR supervisory parameters are those in the vendored module (not re-verified against the BIS text here); MPOR is
  taken from the CSA with a 10-day floor, without the longer-MPOR rules for large or disputed netting sets.
- No CVA or DVA, no wrong-way risk, no concentration or liquidity add-ons, no collateral haircuts or eligibility,
  and IM is counted as freely available collateral even though regulatory IM is normally segregated.
- Collateral is fixed at its post-call level in every scenario; the gap scenario is a deterministic shock, not a
  simulated exposure distribution. Stressed exposure is a scenario outcome, not a probability-weighted measure.
- Symmetric CSA threshold and a one-way IM flow are simplifications of real hedge fund CSAs.
- Limit-rule parameters are illustrative.

## Vendored code

`python/vendor/` contains the SA-CCR, SIMM and CSA modules copied from a companion engine (commit e3490b9). The only
change is rewriting absolute imports to the `vendor.` prefix. Their original tests run unchanged under
`python/tests/vendored`.
