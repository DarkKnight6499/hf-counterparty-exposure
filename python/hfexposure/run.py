"""Entry point: py -3 run_monitor.py  (from the python/ directory, or by path from anywhere)."""
import re
import sys
from dataclasses import dataclass

from . import config as cfg
from .book import by_netting_set, load_book, netting_set_value
from .exposure import CsaRow, ExposureMetrics, Fund, compute_exposure, load_csa, load_funds
from .limits import LimitInputs, LimitProposal, propose_limit
from .market import load_market
from .stress import StressRow, run_stress, worst_row

README_START = "<!-- RESULTS:START -->"
README_END = "<!-- RESULTS:END -->"
STRESS_START = "<!-- STRESS:START -->"
STRESS_END = "<!-- STRESS:END -->"


@dataclass
class CounterpartyResult:
    fund: Fund
    csa: CsaRow
    trades: list                 # BookTrade list
    metrics: ExposureMetrics
    stress: list                 # StressRow list
    worst: StressRow
    proposal: LimitProposal


def run_all() -> list:
    market = load_market()
    book = load_book(market)
    funds, groups = load_funds(), by_netting_set(book)
    csa = load_csa(funds)
    results = []
    for ns in sorted(groups):
        ns_book = groups[ns]
        mtm = netting_set_value(ns_book, market)
        metrics = compute_exposure(ns, [bt.trade for bt in ns_book], mtm, csa[ns])
        rows = run_stress(ns_book, market, metrics.vm_held, metrics.im_held, csa[ns].mpor_days)
        worst = worst_row(rows)
        f = funds[ns]
        proposal = propose_limit(LimitInputs(
            ead=metrics.saccr.ead, simm_im=metrics.simm.total_im, worst_stressed_exposure=worst.exposure,
            current_exposure=metrics.current_exposure_net, nav=f.nav, leverage=f.leverage, rating=f.rating,
            im_held=metrics.im_held))
        results.append(CounterpartyResult(f, csa[ns], ns_book, metrics, rows, worst, proposal))
    return results


def mm(x: float) -> str:
    return f"{x / 1e6:,.2f}"


def results_table(results: list) -> str:
    head = ("| Counterparty | Trades | MTM | Current exposure (net) | SA-CCR EAD | SIMM IM | Worst stressed exposure "
            "| Worst scenario | Limit | Utilization | Status |\n|---|---|---|---|---|---|---|---|---|---|---|")
    lines = [head]
    for r in results:
        m, p = r.metrics, r.proposal
        lines.append(f"| {r.fund.counterparty} | {len(r.trades)} | {mm(m.mtm)} | {mm(m.current_exposure_net)} | "
                     f"{mm(m.saccr.ead)} | {mm(m.simm.total_im)} | {mm(r.worst.exposure)} | {r.worst.scenario.split(' (')[0]} | "
                     f"{mm(p.limit)} | {p.utilization:.0%} | {p.status} |")
    return "\n".join(lines) + "\n\nAll amounts in USD millions."


def stress_table(results: list) -> str:
    """Stressed exposure (after VM and IM held) per scenario and counterparty."""
    names = [r.fund.counterparty for r in results]
    lines = ["| Scenario | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    lines.append("| Current exposure (net of collateral) | "
                 + " | ".join(mm(r.metrics.current_exposure_net) for r in results) + " |")
    for i, s in enumerate(results[0].stress):
        lines.append(f"| {s.scenario} | " + " | ".join(mm(r.stress[i].exposure) for r in results) + " |")
    for idx, label in ((-2, "combined"), (-1, "gap")):
        lines.append(f"| Binding sign combination, {label} | "
                     + " | ".join(r.stress[idx].detail.replace("rates_parallel_bp", "rates bp").replace("usd_pct", "usd")
                                  .replace("spread_bp", "spread bp") for r in results) + " |")
    return "\n".join(lines) + "\n\nStressed exposure in USD millions, netted at netting-set level, after VM and IM held."


def _replace_block(text: str, start: str, end: str, body: str) -> str:
    block = f"{start}\n{body}\n{end}"
    return re.sub(re.escape(start) + ".*?" + re.escape(end), lambda _: block, text, flags=re.S)


def update_readme(results: list) -> None:
    path = cfg.ROOT_DIR / "README.md"
    text = path.read_text(encoding="utf-8")
    text = _replace_block(text, README_START, README_END, results_table(results))
    text = _replace_block(text, STRESS_START, STRESS_END, stress_table(results))
    path.write_text(text, encoding="utf-8")


def main(argv: list = None) -> None:
    from .memo import write_memos
    from .report_xlsx import write_workbook
    argv = sys.argv[1:] if argv is None else argv
    results = run_all()
    cfg.OUTPUT_DIR.mkdir(exist_ok=True)
    write_memos(results, cfg.OUTPUT_DIR)
    write_workbook(results, cfg.OUTPUT_DIR / cfg.WORKBOOK_NAME)
    if "--update-readme" in argv:
        update_readme(results)
    print(results_table(results))
