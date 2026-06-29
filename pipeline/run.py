"""Pipeline orchestrator. Generate -> Verify+gate -> Clean-up -> Optimize -> validate -> write.

The only channel between layers is the record dict (mirrored to disk at the end). Run with
--dry-run for a $0 full exercise, or --only-slug to run all four layers against one existing
threat (a cheap real smoke test).
"""

from __future__ import annotations

import argparse

from . import changelog, client, frontend, models, schema, store
from .layers import cleanup, generate, optimize, verify


def merge_proposals(records: dict[str, dict], proposals: list[dict]) -> list[dict]:
    """Decide create-vs-update by slug. Existing records keep their identity and provenance;
    a proposal for an existing slug refreshes its description/assessment/claims."""
    by_slug = dict(records)
    order = list(records.keys())
    for p in proposals:
        slug = p["id"]
        if slug in by_slug:
            existing = by_slug[slug]
            for field in ("name", "category", "description", "assessment", "claims"):
                if field in p:
                    existing[field] = p[field]
        else:
            by_slug[slug] = p
            order.append(slug)
    return [by_slug[s] for s in order]


def _assert_generate_unsourced(proposals: list[dict]) -> None:
    """Guard: Generate may never introduce a source_url (only Verify can)."""
    for p in proposals:
        for c in p.get("claims", []):
            assert not c.get("source_url"), f"Generate emitted a source_url for {p['id']}"


def run(dry_run: bool = False, only_slug: str | None = None) -> dict:
    run_id = models.new_run_id()
    client_obj = client.build_client(dry_run=dry_run)
    records = store.load_all()
    index = models.index_of(list(records.values()))

    if only_slug:
        if only_slug not in records:
            raise SystemExit(f"--only-slug: unknown slug {only_slug!r}")
        merged = [records[only_slug]]
    else:
        proposals = generate.run(index, client_obj=client_obj, run_id=run_id)
        _assert_generate_unsourced(proposals)
        merged = merge_proposals(records, proposals)

    published: list[dict] = []
    quarantined: list[dict] = []
    for rec in merged:
        v = verify.run(rec, client_obj=client_obj, run_id=run_id)
        (quarantined if v["verification"]["status"] == "quarantined" else published).append(v)

    cleaned = [cleanup.run(r, index, client_obj=client_obj, run_id=run_id) for r in published]
    optimized = optimize.run(cleaned, client_obj=client_obj, run_id=run_id)

    for rec in optimized + quarantined:
        schema.validate(rec)  # hard gate

    summary = {
        "run_id": run_id,
        "dry_run": dry_run,
        "only_slug": only_slug,
        "published": sorted(r["id"] for r in optimized),
        "quarantined": sorted(r["id"] for r in quarantined),
    }

    if dry_run:
        _print_summary(summary, wrote=False)
        return summary

    store.write_all(optimized)
    store.write_quarantine(quarantined)
    frontend.build()
    changelog.regenerate()
    _print_summary(summary, wrote=True)
    return summary


def _print_summary(summary: dict, *, wrote: bool) -> None:
    mode = "DRY RUN (no writes)" if summary["dry_run"] else ("wrote files" if wrote else "")
    print(f"pipeline run {summary['run_id']} — {mode}")
    print(f"  published   ({len(summary['published'])}): {', '.join(summary['published']) or '-'}")
    print(f"  quarantined ({len(summary['quarantined'])}): {', '.join(summary['quarantined']) or '-'}")


def main() -> None:
    ap = argparse.ArgumentParser(prog="pipeline", description="Run the threat-tracker pipeline.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Exercise the full pipeline with no API calls and no writes.")
    ap.add_argument("--only-slug", metavar="SLUG",
                    help="Run all four layers against a single existing threat (cheap real run).")
    args = ap.parse_args()
    run(dry_run=args.dry_run, only_slug=args.only_slug)


if __name__ == "__main__":
    main()
