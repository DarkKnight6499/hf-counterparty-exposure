"""Excel summary workbook: plain formatting, bold headers only."""
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

from . import config as cfg

NUM_FMT = "#,##0.00"


def _sheet(wb: Workbook, title: str, header: list, rows: list) -> None:
    ws = wb.create_sheet(title)
    ws.append(header)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for row in rows:
        ws.append(row)
    for col in ws.columns:
        width = max(len(str(c.value)) if c.value is not None else 0 for c in col)
        ws.column_dimensions[col[0].column_letter].width = min(max(width + 2, 10), 60)
    for row in ws.iter_rows(min_row=2):
        for c in row:
            if isinstance(c.value, float):
                c.number_format = NUM_FMT


def write_workbook(results: list, path: Path) -> None:
    wb = Workbook()
    wb.remove(wb.active)
    wb.properties.creator = cfg.WORKBOOK_AUTHOR

    book_rows = []
    for r in results:
        for bt in r.trades:
            t = bt.trade
            book_rows.append([r.fund.counterparty, t.netting_set, t.trade_id, t.asset_class, t.hedging_set,
                              t.position, t.style, t.opt_type or "", t.notional, t.start_s, t.maturity_m,
                              bt.contract_rate or None, t.strike, t.vol, bt.coupon * 1e4 or None, t.mtm])
    _sheet(wb, "Book", ["Counterparty", "Netting set", "Trade", "Asset class", "Hedging set", "Position", "Style",
                        "Option type", "Notional USD", "Start (y)", "Maturity (y)", "Fixed / contract rate",
                        "Strike", "Vol", "CDS coupon (bp)", "MTM USD"], book_rows)

    exp_rows = []
    for r in results:
        m, t, f = r.metrics, r.csa.terms, r.fund
        exp_rows.append([f.counterparty, f.strategy, f.nav, f.leverage, f.rating, m.mtm, m.vm_held, m.im_held,
                         m.collateral, m.current_exposure_gross, m.current_exposure_net, m.saccr.rc, m.saccr.pfe,
                         m.saccr.multiplier, m.saccr.ead, m.simm.ir_delta_margin, m.simm.fx_delta_margin,
                         m.simm.fx_vega_margin, m.simm.total_im, t.threshold, t.mta, t.independent_amount,
                         r.csa.margin_frequency, r.csa.mpor_days, r.csa.im_regime, m.call.vm_call, m.call.im_call])
    _sheet(wb, "Exposure", ["Counterparty", "Strategy", "NAV USD", "Gross leverage", "Rating bucket", "Net MTM",
                            "VM held", "IM held", "Collateral held", "Current exposure gross",
                            "Current exposure net", "SA-CCR RC", "SA-CCR PFE", "SA-CCR multiplier", "SA-CCR EAD",
                            "SIMM IR delta", "SIMM FX delta", "SIMM FX vega", "SIMM IM", "Threshold", "MTA",
                            "Initial amount", "Margin frequency", "MPOR days", "IM regime", "VM call today",
                            "IM call today"], exp_rows)

    st_rows = [[r.fund.counterparty, s.scenario, s.detail, s.stressed_mtm, s.pnl, s.collateral_held, s.exposure,
                s.exposure_before_im] for r in results for s in r.stress]
    _sheet(wb, "Stress", ["Counterparty", "Scenario", "Binding sign combination", "Stressed MTM", "P&L vs current",
                          "Collateral held", "Stressed exposure", "Exposure, VM only"], st_rows)

    lim_rows = [[r.fund.counterparty, r.proposal.limit, r.proposal.base_pct_nav, r.proposal.leverage_multiplier,
                 r.worst.exposure, r.worst.scenario, r.proposal.utilization, r.proposal.ead_to_limit,
                 r.proposal.current_to_limit, r.proposal.im_coverage, r.proposal.status, r.proposal.recommendation,
                 r.proposal.rule, r.proposal.suggested_ia_increase] for r in results]
    _sheet(wb, "Limits", ["Counterparty", "Recommended limit", "Base % of NAV", "Leverage multiplier",
                          "Worst stressed exposure", "Worst scenario", "Utilization", "EAD / limit",
                          "Current exposure / limit", "IM held / SIMM IM", "Status", "Recommendation", "Rule",
                          "Indicative collateral increase"], lim_rows)
    wb.save(path)
