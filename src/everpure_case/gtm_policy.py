"""Versioned, constrained Phase 4 routing policy."""

import hashlib
import json
from pathlib import Path

# Pin the exact v2 disclosure text while keeping its human-readable copy in the JSON policy.
REQUIRED_DISCLOSURES_SHA256 = "5d5757787645f5cfba44cb644e88ce8aae044fa5a84087871601da3a91dfd320"


def canonical_hash(value: dict) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_policy(root: str | Path) -> dict:
    path = Path(root) / "docs/PHASE_4_ROUTING_POLICY.json"
    policy = json.loads(path.read_text(encoding="utf-8"))
    if (
        policy.get("version") != "phase4-routing-policy-v2"
        or policy.get("rule_order") != [f"R{i}" for i in range(9)]
        or policy.get("reference_scenario") != "base"
        or policy.get("reference_discount_tier") != "medium_15pct"
        or policy.get("enterprise_scale_proxy", {}).get("minimum_gb") != 37656
        or policy.get("service_backlog", {}).get("critical_from_valid_tickets") != 5
        or policy.get("service_backlog", {}).get("elevated_from_valid_tickets") != 3
        or policy.get("priority", {}).get("low_upper_npv_usd") != 161.51698172008832
        or policy.get("priority", {}).get("medium_upper_npv_usd") != 200.26496145151106
        or policy.get("priority", {}).get("low_upper_npv_usd", 0)
        >= policy.get("priority", {}).get("medium_upper_npv_usd", 0)
        or policy.get("execution_authorized") is not False
        or policy.get("recommended_action_type") != "PLANNING_ONLY"
        or policy.get("ticket_velocity_observed") is not False
        or policy.get("revenue_decay_observed") is not False
        or canonical_hash(policy.get("required_executive_disclosures", {}))
        != REQUIRED_DISCLOSURES_SHA256
    ):
        raise ValueError("Unsupported or unsafe Phase 4 policy")
    return policy
