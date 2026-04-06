# Manual ENT harvest backfill

When a scheduled run misses a month, you can re-ingest that window manually with a GitHub Actions dispatch and a local rebuild.

## 1. Dispatch the harvest workflow for the missed month
1. Navigate to **Actions → ENT harvest (stage 1–2)**.
2. Choose **Run workflow** and populate one of the date inputs:
   - **target_month**: `YYYY-MM` (e.g., `2024-10`), or
   - **year** and **month**: numeric year and month (e.g., `2024` and `10`).
3. Trigger the run; the workflow passes these inputs to `articlesRetrieval.ipynb`, which reruns the harvest for that calendar month instead of the rolling lookback window.

## 2. Rebuild derived artifacts after harvest completes
Once the workflow finishes (and the results are committed or available on its artifact/branch):
1. Update your local checkout to include the new harvest outputs.
2. Regenerate downstream data and pages:
   ```bash
   python populate_sessions.py
   python build_journal_club.py
   ```
3. Commit and push any regenerated files or open a pull request as usual.

This flow ensures that missed months are ingested and downstream views stay in sync with the corrected harvest.

## 3. Backfill monthly summaries and standout papers
If a month has been harvested but still lacks curation:

1. Ensure `OPENAI_API_KEY` is available in your shell.
2. Run the curation backfill script for one or more months:
   ```bash
   python3 backfill_monthly_curation.py --months 2026-01 2026-02
   ```
3. Rebuild the site payload:
   ```bash
   python3 build_journal_club.py
   ```

By default the script only fills months that do not already have summaries or highlight flags. Use `--overwrite-summaries` and/or `--overwrite-highlights` if you want to regenerate existing curation.
