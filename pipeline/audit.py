"""Independent re-derivation of every computed trust field on a stored record.

The write-time pipeline (`curate.finalize`) computes claim statuses, the verification
verdict, and sort keys exactly once, at authoring time. This module re-derives all of
them from nothing but the record's own claims and the domain allowlist, so a second,
independent layer (`scripts/validate_data.py`, run by CI on every PR and push to main)
can confirm the stored verdicts. A record whose trust fields were edited after the gate
ran — a swapped source URL, an upgraded verification status, inflated sort keys, or a
quarantined record dropped into a published directory — fails loudly instead of shipping.

Imports only the same pure machinery the gate itself uses; no disk, no network, no API.
"""

from __future__ import annotations

import copy

from .curate import compute_sort_keys
from .gate import apply_gate


def audit_record(record: dict, kind: str = "threat", *, quarantined: bool = False) -> list[str]:
    """Return every trust-consistency problem on a stored record (empty list = clean).

    `quarantined` says which directory the record was loaded from, so placement can be
    checked against the verdict the gate would actually reach.
    """
    msgs: list[str] = []

    regated = apply_gate(copy.deepcopy(record))
    for stored, derived in zip(record.get("claims", []), regated["claims"]):
        if stored.get("verification_status") != derived.get("verification_status"):
            msgs.append(
                f"claims[{stored.get('id')}].verification_status: stored "
                f"{stored.get('verification_status')!r} but the allowlist derives "
                f"{derived.get('verification_status')!r}"
            )
    if record.get("verification") != regated["verification"]:
        msgs.append(
            f"verification: stored {record.get('verification')!r} does not match an "
            f"independent gate re-run {regated['verification']!r}"
        )

    derived_keys = compute_sort_keys(record, kind)
    if record.get("sort_keys") != derived_keys:
        msgs.append(f"sort_keys: stored {record.get('sort_keys')!r} but derived {derived_keys!r}")

    status = (record.get("verification") or {}).get("status")
    if quarantined and status != "quarantined":
        msgs.append(f"placement: {status!r} record sits in a quarantine directory")
    if not quarantined and status == "quarantined":
        msgs.append("placement: quarantined record sits in a published directory")

    return msgs
