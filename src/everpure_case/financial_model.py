"""Illustrative event-time economics and an independent closed-form expectation."""

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from everpure_case.reactivation_scenarios import PROVENANCE
from everpure_case.source_integrity import EXPECTED_SHA256

ASSUMPTIONS_PATH = "docs/PHASE_3_FINANCIAL_ASSUMPTIONS.json"
SCENARIOS = ("conservative", "base", "optimistic")


def fingerprint(values: dict) -> str:
    """Hash actual canonical values, excluding only the stored fingerprint itself."""
    payload = {key: value for key, value in values.items() if key != "fingerprint_sha256"}
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_assumptions(a: dict, phase2_contract: dict) -> None:
    required = {
        "version",
        "provenance",
        "reporting_label",
        "source_sha256",
        "phase2_contract_version",
        "phase2_assumption_fingerprint_sha256",
        "valuation_origin",
        "currency",
        "horizon_months",
        "continuous_month_definition",
        "monthly_gross_revenue_per_reactivated_account",
        "contribution_margin",
        "outreach_cost_per_target",
        "activation_cost_per_reactivation",
        "annual_effective_financial_discount_rate",
        "commercial_discount_tiers",
        "simulations_per_cell",
        "seed",
        "numpy_bit_generator",
        "account_order",
        "scenario_random_number_policy",
        "source_discount_attribute_context",
        "root_dependence_policy",
        "revenue_recognition_rule",
        "revenue_collection_rule",
        "activation_cost_timing",
        "outreach_cost_timing",
        "retention_policy",
        "ongoing_servicing_costs",
        "parameter_uncertainty_policy",
        "counterfactual_policy",
        "missing_feature_policy",
        "eligibility_policy",
        "assessment_brief_status",
        "fingerprint_sha256",
    }
    if set(a) != required:
        raise ValueError(f"Financial assumption keys differ: {required ^ set(a)}")
    if a["fingerprint_sha256"] != fingerprint(a):
        raise ValueError("Financial assumption fingerprint mismatch")
    if (
        a["version"] != "phase3-financial-assumptions-v1"
        or a["provenance"] != PROVENANCE
        or a["source_sha256"] != EXPECTED_SHA256
        or a["phase2_contract_version"] != phase2_contract["version"]
        or a["phase2_assumption_fingerprint_sha256"]
        != phase2_contract["assumption_fingerprint_sha256"]
        or a["valuation_origin"] != phase2_contract["analysis_as_of_date"]
        or a["numpy_bit_generator"] != "PCG64"
    ):
        raise ValueError("Financial assumption provenance mismatch")
    for key in (
        "monthly_gross_revenue_per_reactivated_account",
        "outreach_cost_per_target",
        "activation_cost_per_reactivation",
        "annual_effective_financial_discount_rate",
    ):
        if not math.isfinite(a[key]) or a[key] < 0:
            raise ValueError(f"Invalid {key}")
    if not math.isfinite(a["contribution_margin"]) or not 0 <= a["contribution_margin"] <= 1:
        raise ValueError("Invalid contribution margin")
    if (
        not isinstance(a["horizon_months"], int)
        or a["horizon_months"] != 12
        or not isinstance(a["simulations_per_cell"], int)
        or a["simulations_per_cell"] != 1000
        or not isinstance(a["seed"], int)
        or a["seed"] != 20261009
    ):
        raise ValueError("Unsupported horizon, simulation count or seed")
    if len(a["commercial_discount_tiers"]) != 3 or any(
        not math.isfinite(v) or not 0 <= v <= 1 for v in a["commercial_discount_tiers"].values()
    ):
        raise ValueError("Invalid commercial discount tiers")
    if set(a["commercial_discount_tiers"]) != {"low_5pct", "medium_15pct", "high_30pct"}:
        raise ValueError("Commercial discount tier names changed")
    ordered = [
        a["commercial_discount_tiers"][name] for name in ("low_5pct", "medium_15pct", "high_30pct")
    ]
    if ordered != sorted(ordered):
        raise ValueError("Commercial discounts must be ordered")
    if ordered != [0.05, 0.15, 0.30]:
        raise ValueError("Unsupported commercial discount tier values")
    context = a["source_discount_attribute_context"]
    if (
        context.get("field") != "discount_tier_pct"
        or context.get("full_source_range_pct") != [5.0, 65.0]
        or not math.isclose(
            context.get("primary_cohort_mean_pct", float("nan")),
            34.8583916083916,
            rel_tol=0,
            abs_tol=1e-10,
        )
        or context.get("used_as_new_offer_or_response_evidence") is not False
    ):
        raise ValueError("Source discount attribute context mismatch")


def load_assumptions(root: Path, contract: dict) -> dict:
    a = json.loads((root / ASSUMPTIONS_PATH).read_text(encoding="utf-8"))
    validate_assumptions(a, contract)
    return a


def discount_factor(t: np.ndarray | float, annual_rate: float) -> np.ndarray:
    if not np.isfinite(annual_rate) or annual_rate < 0:
        raise ValueError("Invalid financial discount rate")
    return np.exp(-np.log1p(annual_rate) * np.asarray(t) / 12)


def event_times(uniforms: np.ndarray, hazards: np.ndarray) -> np.ndarray:
    """One exponentially distributed first event per account and replication."""
    u = np.asarray(uniforms, dtype=float)
    h = np.asarray(hazards, dtype=float)
    if (
        u.ndim != 2
        or h.ndim != 1
        or u.shape[1] != len(h)
        or not len(h)
        or not np.isfinite(u).all()
        or ((u <= 0) | (u >= 1)).any()
        or not np.isfinite(h).all()
        or (h < 0).any()
    ):
        raise ValueError("Invalid uniforms or hazards")
    with np.errstate(divide="ignore"):
        return -np.log1p(-u) / h


def account_expectation(
    hazards: np.ndarray,
    a: dict,
    commercial_discount: float,
    *,
    retention_paid_months: int | None = None,
) -> pd.DataFrame:
    """Closed-form marginal expectation; no sampled event times enter this calculation."""
    h = np.asarray(hazards, dtype=float)
    if h.ndim != 1 or not np.isfinite(h).all() or (h < 0).any():
        raise ValueError("Invalid account hazards")
    if not np.isfinite(commercial_discount) or not 0 <= commercial_discount <= 1:
        raise ValueError("Invalid commercial discount")
    horizon = a["horizon_months"]
    if retention_paid_months is not None and (
        not isinstance(retention_paid_months, int) or retention_paid_months < 0
    ):
        raise ValueError("Invalid retention cap")
    months = np.arange(1, horizon + 1, dtype=float)
    eligible = -np.expm1(-h[:, None] * (months - 1))
    if retention_paid_months is not None:
        earlier = np.maximum(0, months - 1 - retention_paid_months)
        eligible += np.expm1(-h[:, None] * earlier)
    pv_paid_months = eligible @ discount_factor(
        months, a["annual_effective_financial_discount_rate"]
    )
    gross_pv = a["monthly_gross_revenue_per_reactivated_account"] * pv_paid_months
    contribution_pv = gross_pv * (1 - commercial_discount) * a["contribution_margin"]
    d = np.log1p(a["annual_effective_financial_discount_rate"]) / 12
    rate = h + d
    activation_factor = np.zeros_like(h)
    np.divide(h * -np.expm1(-rate * horizon), rate, out=activation_factor, where=rate > 0)
    activation_pv = a["activation_cost_per_reactivation"] * activation_factor
    return pd.DataFrame(
        {
            "expected_reactivation_probability": -np.expm1(-h * horizon),
            "expected_billed_account_probability": -np.expm1(-h * max(horizon - 1, 0)),
            "expected_pv_gross_revenue": gross_pv,
            "expected_pv_gross_contribution": gross_pv * a["contribution_margin"],
            "expected_pv_contribution": contribution_pv,
            "expected_pv_activation_cost": activation_pv,
            "allocated_outreach_cost": np.full(len(h), a["outreach_cost_per_target"]),
            "expected_account_npv": contribution_pv - activation_pv - a["outreach_cost_per_target"],
            "activation_discount_factor_integral": activation_factor,
            "paid_month_pv_factor": pv_paid_months,
        }
    )


def pathwise(
    times: np.ndarray, a: dict, commercial_discount: float
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Vectorized pathwise cash flows at precise billing and event times."""
    t = np.asarray(times, dtype=float)
    if t.ndim != 2 or np.isnan(t).any() or (t < 0).any():
        raise ValueError("Invalid event-time matrix")
    if not np.isfinite(commercial_discount) or not 0 <= commercial_discount <= 1:
        raise ValueError("Invalid commercial discount")
    horizon = a["horizon_months"]
    n_runs, n_accounts = t.shape
    event = t <= horizon
    activation = (
        np.sum(
            np.where(event, discount_factor(t, a["annual_effective_financial_discount_rate"]), 0),
            axis=1,
        )
        * a["activation_cost_per_reactivation"]
    )
    event_count = event.sum(axis=1)
    month = np.arange(1, horizon + 1)
    eligible_counts = np.stack([(t <= m - 1).sum(axis=1) for m in month], axis=1)
    gross_month = eligible_counts * a["monthly_gross_revenue_per_reactivated_account"]
    discounted_month = gross_month * (1 - commercial_discount)
    contribution_month = discounted_month * a["contribution_margin"]
    factors = discount_factor(month, a["annual_effective_financial_discount_rate"])
    contribution_pv = contribution_month @ factors
    outreach = n_accounts * a["outreach_cost_per_target"]
    activation_nominal = event_count * a["activation_cost_per_reactivation"]
    run = pd.DataFrame(
        {
            "reactivation_count": event_count,
            "billed_account_count": (t <= horizon - 1).sum(axis=1),
            "gross_revenue": gross_month.sum(axis=1),
            "commercial_discount_deduction": (gross_month - discounted_month).sum(axis=1),
            "commercially_discounted_revenue": discounted_month.sum(axis=1),
            "contribution": contribution_month.sum(axis=1),
            "outreach_cost": np.full(n_runs, outreach),
            "activation_cost": activation_nominal,
            "undiscounted_net_cashflow": contribution_month.sum(axis=1)
            - activation_nominal
            - outreach,
            "pv_contribution": contribution_pv,
            "pv_activation_cost": activation,
            "npv": contribution_pv - activation - outreach,
        }
    )
    monthly = pd.DataFrame(
        {
            "month": np.r_[0, month],
            "mean_gross_revenue": np.r_[0, gross_month.mean(axis=0)],
            "mean_commercial_discount_deduction": np.r_[
                0, (gross_month - discounted_month).mean(axis=0)
            ],
            "mean_discounted_revenue": np.r_[0, discounted_month.mean(axis=0)],
            "mean_contribution": np.r_[0, contribution_month.mean(axis=0)],
            "mean_pv_contribution": np.r_[0, (contribution_month * factors).mean(axis=0)],
            "mean_outreach_cost": np.r_[outreach, np.zeros(horizon)],
            "mean_activation_cost": np.r_[
                (t == 0).sum(axis=1).mean() * a["activation_cost_per_reactivation"],
                [
                    (
                        a["activation_cost_per_reactivation"] * ((t > m - 1) & (t <= m)).sum(axis=1)
                    ).mean()
                    for m in month
                ],
            ],
            "mean_pv_activation_cost": np.r_[
                (t == 0).sum(axis=1).mean() * a["activation_cost_per_reactivation"],
                [
                    (
                        a["activation_cost_per_reactivation"]
                        * np.where(
                            (t > m - 1) & (t <= m),
                            discount_factor(t, a["annual_effective_financial_discount_rate"]),
                            0,
                        ).sum(axis=1)
                    ).mean()
                    for m in month
                ],
            ],
        }
    )
    monthly["mean_net_cashflow"] = (
        monthly.mean_contribution - monthly.mean_outreach_cost - monthly.mean_activation_cost
    )
    monthly["mean_pv_net_cashflow"] = (
        monthly.mean_pv_contribution - monthly.mean_outreach_cost - monthly.mean_pv_activation_cost
    )
    return run, monthly


def summarize(run: pd.DataFrame, analytic_npv: float) -> dict:
    values = run.npv.to_numpy()
    n = len(values)
    sd = float(np.std(values, ddof=1))
    se = sd / np.sqrt(n)
    result = {
        "simulation_count": n,
        "mean_npv": float(values.mean()),
        "median_npv": float(np.median(values)),
        "sd_npv": sd,
        "p05_npv": float(np.quantile(values, 0.05)),
        "p95_npv": float(np.quantile(values, 0.95)),
        "probability_negative_npv": float(np.mean(values < 0)),
        "min_npv": float(values.min()),
        "max_npv": float(values.max()),
        "mc_standard_error": se,
        "analytic_expected_npv": analytic_npv,
        "mc_minus_analytic": float(values.mean() - analytic_npv),
        "standardized_discrepancy": float((values.mean() - analytic_npv) / se) if se else 0.0,
    }
    for key in run.columns.drop("npv"):
        result[f"mean_{key}"] = float(run[key].mean())
    return result
