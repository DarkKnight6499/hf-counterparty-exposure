"""One-page markdown risk-limit memo per counterparty."""
from pathlib import Path

from . import config as cfg

LIMITATIONS = (
    "All data is synthetic. Pricing uses simplified single-curve zero curves, constant FX vols and a flat-hazard CDS "
    "model; SIMM covers interest-rate and FX delta and vega only (credit trades carry no SIMM margin); "
    "no CVA, no wrong-way risk, no collateral haircuts, no curvature margin. Stress results are scenario "
    "outcomes, not probabilities."
)


def mm(x: float) -> str:
    return f"{x / 1e6:,.2f}"


def memo_filename(counterparty: str) -> str:
    safe = "".join(ch if ch.isalnum() else "_" for ch in counterparty).strip("_")
    return f"memo_{safe}.md"


def build_memo(r) -> str:
    f, c, m, p = r.fund, r.csa, r.metrics, r.proposal
    t = c.terms
    saccr = m.saccr
    lines = [
        f"# Counterparty exposure memo: {f.counterparty}",
        "",
        f"Netting set {f.netting_set} | {f.strategy} | NAV USD {mm(f.nav)}m | gross leverage {f.leverage:.1f}x | "
        f"internal rating bucket {f.rating} | {len(r.trades)} trades (synthetic data)",
        "",
        "## Exposure (USD millions)",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Net MTM (value to us) | {mm(m.mtm)} |",
        f"| Collateral held (VM {mm(m.vm_held)} + IM {mm(m.im_held)}) | {mm(m.collateral)} |",
        f"| Current exposure, gross of collateral | {mm(m.current_exposure_gross)} |",
        f"| Current exposure, net of collateral | {mm(m.current_exposure_net)} |",
        f"| SA-CCR EAD (RC {mm(saccr.rc)}, PFE {mm(saccr.pfe)}, multiplier {saccr.multiplier:.3f}) | {mm(saccr.ead)} |",
        f"| SIMM initial margin (IR delta {mm(m.simm.ir_delta_margin)}, FX delta {mm(m.simm.fx_delta_margin)}, "
        f"FX vega {mm(m.simm.fx_vega_margin)}) | {mm(m.simm.total_im)} |",
        "",
        f"CSA: threshold {mm(t.threshold)}, MTA {mm(t.mta)}, initial amount {mm(t.independent_amount)}, "
        f"{c.margin_frequency.lower()} margining, MPOR {c.mpor_days} days, IM regime {c.im_regime}. "
        f"Today's call: VM {mm(m.call.vm_call)}, IM {mm(m.call.im_call)}.",
        "",
        "## Stress tests (USD millions)",
        "",
        "| Scenario | Stressed MTM | P&L | Collateral | Exposure | Exposure, VM only |",
        "|---|---|---|---|---|---|",
    ]
    for s in r.stress:
        label = s.scenario + (f" [{s.detail}]" if s.detail else "")
        lines.append(f"| {label} | {mm(s.stressed_mtm)} | {mm(s.pnl)} | {mm(s.collateral_held)} | "
                     f"{mm(s.exposure)} | {mm(s.exposure_before_im)} |")
    lines += [
        "",
        f"Worst stressed exposure: {mm(r.worst.exposure)} ({r.worst.scenario.split(' (')[0]}).",
        "",
        "## Limit proposal",
        "",
        f"- Recommended limit: USD {mm(p.limit)}m ({p.base_pct_nav:.1%} of NAV for {f.rating}, leverage multiplier "
        f"{p.leverage_multiplier:.2f}).",
        f"- Utilization (worst stressed exposure / limit): {p.utilization:.0%}. EAD / limit: {p.ead_to_limit:.2f}x. "
        f"Current exposure / limit: {p.current_to_limit:.0%}. IM held / SIMM IM: {p.im_coverage:.0%}.",
        f"- Status: **{p.status}**. Rule: {p.rule}.",
        f"- Recommendation: **{p.recommendation}**."
        + (f" Indicative collateral increase: USD {mm(p.suggested_ia_increase)}m." if p.suggested_ia_increase > 0 else ""),
        "",
        "## Limitations",
        "",
        LIMITATIONS,
        "",
    ]
    return "\n".join(lines)


def write_memos(results: list, out_dir: Path) -> list:
    paths = []
    for r in results:
        path = out_dir / memo_filename(r.fund.counterparty)
        path.write_text(build_memo(r), encoding="utf-8")
        paths.append(path)
    return paths
