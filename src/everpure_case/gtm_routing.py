"""Pure account decision rules; economic priority and readiness remain separate."""

import math

CHANNELS = (
    "PARTNER_LED_CANDIDATE",
    "DIRECT_ENTERPRISE_CANDIDATE",
    "DIGITAL_NURTURE_CANDIDATE",
    "HOLD_REVIEW",
)


def route_account(a: dict, policy: dict) -> dict:
    """Route a validated enriched record. Never grants operational permission."""
    partner = a["partner_status"]
    health = a["health_status"]
    tickets = a["valid_open_tickets"]
    usage = a["monthly_usage_gb"]
    npv = float(a["expected_account_npv"])
    if partner not in {"YES", "NO", "UNKNOWN"} or health not in {
        "Green",
        "Yellow",
        "Red",
        "UNKNOWN",
    }:
        raise ValueError("Invalid source category")
    if not math.isfinite(npv) or (tickets is not None and (tickets < 0 or tickets == 999)):
        raise ValueError("Invalid financial or ticket value")
    if usage is not None and (not math.isfinite(usage) or usage < 0):
        raise ValueError("Invalid usage")
    critical = policy["service_backlog"]["critical_from_valid_tickets"]
    elevated = policy["service_backlog"]["elevated_from_valid_tickets"]
    if tickets is None:
        service = "UNKNOWN_SERVICE_EVIDENCE"
    elif tickets >= critical:
        service = "CRITICAL_BACKLOG"
    elif tickets >= elevated:
        service = "ELEVATED_BACKLOG"
    elif tickets > 0:
        service = "LOW_BACKLOG"
    else:
        service = "NO_OBSERVED_OPEN_BACKLOG"
    warnings = []
    if partner == "UNKNOWN":
        warnings.append("PARTNER_OWNERSHIP_UNRESOLVED")
    if health == "UNKNOWN":
        warnings.append("HEALTH_UNKNOWN")
    if tickets is None:
        warnings.append("TICKET_BACKLOG_UNKNOWN")
    if a["ticket_sentinel"]:
        warnings.append("TICKET_SENTINEL_999")
    if a["has_manual_review_exceptions"]:
        warnings.append("SOURCE_MANUAL_REVIEW")
    if usage is None:
        warnings.append("SCALE_UNKNOWN")
    warnings.append("FISCAL_ELIGIBILITY_UNCONFIRMED")
    if health == "Red":
        warnings.append("ACCOUNT_HEALTH_REVIEW_REQUIRED")
    if tickets is not None and tickets >= elevated:
        warnings.append("ELEVATED_TICKET_BACKLOG")
    if not a["identity_valid"]:
        rule, channel, reason = "R2", "HOLD_REVIEW", "IDENTITY_OR_HIERARCHY_CONFLICT"
    elif partner == "UNKNOWN":
        rule, channel, reason = "R3", "HOLD_REVIEW", "PARTNER_OWNERSHIP_UNRESOLVED"
    elif health == "Red" or (tickets is not None and tickets >= critical):
        rule, channel, reason = "R4", "HOLD_REVIEW", "SERVICE_RECOVERY_REQUIRED"
    elif partner == "YES":
        rule, channel, reason = "R5", "PARTNER_LED_CANDIDATE", "SOURCE_PARTNER_MANAGED"
    elif usage is not None and usage >= policy["enterprise_scale_proxy"]["minimum_gb"]:
        rule, channel, reason = "R6", "DIRECT_ENTERPRISE_CANDIDATE", "USAGE_SCALE_PROXY"
    elif usage is not None:
        rule, channel, reason = "R7", "DIGITAL_NURTURE_CANDIDATE", "KNOWN_NONPARTNER_LOWER_SCALE"
    else:
        rule, channel, reason = "R8", "HOLD_REVIEW", "SCALE_EVIDENCE_UNRESOLVED"
    low = policy["priority"]["low_upper_npv_usd"]
    medium = policy["priority"]["medium_upper_npv_usd"]
    priority = "LOW" if npv <= low else "MEDIUM" if npv <= medium else "HIGH"
    if partner == "UNKNOWN" or not a["identity_valid"] or service == "CRITICAL_BACKLOG":
        evidence = "CRITICAL_UNRESOLVED"
    elif (
        health == "UNKNOWN" or tickets is None or usage is None or a["has_manual_review_exceptions"]
    ):
        evidence = "MATERIAL_REVIEW"
    else:
        evidence = "RELATIVELY_COMPLETE"
    return {
        "planning_disposition": channel,
        "primary_rule_id": rule,
        "primary_reason_code": reason,
        "additional_reason_codes": "|".join(sorted(set(warnings))),
        "commercial_priority_tier": priority,
        "evidence_quality_status": evidence,
        "service_barrier_status": service,
        "service_recovery_required": health == "Red" or service == "CRITICAL_BACKLOG",
        "partner_review_required": partner == "UNKNOWN",
        "health_review_required": health in {"Red", "UNKNOWN"},
        "ticket_review_required": tickets is None
        or service in {"ELEVATED_BACKLOG", "CRITICAL_BACKLOG"},
        "fiscal_eligibility_confirmed": False,
        "execution_authorized": False,
        "recommended_action_type": "PLANNING_ONLY",
        "policy_version": policy["version"],
        "assumed_dormancy_persistence_12m": 1 - float(a["expected_reactivation_probability"]),
        "dormancy_proxy_label": policy["dormancy_proxy_label"],
        "ticket_velocity_observed": False,
    }
