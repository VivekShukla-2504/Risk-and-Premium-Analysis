"""
Scenario and sensitivity analysis.

This is SCENARIO ANALYSIS ("what if these assumptions held?"), NOT a forecast or prediction.

Base experience = the observed portfolio in scope (incurred claims, earned premium proxy).
Shocks are multiplicative:

    frequency_s = frequency_0 x (1 + dF)
    severity_s  = severity_0  x (1 + dS) x (1 + inflation)
    claim cost  = policies x frequency_s x severity_s            (expected claim cost)
    premium_s   = earned premium_0 x (1 + dP)
    loss ratio  = claim cost / premium_s
    margin      = 1 - loss ratio - expense ratio                  (illustrative underwriting margin)

The expense ratio is an ASSUMPTION supplied by the user; investment income, reinsurance, capital costs, taxes and
IBNR are ignored.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from app.services import analytics_service as A

# (low, high) allowed values, in percent
LIMITS = {
    "frequency_change_pct": (-20.0, 20.0),
    "severity_change_pct": (-20.0, 20.0),
    "inflation_pct": (-10.0, 30.0),
    "premium_adjustment_pct": (-30.0, 30.0),
    "expense_ratio_pct": (0.0, 60.0),
    "target_loss_ratio_pct": (30.0, 100.0),
}
GRID_STEPS = [-20.0, -10.0, 0.0, 10.0, 20.0]
TORNADO_SHOCK = 10.0

DISCLAIMER = ("Scenario analysis: shows the arithmetic effect of the assumptions you choose on this (synthetic) portfolio's "
              "observed experience. It is not a prediction or forecast and is not pricing advice.")

FORMULAS = {
    "frequency": "frequency_s = frequency_0 x (1 + frequency change)",
    "severity": "severity_s = severity_0 x (1 + severity change) x (1 + inflation)",
    "expected_claim_cost": "policies x frequency_s x severity_s",
    "premium": "earned premium_0 x (1 + premium adjustment)",
    "loss_ratio": "expected claim cost / scenario premium",
    "underwriting_margin": "1 - loss ratio - expense ratio  (illustrative; expense ratio is an assumption)",
    "required_premium_change": "(expected claim cost / target loss ratio) / earned premium_0 - 1",
}


class ScenarioError(ValueError):
    """Scenario cannot be computed (invalid inputs or no claims in scope)."""


@dataclass(frozen=True)
class ScenarioInputs:
    frequency_change_pct: float = 0.0
    severity_change_pct: float = 0.0
    inflation_pct: float = 0.0
    premium_adjustment_pct: float = 0.0
    expense_ratio_pct: float = 25.0
    target_loss_ratio_pct: float = 65.0

    def validate(self) -> None:
        for name, (lo, hi) in LIMITS.items():
            v = getattr(self, name)
            if not (lo <= v <= hi):
                raise ScenarioError(f"{name} must be between {lo:g} and {hi:g} (got {v:g})")


def _base_from(df: pd.DataFrame) -> dict:
    s = A._sums(df)
    if s["policies"] == 0:
        raise ScenarioError("No policies in scope for the scenario.")
    if s["claims"] == 0:
        raise ScenarioError("No claims in scope: claim severity is undefined, so a scenario cannot be built.")
    if s["earned"] <= 0:
        raise ScenarioError("Earned premium is zero for the selected scope.")
    return s


def _point(base: dict, inp: ScenarioInputs) -> dict:
    """Scenario result for one set of assumptions, from the base totals."""
    n = base["policies"]
    f0 = base["claims"] / n
    s0 = base["incurred"] / base["claims"]
    f1 = f0 * (1 + inp.frequency_change_pct / 100)
    if f1 > 1 + 1e-12:
        max_change = (1 / f0 - 1) * 100
        raise ScenarioError(
            f"Adjusted claim frequency would be {f1:.1%}, above the 100% maximum for one claim per policy. "
            f"The selected scope supports a frequency increase of at most {max_change:.2f}%."
        )
    s1 = s0 * (1 + inp.severity_change_pct / 100) * (1 + inp.inflation_pct / 100)
    cost = n * f1 * s1
    premium = base["earned"] * (1 + inp.premium_adjustment_pct / 100)
    lr = cost / premium
    exp = inp.expense_ratio_pct / 100
    return {
        "claim_frequency": f1, "claim_severity": s1, "expected_claims": n * f1,
        "pure_premium": f1 * s1, "expected_claim_cost": cost, "earned_premium": premium,
        "loss_ratio": lr, "expense_ratio": exp, "combined_ratio": lr + exp,
        "underwriting_result": premium - cost - exp * premium, "underwriting_margin": 1 - lr - exp,
    }


def _round_point(p: dict) -> dict:
    money = {"claim_severity", "pure_premium", "expected_claim_cost", "earned_premium", "underwriting_result"}
    return {k: round(v, 2 if k in money else (2 if k == "expected_claims" else 6)) for k, v in p.items()}


def _delta(base: dict, scen: dict) -> dict:
    out = {}
    for k in ("claim_frequency", "claim_severity", "pure_premium", "expected_claim_cost", "earned_premium",
              "loss_ratio", "underwriting_result"):
        b, s = base[k], scen[k]
        out[k] = {"absolute": round(s - b, 6 if "ratio" in k or k == "claim_frequency" else 2),
                  "percent": None if b == 0 else round((s / b - 1) * 100, 4)}
    return out


def compute_scenario(df: pd.DataFrame, inp: ScenarioInputs) -> dict:
    inp.validate()
    base_sums = _base_from(df)
    zero = ScenarioInputs(0, 0, 0, 0, inp.expense_ratio_pct, inp.target_loss_ratio_pct)
    base = _point(base_sums, zero)
    scen = _point(base_sums, inp)

    # Premium needed to hit the target loss ratio / break even, given the scenario claim cost
    target = inp.target_loss_ratio_pct / 100
    exp = inp.expense_ratio_pct / 100
    req_target = scen["expected_claim_cost"] / target
    req_break_even = scen["expected_claim_cost"] / (1 - exp)

    # Sampling noise of the baseline frequency (95% Wilson interval), to put the shocks in context
    lo, hi = A.wilson_interval(base_sums["claims"], base_sums["policies"])
    f0 = base["claim_frequency"]
    noise_pct = None if lo is None else round((hi - lo) / 2 / f0 * 100, 2)

    # Impossible incidence shocks are left unavailable rather than reported above 100%.
    lr_grid, margin_grid = [], []
    for ds in GRID_STEPS:
        lr_row, m_row = [], []
        for df_ in GRID_STEPS:
            f1 = f0 * (1 + df_ / 100)
            if f1 > 1 + 1e-12:
                lr_row.append(None)
                m_row.append(None)
                continue
            pt = _point(base_sums, ScenarioInputs(df_, ds, inp.inflation_pct, inp.premium_adjustment_pct,
                                                  inp.expense_ratio_pct, inp.target_loss_ratio_pct))
            lr_row.append(round(pt["loss_ratio"], 6))
            m_row.append(round(pt["underwriting_margin"], 6))
        lr_grid.append(lr_row)
        margin_grid.append(m_row)

    # Compare equal one-at-a-time shocks; these are arithmetic effects, not data-estimated rankings.
    drivers = {
        "frequency_change_pct": "Claim frequency", "severity_change_pct": "Claim severity",
        "inflation_pct": "Claim-cost inflation", "premium_adjustment_pct": "Premium",
    }
    tornado = []
    for field, label in drivers.items():
        lo_i = ScenarioInputs(**{**asdict(zero), field: -TORNADO_SHOCK})
        hi_i = ScenarioInputs(**{**asdict(zero), field: TORNADO_SHOCK})
        lr_lo = _point(base_sums, lo_i)["loss_ratio"]
        try:
            lr_hi = _point(base_sums, hi_i)["loss_ratio"]
        except ScenarioError:
            lr_hi = None
        tornado.append({
            "driver": label, "shock_pct": TORNADO_SHOCK,
            "loss_ratio_at_minus": round(lr_lo, 6),
            "loss_ratio_at_plus": None if lr_hi is None else round(lr_hi, 6),
            "swing_percentage_points": None if lr_hi is None else round(abs(lr_hi - lr_lo) * 100, 4),
        })

    # Same assumptions applied to each policy type
    by_type = []
    for ptype in sorted(df["PolicyType"].dropna().unique()):
        part = df[df["PolicyType"] == ptype]
        try:
            bs = _base_from(part)
        except ScenarioError:
            continue
        b = _point(bs, zero)
        try:
            s = _point(bs, inp)
        except ScenarioError as exc:
            by_type.append({
                "policy_type": ptype, "policies": bs["policies"], "scenario_error": str(exc),
                "base_loss_ratio": round(b["loss_ratio"], 6), "scenario_loss_ratio": None,
                "base_expected_claim_cost": round(b["expected_claim_cost"], 2),
                "scenario_expected_claim_cost": None, "scenario_underwriting_margin": None,
            })
            continue
        by_type.append({
            "policy_type": ptype, "policies": bs["policies"],
            "base_loss_ratio": round(b["loss_ratio"], 6), "scenario_loss_ratio": round(s["loss_ratio"], 6),
            "base_expected_claim_cost": round(b["expected_claim_cost"], 2),
            "scenario_expected_claim_cost": round(s["expected_claim_cost"], 2),
            "scenario_underwriting_margin": round(s["underwriting_margin"], 6),
        })

    return {
        "disclaimer": DISCLAIMER,
        "inputs": asdict(inp),
        "base": _round_point(base),
        "scenario": _round_point(scen),
        "change": _delta(base, scen),
        "profitability_indicator": {
            "label": "Illustrative underwriting margin = 1 - loss ratio - expense ratio",
            "base_margin": round(base["underwriting_margin"], 6),
            "scenario_margin": round(scen["underwriting_margin"], 6),
            "scenario_result": round(scen["underwriting_result"], 2),
            "scenario_is_profitable": bool(scen["underwriting_margin"] > 0),
            "excludes": "investment income, reinsurance, capital cost, taxes, IBNR",
        },
        "premium_needed": {
            "for_target_loss_ratio": {"target_loss_ratio_pct": inp.target_loss_ratio_pct,
                                      "required_earned_premium": round(req_target, 2),
                                      "change_vs_base_premium_pct": round((req_target / base["earned_premium"] - 1) * 100, 2)},
            "to_break_even": {"required_earned_premium": round(req_break_even, 2),
                              "change_vs_base_premium_pct": round((req_break_even / base["earned_premium"] - 1) * 100, 2),
                              "definition": "premium at which loss ratio + expense ratio = 100%"},
        },
        "baseline_uncertainty": {
            "claim_frequency_ci_95": [lo, hi],
            "frequency_half_width_pct_of_estimate": noise_pct,
            "note": "The baseline frequency itself carries sampling error of about this size; frequency shocks smaller "
                    "than this cannot be distinguished from noise in this dataset.",
        },
        "sensitivity_grid": {
            "rows": "severity change %", "columns": "frequency change %",
            "severity_changes_pct": GRID_STEPS, "frequency_changes_pct": GRID_STEPS,
            "loss_ratio": lr_grid, "underwriting_margin": margin_grid,
            "held_constant": {"inflation_pct": inp.inflation_pct, "premium_adjustment_pct": inp.premium_adjustment_pct,
                              "expense_ratio_pct": inp.expense_ratio_pct},
        },
        "one_at_a_time_sensitivity": tornado,
        "sensitivity_comparison_note": (
            f"Unranked arithmetic comparison: each driver is changed alone by +/-{TORNADO_SHOCK:g}% from the same "
            "observed baseline, with other assumptions held at zero. Shocks are not estimated from experience. "
            "Frequency is a per-policy incidence proportion and cannot exceed 100%; an infeasible result is unavailable."
        ),
        "by_policy_type": by_type,
        "formulas": FORMULAS,
        "assumptions": [
            "Base experience is the observed incurred claims (Settled + Pending) and the earned-premium proxy.",
            "No IBNR, claim development, trend, seasonality or policy-count changes are modelled.",
            "Frequency, severity, inflation and premium shocks are multiplicative and independent.",
            f"Expense ratio ({inp.expense_ratio_pct:g}%) and target loss ratio ({inp.target_loss_ratio_pct:g}%) are user assumptions, not data.",
        ],
    }


# =========================================================================== #
# Scenario comparison: Baseline / Optimistic / Stress / Custom
# =========================================================================== #
PRESET_NOTE = ("Optimistic and Stress are illustrative assumptions chosen for this exercise. They are not estimated from "
               "the data, not forecasts, and not regulatory stress tests. Edit the sliders to define your own.")

PRESETS = [
    {"key": "baseline", "label": "Baseline",
     "description": "Observed experience with no adjustments.",
     "inputs": {"frequency_change_pct": 0.0, "severity_change_pct": 0.0, "inflation_pct": 0.0, "premium_adjustment_pct": 0.0}},
    {"key": "optimistic", "label": "Optimistic",
     "description": "Fewer claims, slightly smaller claims, mild cost inflation and a modest rate increase.",
     "inputs": {"frequency_change_pct": -10.0, "severity_change_pct": -5.0, "inflation_pct": 2.0, "premium_adjustment_pct": 5.0}},
    {"key": "stress", "label": "Stress",
     "description": "More claims, larger claims, high cost inflation and no rate increase.",
     "inputs": {"frequency_change_pct": 15.0, "severity_change_pct": 10.0, "inflation_pct": 8.0, "premium_adjustment_pct": 0.0}},
]
CUSTOM_DESCRIPTION = "Your own assumptions, set with the sliders."

# A preset outside the allowed ranges is a programming error: fail at import time, not at request time.
for _p in PRESETS:
    ScenarioInputs(**_p["inputs"]).validate()

_MONEY_RESULTS = {"adjusted_claim_severity", "adjusted_expected_claim_cost", "adjusted_premium", "baseline_claim_cost",
                  "pure_premium", "underwriting_result"}


def _usd(x: float) -> str:
    return f"{x:,.2f}"


def _pc(x: float, digits: int = 2) -> str:
    return f"{x * 100:.{digits}f}%"


def _adj(pct: float) -> str:
    return f"(1 {'+' if pct >= 0 else '-'} {abs(pct):.1f}%)"


def explain_steps(base: dict, inp: ScenarioInputs, pt: dict) -> list[dict]:
    """The scenario calculation, one step at a time, with the actual numbers substituted in."""
    n = base["policies"]
    f0 = base["claims"] / n
    s0 = base["incurred"] / base["claims"]
    cost0 = n * f0 * s0

    def step(label, formula, substitution, value, fmt, explanation, digits=None):
        out = {"label": label, "formula": formula, "substitution": substitution,
               "value": round(value, 2 if fmt in ("amount", "amount2") else 6), "format": fmt, "explanation": explanation}
        if digits is not None:
            out["digits"] = digits
        return out

    return [
        step("Baseline claim cost", "policies x baseline claim frequency x baseline claim severity",
             f"{n:,} x {_pc(f0)} x {_usd(s0)}", cost0, "amount",
             "The observed incurred claims (Settled plus Pending) in the selected scope. Nothing is adjusted yet."),
        step("Adjusted claim frequency", "baseline frequency x (1 + frequency adjustment)",
             f"{_pc(f0)} x {_adj(inp.frequency_change_pct)}", pt["claim_frequency"], "percent",
             "Frequency is the share of policies with a claim. The adjustment scales that share up or down.", digits=2),
        step("Adjusted claim severity", "baseline severity x (1 + severity adjustment) x (1 + claim inflation)",
             f"{_usd(s0)} x {_adj(inp.severity_change_pct)} x {_adj(inp.inflation_pct)}", pt["claim_severity"], "amount2",
             "Severity is the average cost of a claim. Inflation is applied on top of any severity adjustment, "
             "so the two effects multiply."),
        step("Adjusted expected claim cost", "policies x adjusted frequency x adjusted severity",
             f"{n:,} x {_pc(pt['claim_frequency'])} x {_usd(pt['claim_severity'])}", pt["expected_claim_cost"], "amount",
             "Expected number of claiming policies times the adjusted average claim. This is the portfolio's claim cost "
             "if the assumptions held."),
        step("Adjusted premium", "baseline earned premium x (1 + premium adjustment)",
             f"{_usd(base['earned'])} x {_adj(inp.premium_adjustment_pct)}", pt["earned_premium"], "amount",
             "Earned premium is the part of written premium that relates to cover already provided. "
             "The adjustment represents a change of rates."),
        step("Adjusted loss ratio", "adjusted expected claim cost / adjusted premium",
             f"{_usd(pt['expected_claim_cost'])} / {_usd(pt['earned_premium'])}", pt["loss_ratio"], "percent",
             "Claims as a share of premium. Above 100% the claims exceed the premium before any expenses.", digits=1),
        step("Illustrative underwriting margin", "1 - adjusted loss ratio - expense ratio",
             f"1 - {_pc(pt['loss_ratio'])} - {_pc(pt['expense_ratio'])}", pt["underwriting_margin"], "percent",
             "What is left of each unit of premium after claims and the ASSUMED expenses. Investment income, reinsurance, "
             "capital cost, taxes and IBNR are ignored.", digits=1),
    ]


def _results(base_pt: dict, pt: dict) -> dict:
    raw = {
        "baseline_claim_cost": base_pt["expected_claim_cost"],
        "adjusted_claim_frequency": pt["claim_frequency"],
        "adjusted_claim_severity": pt["claim_severity"],
        "adjusted_expected_claim_cost": pt["expected_claim_cost"],
        "adjusted_premium": pt["earned_premium"],
        "adjusted_loss_ratio": pt["loss_ratio"],
        "expected_claims": pt["expected_claims"],
        "pure_premium": pt["pure_premium"],
        "expense_ratio": pt["expense_ratio"],
        "combined_ratio": pt["combined_ratio"],
        "underwriting_margin": pt["underwriting_margin"],
        "underwriting_result": pt["underwriting_result"],
    }
    return {k: round(v, 2 if (k in _MONEY_RESULTS or k == "expected_claims") else 6) for k, v in raw.items()}


def compare_scenarios(df: pd.DataFrame, custom: ScenarioInputs) -> dict:
    """Baseline, Optimistic, Stress and Custom computed side by side on the same portfolio and shared assumptions."""
    custom.validate()
    base_sums = _base_from(df)
    shared = {"expense_ratio_pct": custom.expense_ratio_pct, "target_loss_ratio_pct": custom.target_loss_ratio_pct}

    entries = [(p["key"], p["label"], p["description"], True, ScenarioInputs(**p["inputs"], **shared)) for p in PRESETS]
    entries.append(("custom", "Custom", CUSTOM_DESCRIPTION, False, custom))

    base_pt = _point(base_sums, entries[0][4])
    scenarios = []
    for key, label, description, is_preset, inp in entries:
        try:
            pt = _point(base_sums, inp)
        except ScenarioError as exc:
            scenarios.append({
                "key": key, "label": label, "description": description, "is_preset": is_preset,
                "inputs": {k: v for k, v in asdict(inp).items()}, "results": None,
                "validation_error": str(exc), "change_vs_baseline": None,
                "premium_change_to_break_even_pct": None, "is_profitable": None, "steps": [],
            })
            continue
        exp = inp.expense_ratio_pct / 100
        break_even = pt["expected_claim_cost"] / (1 - exp)
        scenarios.append({
            "key": key, "label": label, "description": description, "is_preset": is_preset,
            "inputs": {k: v for k, v in asdict(inp).items()},
            "results": _results(base_pt, pt),
            "change_vs_baseline": {
                "expected_claim_cost_pct": round((pt["expected_claim_cost"] / base_pt["expected_claim_cost"] - 1) * 100, 4),
                "premium_pct": round((pt["earned_premium"] / base_pt["earned_premium"] - 1) * 100, 4),
                "loss_ratio_points": round((pt["loss_ratio"] - base_pt["loss_ratio"]) * 100, 4),
            },
            "premium_change_to_break_even_pct": round((break_even / base_pt["earned_premium"] - 1) * 100, 2),
            "is_profitable": bool(pt["underwriting_margin"] > 0),
            "steps": explain_steps(base_sums, inp, pt),
        })

    n = base_sums["policies"]
    return {
        "disclaimer": DISCLAIMER,
        "preset_note": PRESET_NOTE,
        "baseline": {
            "policies": n, "claiming_policies": base_sums["claims"],
            "claim_frequency": round(base_sums["claims"] / n, 6),
            "claim_severity": round(base_sums["incurred"] / base_sums["claims"], 2),
            "claim_cost": round(base_sums["incurred"], 2), "earned_premium": round(base_sums["earned"], 2),
        },
        "shared_assumptions": {
            "expense_ratio_pct": custom.expense_ratio_pct,
            "expense_ratio_note": "Assumed by the user, not taken from the data.",
            "target_loss_ratio_pct": custom.target_loss_ratio_pct,
        },
        "scenarios": scenarios,
        "formulas": FORMULAS,
        "assumptions": [
            "Base experience is the observed incurred claims (Settled + Pending) and the earned-premium proxy.",
            "No IBNR, claim development, trend, seasonality or change in the number of policies is modelled.",
            "Frequency, severity, inflation and premium adjustments are multiplicative and independent.",
            "All scenarios share the same expense ratio and target loss ratio.",
            "Numbers shown in the step-by-step substitutions are rounded for display; calculations use full precision.",
        ],
        "limitations": [
            "Scenario analysis shows arithmetic consequences of assumptions; it does not say how likely any scenario is.",
            "Baseline frequency and severity carry sampling error (see baseline uncertainty on the detailed analysis).",
            "The underwriting margin is illustrative and excludes investment income, reinsurance, capital and taxes.",
        ],
    }
