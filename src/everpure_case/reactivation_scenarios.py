"""Observed Phase 1 features plus explicit assumptions; independent of synthetic Cox."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from everpure_case.ingestion import read_source
from everpure_case.source_integrity import EXPECTED_SHA256, verify_authoritative_source
from everpure_case.survival import exponential_event_probability

PROVENANCE = "ASSUMPTION_BASED_NOT_CALIBRATED"
PRIMARY_POLICY = "reported_2y_scenario_cohort"
POLICIES = {
    PRIMARY_POLICY: {"primary_reported_2y"},
    "hypothetical_include_conflicts": {"primary_reported_2y", "eligibility_conflict"},
    "hypothetical_include_all": {
        "primary_reported_2y",
        "eligibility_conflict",
        "eligibility_unknown",
    },
}
ASSUMPTIONS_FILE = "docs/PHASE_2_ASSUMPTIONS.json"


def validate_assumptions(parameters: dict) -> None:
    """Reject stale, malformed, or order-inverting scenario parameters."""
    if parameters.get("version") != "phase2-assumptions-v1":
        raise ValueError("Unknown scenario parameter version")
    hazards_by_scenario = parameters["monthly_baseline_hazards"]
    scenario_order = ["conservative", "base", "optimistic"]
    if set(hazards_by_scenario) != set(scenario_order):
        raise ValueError("Scenario hazards must use the three named cases")
    hazards = [hazards_by_scenario[name] for name in scenario_order]
    if not all(np.isfinite(h) and h >= 0 for h in hazards) or hazards != sorted(hazards):
        raise ValueError("Scenario hazards must be finite, nonnegative, and ordered")
    if parameters["horizons_months"] != [3, 6, 12]:
        raise ValueError("Primary horizons changed")
    if not all(np.isfinite(v) for v in parameters["assumed_log_hazard_effects"].values()):
        raise ValueError("Non-finite assumed effect")


def load_assumptions(repo_root: str | Path) -> dict:
    parameters = json.loads((Path(repo_root) / ASSUMPTIONS_FILE).read_text(encoding="utf-8"))
    validate_assumptions(parameters)
    return parameters


def assumption_fingerprint(parameters: dict) -> str:
    """SHA-256 of canonical UTF-8 JSON for the complete assumption register."""
    validate_assumptions(parameters)
    canonical = json.dumps(
        parameters, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_phase1_accounts(repo_root: str | Path) -> pd.DataFrame:
    """Read approved, immutable Phase 1 artifacts and enforce account grain."""
    root = Path(repo_root)
    verify_authoritative_source(root)
    metrics = json.loads((root / "outputs/phase1/metrics.json").read_text(encoding="utf-8"))
    if (
        metrics["source_sha256"] != EXPECTED_SHA256
        or metrics["analysis_as_of_date"] != "2026-10-09"
    ):
        raise ValueError("Phase 1 metrics do not match the frozen baseline")
    base = root / "outputs/phase1"
    accounts = pd.read_csv(base / "cleaned_accounts.csv", dtype=str, keep_default_na=False)
    raw = read_source(root / "data/raw/Case_Study_1_Install_Base_Reactivation.csv")
    raw["source_row_number"] = raw["source_row_number"].astype(str)
    if not accounts[list(raw.columns)].equals(raw):
        raise ValueError("Phase 1 cleaned source columns no longer match authoritative source")
    hierarchy = pd.read_csv(base / "account_hierarchy.csv", dtype=str, keep_default_na=False)
    quality = pd.read_csv(base / "account_quality_summary.csv", dtype=str, keep_default_na=False)
    for name, frame in (("accounts", accounts), ("hierarchy", hierarchy), ("quality", quality)):
        if len(frame) != 2000 or frame.account_id.duplicated().any():
            raise ValueError(f"Invalid {name} account grain")
    if set(accounts.account_id) != set(hierarchy.account_id) or set(accounts.account_id) != set(
        quality.account_id
    ):
        raise ValueError("Phase 1 account sets do not match")
    joined = accounts.merge(
        hierarchy[["account_id", "root_account_id", "hierarchy_status"]],
        on="account_id",
        validate="one_to_one",
        how="left",
    )
    joined = joined.merge(
        quality[["account_id", "has_manual_review_exceptions"]],
        on="account_id",
        validate="one_to_one",
        how="left",
    )
    if (
        len(joined) != 2000
        or joined.root_account_id.eq("").any()
        or not joined.hierarchy_status.eq("resolved").all()
    ):
        raise ValueError("Unresolved or multiplied hierarchy mapping")
    expected_root = joined.parent_account_id.where(
        joined.parent_account_id.ne(""), joined.account_id
    )
    if not joined.root_account_id.eq(expected_root).all():
        raise ValueError("Hierarchy root mapping changed")
    raw_ticket = pd.to_numeric(joined.open_support_tickets, errors="coerce")
    cleaned_ticket = pd.to_numeric(joined.tickets_clean.replace("", np.nan), errors="coerce")
    if not cleaned_ticket.equals(raw_ticket.mask(raw_ticket.eq(999))):
        raise ValueError("Phase 1 valid ticket rule changed")
    expected_sentinel = raw_ticket.eq(999).map({True: "True", False: "False"})
    if not joined.ticket_sentinel.eq(expected_sentinel).all():
        raise ValueError("Phase 1 ticket sentinel flag changed")
    inactivity = pd.to_numeric(joined.years_inactive.replace("", np.nan), errors="coerce")
    expected_reported = pd.Series(
        np.where(inactivity.isna(), "", np.where(inactivity.ge(2), "True", "False")),
        index=joined.index,
    )
    if not joined.reported_2y_eligible.eq(expected_reported).all():
        raise ValueError("Phase 1 reported inactivity rule changed")
    if metrics["source_rows"] != len(joined) or metrics["reported_2y_eligible_rows"] != 1144:
        raise ValueError("Phase 1 population mismatch")
    return joined.sort_values("account_id").reset_index(drop=True)


def reconcile_cohort(accounts: pd.DataFrame) -> pd.DataFrame:
    if accounts.account_id.duplicated().any():
        raise ValueError("Duplicate account")
    status = np.select(
        [
            accounts.reported_2y_eligible.eq("True"),
            accounts.eligibility_comparison_status.eq("disagree"),
            accounts.eligibility_comparison_status.eq("unknown"),
        ],
        ["primary_reported_2y", "eligibility_conflict", "eligibility_unknown"],
        default="invalid",
    )
    if (status == "invalid").any():
        raise ValueError("Unrecognized Phase 1 eligibility state")
    frame = accounts[
        [
            "account_id",
            "root_account_id",
            "years_inactive",
            "reported_2y_eligible",
            "eligibility_comparison_status",
        ]
    ].copy()
    frame["scenario_cohort_status"] = status
    frame["source_provenance"] = "DERIVED_SOURCE"
    return frame


def engineer_features(accounts: pd.DataFrame) -> pd.DataFrame:
    """Keep missing states explicit; scoring uses documented reference levels."""
    if accounts.account_id.duplicated().any():
        raise ValueError("Duplicate account")
    if not accounts.health_clean.isin(["Green", "Yellow", "Red", ""]).all():
        raise ValueError("Invalid cleaned health")
    if not accounts.partner_managed_clean.isin(["0.00000000", "1.00000000", ""]).all():
        raise ValueError("Invalid cleaned ownership")
    tickets = pd.to_numeric(accounts.tickets_clean.replace("", np.nan), errors="coerce")
    if (accounts.tickets_clean.ne("") & tickets.isna()).any() or (tickets.dropna() < 0).any():
        raise ValueError("Invalid valid-ticket measurement")
    sentinel = accounts.ticket_sentinel.eq("True")
    if (sentinel & tickets.notna()).any():
        raise ValueError("Ticket sentinel became a valid count")
    fields = pd.DataFrame(
        {
            "account_id": accounts.account_id.to_numpy(),
            "root_account_id": accounts.root_account_id.to_numpy(),
            "health_clean": accounts.health_clean.to_numpy(),
            "health_unknown": accounts.health_clean.eq("").to_numpy(),
            "partner_managed_clean": accounts.partner_managed_clean.to_numpy(),
            "partner_unknown": accounts.partner_managed_clean.eq("").to_numpy(),
            "tickets_clean": tickets.to_numpy(),
            "tickets_missing": tickets.isna().to_numpy(),
            "ticket_sentinel": sentinel.to_numpy(),
            "is_child": accounts.parent_account_id.ne("").to_numpy(),
        }
    )
    fields["health_red"] = fields.health_clean.eq("Red").astype(float)
    fields["health_yellow"] = fields.health_clean.eq("Yellow").astype(float)
    fields["partner_managed_yes"] = fields.partner_managed_clean.eq("1.00000000").astype(float)
    fields["log1p_valid_tickets"] = np.log1p(fields.tickets_clean.fillna(0))
    fields["is_child"] = fields.is_child.astype(float)
    if not np.isfinite(
        fields[
            [
                "health_red",
                "health_yellow",
                "partner_managed_yes",
                "log1p_valid_tickets",
                "is_child",
            ]
        ].to_numpy()
    ).all():
        raise ValueError("Non-finite transformed feature")
    return fields


def project_accounts(
    accounts: pd.DataFrame,
    assumptions: dict,
    cohort_policy: str = PRIMARY_POLICY,
    *,
    hazard_multiplier: float = 1.0,
    effect_scale: float = 1.0,
    unknown_health_log_effect: float = 0.0,
    horizons: tuple[int, ...] = (3, 6, 12),
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Account x scenario x horizon assumed cumulative event probabilities."""
    validate_assumptions(assumptions)
    if cohort_policy not in POLICIES:
        raise ValueError("Unknown cohort policy")
    if not np.isfinite(hazard_multiplier) or hazard_multiplier < 0:
        raise ValueError("Invalid baseline hazard multiplier")
    if not np.isfinite(effect_scale):
        raise ValueError("Invalid effect scale")
    if not np.isfinite(unknown_health_log_effect):
        raise ValueError("Invalid unknown-health sensitivity effect")
    if not horizons or any(not np.isfinite(h) or h < 0 for h in horizons):
        raise ValueError("Invalid horizon")
    reconciliation = reconcile_cohort(accounts)
    features = engineer_features(accounts)
    selected = reconciliation[reconciliation.scenario_cohort_status.isin(POLICIES[cohort_policy])]
    selected = selected.merge(features, on=["account_id", "root_account_id"], validate="one_to_one")
    effects = assumptions["assumed_log_hazard_effects"]
    linear = (
        effect_scale * sum(selected[name].to_numpy() * value for name, value in effects.items())
        + selected.health_unknown.to_numpy() * unknown_health_log_effect
    )
    if not np.isfinite(linear).all():
        raise ValueError("Non-finite linear predictor")
    selected = selected.assign(assumed_log_hazard_linear_predictor=linear)
    results = []
    for scenario, baseline in assumptions["monthly_baseline_hazards"].items():
        for horizon in horizons:
            item = selected[
                [
                    "account_id",
                    "root_account_id",
                    "scenario_cohort_status",
                    "health_unknown",
                    "partner_unknown",
                    "tickets_missing",
                    "ticket_sentinel",
                    "assumed_log_hazard_linear_predictor",
                ]
            ].copy()
            item["analysis_as_of_date"] = assumptions["analysis_as_of_date"]
            item["scenario_name"] = scenario
            item["horizon_months"] = horizon
            item["assumed_baseline_hazard_per_month"] = baseline * hazard_multiplier
            item["cumulative_reactivation_probability"] = exponential_event_probability(
                baseline * hazard_multiplier, horizon, linear
            )
            item["scenario_parameter_version"] = assumptions["version"]
            item["probability_provenance"] = PROVENANCE
            item["source_baseline_sha"] = EXPECTED_SHA256
            item["cohort_policy"] = cohort_policy
            results.append(item)
    detail = (
        pd.concat(results, ignore_index=True)
        .sort_values(["account_id", "scenario_name", "horizon_months"])
        .reset_index(drop=True)
    )
    if detail.duplicated(["account_id", "scenario_name", "horizon_months"]).any():
        raise AssertionError("Duplicate account prediction")
    summary = (
        detail.groupby(["scenario_name", "horizon_months"], sort=True)
        .agg(
            cohort_accounts=("account_id", "size"),
            expected_reactivations=("cumulative_reactivation_probability", "sum"),
            mean_probability=("cumulative_reactivation_probability", "mean"),
            min_probability=("cumulative_reactivation_probability", "min"),
            median_probability=("cumulative_reactivation_probability", "median"),
            p10_probability=("cumulative_reactivation_probability", lambda x: x.quantile(0.1)),
            p90_probability=("cumulative_reactivation_probability", lambda x: x.quantile(0.9)),
            max_probability=("cumulative_reactivation_probability", "max"),
        )
        .reset_index()
    )
    summary["cohort_policy"] = cohort_policy
    summary["probability_provenance"] = PROVENANCE
    summary["scenario_parameter_version"] = assumptions["version"]
    return detail, summary


def scenario_sensitivity(accounts: pd.DataFrame, assumptions: dict) -> pd.DataFrame:
    """Vary hazard, effects, horizon, missing health, and population separately."""
    primary = reconcile_cohort(accounts).scenario_cohort_status.eq("primary_reported_2y")
    known_health = accounts.loc[primary & accounts.health_clean.ne(""), "health_clean"]
    if known_health.empty:
        raise ValueError("No observed health levels for sensitivity reference")
    effects = assumptions["assumed_log_hazard_effects"]
    observed_average_health_effect = float(
        known_health.eq("Yellow").mean() * effects["health_yellow"]
        + known_health.eq("Red").mean() * effects["health_red"]
    )
    cases = [
        ("primary_base", PRIMARY_POLICY, 1.0, 1.0, 0.0),
        ("half_baseline_hazard", PRIMARY_POLICY, 0.5, 1.0, 0.0),
        ("one_and_half_baseline_hazard", PRIMARY_POLICY, 1.5, 1.0, 0.0),
        ("zero_covariate_effects", PRIMARY_POLICY, 1.0, 0.0, 0.0),
        ("half_covariate_effects", PRIMARY_POLICY, 1.0, 0.5, 0.0),
        ("one_and_half_covariate_effects", PRIMARY_POLICY, 1.0, 1.5, 0.0),
        ("hypothetical_include_conflicts", "hypothetical_include_conflicts", 1.0, 1.0, 0.0),
        (
            "hypothetical_include_all_including_unknown",
            "hypothetical_include_all",
            1.0,
            1.0,
            0.0,
        ),
        ("unknown_health_as_yellow", PRIMARY_POLICY, 1.0, 1.0, effects["health_yellow"]),
        ("unknown_health_as_red", PRIMARY_POLICY, 1.0, 1.0, effects["health_red"]),
        (
            "unknown_health_observed_average",
            PRIMARY_POLICY,
            1.0,
            1.0,
            observed_average_health_effect,
        ),
    ]
    parts = []
    for label, policy, hazard_mult, effect_scale, unknown_effect in cases:
        _, summary = project_accounts(
            accounts,
            assumptions,
            policy,
            hazard_multiplier=hazard_mult,
            effect_scale=effect_scale,
            unknown_health_log_effect=unknown_effect,
        )
        summary = summary.loc[
            summary.scenario_name.eq("base"),
            ["horizon_months", "cohort_accounts", "expected_reactivations", "mean_probability"],
        ].copy()
        summary["sensitivity_case"] = label
        summary["cohort_policy"] = policy
        summary["baseline_hazard_multiplier"] = hazard_mult
        summary["effect_scale"] = effect_scale
        summary["unknown_health_log_effect"] = unknown_effect
        summary["unknown_health_effect_basis"] = (
            "observed primary-cohort health mix weighted by assumed effects"
            if label == "unknown_health_observed_average"
            else "assumed reference or named health level"
        )
        parts.append(summary)
    return (
        pd.concat(parts, ignore_index=True)
        .sort_values(["sensitivity_case", "horizon_months"])
        .reset_index(drop=True)
    )
