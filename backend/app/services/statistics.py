"""
Small, dependency-free hypothesis tests (NumPy/math only) used to avoid over-reading segment differences.

* chi_square_homogeneity: "is the claim rate the same across groups?"
* one_way_anova:          "is the mean claim size the same across groups?"
* z_test_vs_expected:     "is actual claim count different from expected?"

p-values come from the chi-square and F distributions, implemented via the regularised
incomplete gamma / beta functions (Numerical Recipes style) and checked against SciPy in the tests.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

ALPHA = 0.05


# --------------------------------------------------------------------------- #
# Distribution functions
# --------------------------------------------------------------------------- #
def regularized_gamma_q(a: float, x: float) -> float:
    """Upper regularised incomplete gamma Q(a, x)."""
    if a <= 0 or x < 0:
        raise ValueError("require a > 0 and x >= 0")
    if x == 0:
        return 1.0
    log_pref = -x + a * math.log(x) - math.lgamma(a)
    if x < a + 1:  # series for P(a, x)
        ap, term = a, 1.0 / a
        total = term
        for _ in range(2000):
            ap += 1
            term *= x / ap
            total += term
            if abs(term) < abs(total) * 1e-15:
                break
        return max(0.0, 1.0 - total * math.exp(log_pref))
    tiny = 1e-300  # continued fraction for Q(a, x), modified Lentz
    b = x + 1 - a
    c = 1 / tiny
    d = 1 / b
    h = d
    for i in range(1, 2000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = tiny if abs(d) < tiny else d
        c = b + an / c
        c = tiny if abs(c) < tiny else c
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-15:
            break
    return min(1.0, math.exp(log_pref) * h)


def chi2_sf(x: float, dof: int) -> float:
    """P(Chi2_dof >= x)."""
    return 1.0 if x <= 0 else regularized_gamma_q(dof / 2.0, x / 2.0)


def _betacf(a: float, b: float, x: float) -> float:
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1, a - 1
    c = 1.0
    d = 1 - qab * x / qap
    d = tiny if abs(d) < tiny else d
    d = 1 / d
    h = d
    for m in range(1, 2000):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        d = tiny if abs(d) < tiny else d
        c = 1 + aa / c
        c = tiny if abs(c) < tiny else c
        d = 1 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        d = tiny if abs(d) < tiny else d
        c = 1 + aa / c
        c = tiny if abs(c) < tiny else c
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-15:
            break
    return h


def regularized_beta(x: float, a: float, b: float) -> float:
    """Regularised incomplete beta I_x(a, b)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1) / (a + b + 2):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1 - x) / b


def f_sf(f: float, d1: int, d2: int) -> float:
    """P(F_{d1,d2} >= f)."""
    if f <= 0:
        return 1.0
    return regularized_beta(d2 / (d2 + d1 * f), d2 / 2.0, d1 / 2.0)


def normal_two_sided_p(z: float) -> float:
    return math.erfc(abs(z) / math.sqrt(2))


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
def _verdict(p: float, what: str) -> str:
    if p < ALPHA:
        return (f"Statistically significant at the 5% level (p = {p:.3f}): {what} differs between groups by more "
                "than random variation would usually explain. Still not evidence of causation.")
    return (f"Not statistically significant (p = {p:.3f}): observed differences in {what} are consistent with random variation.")


def chi_square_homogeneity(claims: list[int], policies: list[int]) -> dict:
    """Chi-square test that the claim rate is equal in every group (2 x k table)."""
    pairs = [(int(c), int(n)) for c, n in zip(claims, policies) if n > 0]
    k = len(pairs)
    total_n = sum(n for _, n in pairs)
    total_c = sum(c for c, _ in pairs)
    if k < 2 or total_c == 0 or total_c == total_n:
        return {"test": "chi-square test of homogeneity (claim rate)", "computable": False,
                "reason": "needs at least two non-empty groups and a mix of claiming and non-claiming policies"}
    p_all = total_c / total_n
    chi2 = 0.0
    min_expected = float("inf")
    for c, n in pairs:
        e_claim, e_none = n * p_all, n * (1 - p_all)
        min_expected = min(min_expected, e_claim, e_none)
        chi2 += (c - e_claim) ** 2 / e_claim + ((n - c) - e_none) ** 2 / e_none
    dof = k - 1
    p = chi2_sf(chi2, dof)
    return {
        "test": "chi-square test of homogeneity (claim rate)", "computable": True,
        "statistic": round(chi2, 4), "degrees_of_freedom": dof, "p_value": round(p, 6),
        "significant_at_5pct": bool(p < ALPHA),
        "approximation_reliable": bool(min_expected >= 5),
        "interpretation": _verdict(p, "claim frequency"),
    }


def one_way_anova(groups: list[np.ndarray]) -> dict:
    """One-way ANOVA F-test that mean claim size is equal across groups."""
    arrays = [np.asarray(g, dtype=float) for g in groups if len(g) > 0]
    k = len(arrays)
    n_total = sum(len(a) for a in arrays)
    name = "one-way ANOVA (mean claim severity)"
    if k < 2 or n_total - k <= 0:
        return {"test": name, "computable": False, "reason": "needs at least two groups with claims"}
    grand = np.concatenate(arrays).mean()
    ssb = sum(len(a) * (a.mean() - grand) ** 2 for a in arrays)
    ssw = sum(((a - a.mean()) ** 2).sum() for a in arrays)
    if ssw == 0:
        return {"test": name, "computable": False, "reason": "no variation within groups"}
    d1, d2 = k - 1, n_total - k
    f = (ssb / d1) / (ssw / d2)
    p = f_sf(f, d1, d2)
    return {
        "test": name, "computable": True, "statistic": round(float(f), 4),
        "degrees_of_freedom": [d1, d2], "p_value": round(p, 6),
        "significant_at_5pct": bool(p < ALPHA),
        "interpretation": _verdict(p, "average claim size"),
    }


def z_test_vs_expected(actual: int, n: int, expected_rate: float | None) -> dict:
    """Is the actual claim count different from n x expected_rate? (normal approximation to the binomial)"""
    if n <= 0 or expected_rate is None or not (0 < expected_rate < 1):
        return {"expected_claims": None, "actual_to_expected": None, "z_score": None, "p_value": None,
                "significant_at_5pct": None}
    expected = n * expected_rate
    sd = math.sqrt(n * expected_rate * (1 - expected_rate))
    z = (actual - expected) / sd
    p = normal_two_sided_p(z)
    return {"expected_claims": round(expected, 2), "actual_to_expected": round(actual / expected, 6),
            "z_score": round(z, 4), "p_value": round(p, 6), "significant_at_5pct": bool(p < ALPHA)}


# --------------------------------------------------------------------------- #
# DataFrame wrappers
# --------------------------------------------------------------------------- #
def segment_significance(df: pd.DataFrame, column: str, order: list | None = None) -> dict:
    keys = order if order is not None else sorted(df[column].dropna().unique().tolist())
    claims, policies, sev_groups = [], [], []
    for key in keys:
        part = df[df[column] == key]
        policies.append(len(part))
        claims.append(int(part["IsClaim"].sum()))
        sev_groups.append(part.loc[part["IsClaim"], "IncurredAmount"].to_numpy())
    return {
        "claim_frequency": chi_square_homogeneity(claims, policies),
        "claim_severity": one_way_anova(sev_groups),
        "caution": "Each test is run once per dimension at the 5% level; with several dimensions tested, "
                   "an occasional 'significant' result is expected by chance alone.",
    }
