# Counterparty exposure memo: Halcyon Rates Relative Value Fund

Netting set NS-B | Rates relative value | NAV USD 600.00m | gross leverage 14.0x | internal rating bucket RB3 | 18 trades (synthetic data)

## Exposure (USD millions)

| Metric | Value |
|---|---|
| Net MTM (value to us) | 24.33 |
| Collateral held (VM 24.33 + IM 20.00) | 44.33 |
| Current exposure, gross of collateral | 24.33 |
| Current exposure, net of collateral | 0.00 |
| SA-CCR EAD (RC 0.00, PFE 5.83, multiplier 0.462) | 8.17 |
| SIMM initial margin (IR delta 36.37, FX delta 9.79, FX vega 0.00) | 38.96 |

CSA: threshold 0.00, MTA 0.25, initial amount 20.00, weekly margining, MPOR 15 days, IM regime IA_ONLY. Today's call: VM 4.33, IM 0.00.

## Stress tests (USD millions)

| Scenario | Stressed MTM | P&L | Collateral | Exposure | Exposure, VM only |
|---|---|---|---|---|---|
| Rates +200bp parallel | 23.13 | -1.20 | 44.33 | 0.00 | 0.00 |
| Rates -200bp parallel | 96.49 | 72.16 | 44.33 | 52.16 | 72.16 |
| Curve steepener | -9.47 | -33.80 | 44.33 | 0.00 | 0.00 |
| Curve flattener | 68.71 | 44.38 | 44.33 | 24.38 | 44.38 |
| USD +10% vs all | 18.58 | -5.75 | 44.33 | 0.00 | 0.00 |
| USD -10% vs all | 31.36 | 7.03 | 44.33 | 0.00 | 7.03 |
| Credit spread +300bp | 24.33 | 0.00 | 44.33 | 0.00 | 0.00 |
| Combined adverse (worst of 8 sign combinations) [rates_parallel_bp=-100, usd_pct=-0.05, spread_bp=+150] | 51.99 | 27.66 | 44.33 | 7.66 | 27.66 |
| MPOR gap (combined shock x sqrt(MPOR/10)) [rates_parallel_bp=-100, usd_pct=-0.05, spread_bp=+150] | 61.41 | 37.08 | 44.33 | 17.08 | 37.08 |

Worst stressed exposure: 52.16 (Rates -200bp parallel).

## Limit proposal

- Recommended limit: USD 8.57m (3.0% of NAV for RB3, leverage multiplier 0.48).
- Utilization (worst stressed exposure / limit): 609%. EAD / limit: 0.95x. Current exposure / limit: 0%. IM held / SIMM IM: 51%.
- Status: **BREACH**. Rule: R1b stressed utilization 609% > 100%; shortfall above 2.0% of NAV.
- Recommendation: **Reduce exposure or stop new trading**. Indicative collateral increase: USD 43.59m.

## Limitations

All data is synthetic. Pricing uses simplified single-curve zero curves, constant FX vols and a flat-hazard CDS model; SIMM covers interest-rate and FX delta and vega only (credit trades carry no SIMM margin); no CVA, no wrong-way risk, no collateral haircuts, no curvature margin. Stress results are scenario outcomes, not probabilities.
