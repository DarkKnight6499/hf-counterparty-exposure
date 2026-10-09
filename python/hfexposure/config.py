"""Single config module: every user-adjustable input lives here."""
from pathlib import Path

# ---- Paths -------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = ROOT_DIR / "outputs"
TRADES_CSV = DATA_DIR / "trades.csv"
FUNDS_CSV = DATA_DIR / "funds.csv"
CSA_CSV = DATA_DIR / "csa_terms.csv"
MARKET_JSON = DATA_DIR / "market_data.json"
WORKBOOK_NAME = "exposure_summary.xlsx"
WORKBOOK_AUTHOR = "Yazad Madan"

# ---- Column names (trades.csv: first block is read by the vendored SA-CCR loader) ----
COL_TRADE_ID = "trade_id"
COL_NETTING_SET = "netting_set"
COL_ASSET_CLASS = "asset_class"
COL_HEDGING_SET = "hedging_set"
COL_POSITION = "position"
COL_STYLE = "style"
COL_OPT_TYPE = "opt_type"
COL_NOTIONAL = "notional"
COL_START = "start_s"
COL_MATURITY = "maturity_m"
COL_UNDERLYING = "underlying_price"
COL_STRIKE = "strike"
COL_VOL = "vol"
COL_MTM = "mtm"
COL_SUB_CATEGORY = "sub_category"
COL_FIXED_RATE = "fixed_rate"        # IRS fixed rate (decimal) or FX forward contract rate
COL_COUPON_BP = "coupon_bp"          # CDS running coupon
TRADE_COLUMNS = [
    COL_TRADE_ID, COL_NETTING_SET, COL_ASSET_CLASS, COL_HEDGING_SET, COL_POSITION, COL_STYLE,
    COL_OPT_TYPE, COL_NOTIONAL, COL_START, COL_MATURITY, COL_UNDERLYING, COL_STRIKE, COL_VOL,
    COL_MTM, COL_SUB_CATEGORY, COL_FIXED_RATE, COL_COUPON_BP,
]

# funds.csv
COL_COUNTERPARTY = "counterparty"
COL_STRATEGY = "strategy"
COL_NAV = "nav_usd"
COL_LEVERAGE = "gross_leverage"
COL_RATING = "rating_bucket"
# csa_terms.csv
COL_THRESHOLD = "threshold"
COL_MTA = "mta"
COL_IA = "independent_amount"
COL_POSTED_VM = "posted_vm"
COL_POSTED_IM = "posted_im"
COL_MARGIN_FREQ = "margin_frequency"
COL_MPOR_DAYS = "mpor_days"
COL_IM_REGIME = "im_regime"
IM_REGIME_SIMM = "SIMM"          # margin call IM = max(SIMM, initial amount)
IM_REGIME_IA_ONLY = "IA_ONLY"    # fund outside regulatory IM scope: margin call IM = initial amount only

# ---- Stress scenarios (full revaluation) -----------------------------------------
# rates_parallel_bp: bp added to every zero rate; rates_curve_bp: {tenor_years: bp}, linear in tenor;
# usd_pct: +0.10 means USD appreciates 10% against every other currency; spread_bp: added to CDS par spreads.
SCENARIOS = [
    {"name": "Rates +200bp parallel", "rates_parallel_bp": 200.0},
    {"name": "Rates -200bp parallel", "rates_parallel_bp": -200.0},
    {"name": "Curve steepener", "rates_curve_bp": {0.25: -50.0, 2.0: -25.0, 10.0: 50.0, 30.0: 75.0}},
    {"name": "Curve flattener", "rates_curve_bp": {0.25: 50.0, 2.0: 25.0, 10.0: -50.0, 30.0: -75.0}},
    {"name": "USD +10% vs all", "usd_pct": 0.10},
    {"name": "USD -10% vs all", "usd_pct": -0.10},
    {"name": "Credit spread +300bp", "spread_bp": 300.0},
]
# Combined and gap scenarios evaluate every sign combination of these axes and keep the worst for the
# netting set. Calibrated as a 10-day shock, so smaller than the stand-alone instantaneous scenarios above.
COMBINED_AXES = {
    "rates_parallel_bp": (100.0, -100.0),
    "usd_pct": (0.05, -0.05),
    "spread_bp": (150.0, -50.0),
}
COMBINED_NAME = "Combined adverse (worst of 8 sign combinations)"
GAP_NAME = "MPOR gap (combined shock x sqrt(MPOR/10))"
GAP_REFERENCE_DAYS = 10          # horizon over which the combined shock is calibrated
MIN_SPREAD_BP = 5.0              # floor when spreads tighten
PRICING_TOLERANCE_USD = 0.01     # book MTM in trades.csv must match a fresh repricing to this tolerance

# ---- Limit rule parameters ---------------------------------------------------------
LIMIT_BASE_PCT_NAV = {"RB1": 0.060, "RB2": 0.045, "RB3": 0.030, "RB4": 0.015}  # limit as share of NAV
LIMIT_LEVERAGE_REF = 3.0         # gross leverage up to this is not penalised
LIMIT_LEVERAGE_SLOPE = 0.10      # multiplier = 1 / (1 + slope * max(leverage - ref, 0))
LIMIT_ABSOLUTE_CAP = 150_000_000.0
LIMIT_REVIEW_UTILIZATION = 0.75  # stressed exposure / limit above this is REVIEW
LIMIT_BREACH_UTILIZATION = 1.00  # above this is BREACH
LIMIT_EAD_REVIEW_MULTIPLE = 3.0  # EAD above this multiple of the limit is REVIEW
LIMIT_IM_COVERAGE_MIN = 0.50     # IM held below this share of SIMM IM is REVIEW
LIMIT_CURE_MAX_PCT_NAV = 0.02    # a breach curable by an extra initial amount of up to this share of NAV
                                 # gets "require higher initial amount"; larger breaches get "reduce / stop"
