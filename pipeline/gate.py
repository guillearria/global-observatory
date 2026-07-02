"""The deterministic quarantine gate — the trust core, as a standalone module.

Pure Python, imports only `config`. It decides what publishes; the drafter's (or a model's)
say-so is never trusted over the domain check.
"""

from __future__ import annotations

from . import config


def _gate_notes(status, verified, disputed, unverified) -> str:
    return (
        f"gate: {len(verified)} verified, {len(disputed)} disputed, {len(unverified)} unverified "
        f"-> {status}"
    )


def apply_gate(record: dict) -> dict:
    """Re-check every claim against the source allowlist and set verification status.

    A claim marked verified but citing a non-allowlisted domain is downgraded to unverified — the
    model's say-so is never trusted over the deterministic domain check. A record publishes only
    with >=1 verified claim and 0 disputed claims; otherwise it is quarantined.
    """
    claims = record.get("claims", [])
    for c in claims:
        if c.get("verification_status") == "verified":
            ok, label = config.allowlisted(c.get("source_url") or "")
            if not ok:
                c["verification_status"] = "unverified"
            elif label:
                c["source_name"] = label

    verified = [c for c in claims if c.get("verification_status") == "verified"]
    disputed = [c for c in claims if c.get("verification_status") == "disputed"]
    unverified = [c for c in claims if c.get("verification_status") == "unverified"]

    if disputed or not verified:
        status, confidence = "quarantined", "low"
    elif unverified:
        status, confidence = "partial", "medium"
    else:
        status, confidence = "verified", "high"

    record["verification"] = {
        "status": status,
        "confidence": confidence,
        "notes": _gate_notes(status, verified, disputed, unverified),
    }
    return record
