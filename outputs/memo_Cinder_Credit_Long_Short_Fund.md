# Counterparty exposure memo: Cinder Credit Long/Short Fund

Netting set NS-C | Credit long/short | NAV USD 1,200.00m | gross leverage 3.0x | internal rating bucket RB4 | 19 trades (synthetic data)

## Exposure (USD millions)

| Metric | Value |
|---|---|
| Net MTM (value to us) | 1.23 |
| Collateral held (VM 0.00 + IM 5.00) | 5.00 |
| Current exposure, gross of collateral | 1.23 |
| Current exposure, net of collateral | 0.00 |
| SA-CCR EAD (RC 0.00, PFE 4.23, multiplier 0.726) | 5.93 |
| SIMM initial margin (IR delta 5.64, FX delta 1.96, FX vega 0.36) | 6.39 |

CSA: threshold 2.00, MTA 0.25, initial amount 5.00, daily margining, MPOR 20 days, IM regime IA_ONLY. Today's call: VM 0.00, IM 0.00.

## Stress tests (USD millions)

| Scenario | Stressed MTM | P&L | Collateral | Exposure | Exposure, VM only |
|---|---|---|---|---|---|
| Rates +200bp parallel | -20.96 | -22.19 | 5.00 | 0.00 | 0.00 |
| Rates -200bp parallel | 26.30 | 25.07 | 5.00 | 21.30 | 26.30 |
| Curve steepener | -0.36 | -1.59 | 5.00 | 0.00 | 0.00 |
| Curve flattener | 2.83 | 1.60 | 5.00 | 0.00 | 2.83 |
| USD +10% vs all | 3.84 | 2.61 | 5.00 | 0.00 | 3.84 |
| USD -10% vs all | -0.21 | -1.43 | 5.00 | 0.00 | 0.00 |
| Credit spread +300bp | -27.70 | -28.93 | 5.00 | 0.00 | 0.00 |
| Combined adverse (worst of 8 sign combinations) [rates_parallel_bp=-100, usd_pct=+0.05, spread_bp=-50] | 20.21 | 18.99 | 5.00 | 15.21 | 20.21 |
| MPOR gap (combined shock x sqrt(MPOR/10)) [rates_parallel_bp=-100, usd_pct=+0.05, spread_bp=-50] | 27.90 | 26.67 | 5.00 | 22.90 | 27.90 |

Worst stressed exposure: 22.90 (MPOR gap).

## Limit proposal

- Recommended limit: USD 18.00m (1.5% of NAV for RB4, leverage multiplier 1.00).
- Utilization (worst stressed exposure / limit): 127%. EAD / limit: 0.33x. Current exposure / limit: 0%. IM held / SIMM IM: 78%.
- Status: **BREACH**. Rule: R1a stressed utilization 127% > 100%; shortfall within 2.0% of NAV.
- Recommendation: **Require higher initial amount / lower threshold**. Indicative collateral increase: USD 4.90m.

## Limitations

All data is synthetic. Pricing uses simplified single-curve zero curves, constant FX vols and a flat-hazard CDS model; SIMM covers interest-rate and FX delta and vega only (credit trades carry no SIMM margin); no CVA, no wrong-way risk, no collateral haircuts, no curvature margin. Stress results are scenario outcomes, not probabilities.
