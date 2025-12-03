import csv
import json
from datetime import datetime
from pathlib import Path


def load_ent_index(root: Path) -> dict[str, dict]:
    """Index all ent_all_results.json files by PMID."""

    index: dict[str, dict] = {}
    for year_dir in root.glob("20[0-9][0-9]"):
        if not year_dir.is_dir():
            continue
        for month_dir in year_dir.glob("[01][0-9]"):
            jf = month_dir / "ent_all_results.json"
            if jf.is_file():
                articles = json.loads(jf.read_text(encoding="utf-8"))
                for art in articles:
                    pmid = str(art.get("PMID", "")).strip()
                    if pmid and pmid not in index:
                        index[pmid] = art
    return index


def load_manual_sessions(sessions_path: Path) -> dict[str, dict]:
    """Load existing sessions.csv and index by PMID."""

    if not sessions_path.is_file():
        return {}

    manual: dict[str, dict] = {}
    with sessions_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pmid = str(row.get("pmid", "")).strip()
            if pmid:
                manual[pmid] = row
    return manual


def normalize_date(date_str: str) -> str:
    """Normalize publication or curated dates to ISO format when possible."""

    date_str = (date_str or "").strip()
    if not date_str:
        return ""
    try:
        dt = datetime.strptime(date_str, "%Y-%b-%d")
    except Exception:
        try:
            dt = datetime.fromisoformat(date_str)
        except Exception:
            return date_str
    return dt.date().isoformat()


def build_session_row(pmid: str, art: dict | None, manual: dict | None) -> list:
    art = art or {}
    manual = manual or {}

    date_str = manual.get("date") or art.get("Publication_Date", "")
    title = manual.get("title") or art.get("Title", "")
    journal = manual.get("journal") or art.get("Journal", "")
    authors = manual.get("authors") or art.get("Authors", "")
    doi = manual.get("doi") or art.get("DOI", "")
    abstract = manual.get("abstract") or art.get("Abstract", "")
    pdf = manual.get("pdf", "") or (f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "")

    return [
        normalize_date(date_str),
        manual.get("presenter", ""),
        pmid,
        title,
        journal,
        authors,
        doi,
        abstract,
        manual.get("notes", ""),
        pdf,
    ]


def main():
    repo_root = Path(__file__).parent
    ent_index = load_ent_index(repo_root)
    sessions_path = repo_root / "sessions.csv"
    manual_sessions = load_manual_sessions(sessions_path)

    all_pmids = set(ent_index) | set(manual_sessions)
    rows = []
    for pmid in all_pmids:
        art = ent_index.get(pmid)
        manual = manual_sessions.get(pmid)
        rows.append(build_session_row(pmid, art, manual))

    # Sort newest first by normalized date string
    rows.sort(key=lambda r: r[0], reverse=True)

    with sessions_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "date",
                "presenter",
                "pmid",
                "title",
                "journal",
                "authors",
                "doi",
                "abstract",
                "notes",
                "pdf",
            ]
        )
        writer.writerows(rows)

    print(
        f"Wrote {len(rows)} unique PMIDs to {sessions_path} using ent_all_results.json files across the repo"
    )


if __name__ == "__main__":
    main()
