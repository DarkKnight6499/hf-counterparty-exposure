# Counterparty exposure memo: Meridian Global Macro Fund

Netting set NS-A | Global macro | NAV USD 2,500.00m | gross leverage 4.0x | internal rating bucket RB2 | 18 trades (synthetic data)

## Exposure (USD millions)

| Metric | Value |
|---|---|
| Net MTM (value to us) | 13.70 |
| Collateral held (VM 8.70 + IM 49.41) | 58.11 |
| Current exposure, gross of collateral | 13.70 |
| Current exposure, net of collateral | 0.00 |
| SA-CCR EAD (RC 0.00, PFE 2.46, multiplier 0.197) | 3.45 |
| SIMM initial margin (IR delta 26.64, FX delta 35.54, FX vega 2.51) | 49.41 |

CSA: threshold 5.00, MTA 0.50, initial amount 10.00, daily margining, MPOR 10 days, IM regime SIMM. Today's call: VM 0.70, IM 4.41.

## Stress tests (USD millions)

| Scenario | Stressed MTM | P&L | Collateral | Exposure | Exposure, VM only |
|---|---|---|---|---|---|
| Rates +200bp parallel | 100.56 | 86.86 | 58.11 | 42.45 | 91.86 |
| Rates -200bp parallel | -89.91 | -103.61 | 58.11 | 0.00 | 0.00 |
| Curve steepener | 31.68 | 17.98 | 58.11 | 0.00 | 22.98 |
| Curve flattener | -5.04 | -18.74 | 58.11 | 0.00 | 0.00 |
| USD +10% vs all | 6.73 | -6.98 | 58.11 | 0.00 | 0.00 |
| USD -10% vs all | 28.27 | 14.56 | 58.11 | 0.00 | 19.56 |
| Credit spread +300bp | 13.70 | 0.00 | 58.11 | 0.00 | 5.00 |
| Combined adverse (worst of 8 sign combinations) [rates_parallel_bp=+100, usd_pct=-0.05, spread_bp=+150] | 65.78 | 52.08 | 58.11 | 7.67 | 57.08 |
| MPOR gap (combined shock x sqrt(MPOR/10)) [rates_parallel_bp=+100, usd_pct=-0.05, spread_bp=+150] | 65.78 | 52.08 | 58.11 | 7.67 | 57.08 |

Worst stressed exposure: 42.45 (Rates +200bp parallel).

## Limit proposal

- Recommended limit: USD 102.27m (4.5% of NAV for RB2, leverage multiplier 0.91).
- Utilization (worst stressed exposure / limit): 42%. EAD / limit: 0.03x. Current exposure / limit: 0%. IM held / SIMM IM: 100%.
- Status: **WITHIN LIMIT**. Rule: R3 no review or breach trigger.
- Recommendation: **Approve as proposed**.

## Limitations

All data is synthetic. Pricing uses simplified single-curve zero curves, constant FX vols and a flat-hazard CDS model; SIMM covers interest-rate and FX delta and vega only (credit trades carry no SIMM margin); no CVA, no wrong-way risk, no collateral haircuts, no curvature margin. Stress results are scenario outcomes, not probabilities.
