"""end-times-tracker pipeline.

Four independent, context-free model layers (Generate -> Verify -> Clean-up -> Optimize)
plus the Python guards and deterministic file store that make "git history is the changelog"
hold. See docs/ARCHITECTURE.md.
"""
