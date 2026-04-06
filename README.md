# Journal Club

Static site and data pipeline for the HYMC / Technion journal club.

## Local Preview

Serve the site locally with a rebuild first:

```bash
python3 serve_local.py
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

Useful options:

```bash
# Rebuild once, serve, and keep watching for source/data changes
python3 serve_local.py --watch

# Serve on a different port and open the browser automatically
python3 serve_local.py --port 4173 --open-browser

# Skip the initial rebuild if you only changed static files
python3 serve_local.py --skip-build
```

`--watch` reruns:

```bash
python3 populate_sessions.py
python3 build_journal_club.py
```

when tracked source files change.

## Manual Rebuild

If you only want to regenerate derived data:

```bash
python3 populate_sessions.py
python3 build_journal_club.py
```

## Monthly Curation Backfill

To populate missing monthly summaries and standout papers:

```bash
python3 backfill_monthly_curation.py --months 2026-01 2026-02
python3 build_journal_club.py
```

This requires `OPENAI_API_KEY` in the environment.
