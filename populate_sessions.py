from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path

from tag_subjects import assign_subjects


CANONICAL_COLUMNS = [
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
    "subjects",
    "highlight",
    "analysis",
    "images",
    "summary_month",
    "summary_headline",
    "summary_paragraph",
    "summary_highlights",
]


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


def load_existing_sessions(
    sessions_path: Path,
) -> tuple[list[str], dict[str, dict[str, str]], list[dict[str, str]]]:
    """Load existing sessions.csv, preserving field order and unknown columns."""

    if not sessions_path.is_file():
        return CANONICAL_COLUMNS.copy(), {}, []

    fieldnames: list[str] = []
    manual: dict[str, dict[str, str]] = {}
    orphans: list[dict[str, str]] = []
    with sessions_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = [name for name in (reader.fieldnames or []) if name]
        for row in reader:
            cleaned_row = {
                str(key).strip(): (value or "")
                for key, value in row.items()
                if key
            }
            pmid = str(cleaned_row.get("pmid", "")).strip()
            if pmid:
                manual[pmid] = cleaned_row
            elif any(str(value).strip() for value in cleaned_row.values()):
                orphans.append(cleaned_row)

    if not fieldnames:
        fieldnames = CANONICAL_COLUMNS.copy()

    return fieldnames, manual, orphans


def merge_fieldnames(existing_fieldnames: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for field in [*existing_fieldnames, *CANONICAL_COLUMNS]:
        if field and field not in seen:
            merged.append(field)
            seen.add(field)
    return merged


def first_nonempty(*values: object) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def normalize_date(date_str: str) -> str:
    """Normalize publication or curated dates to ISO format when possible."""

    date_str = (date_str or "").strip()
    if not date_str:
        return ""

    known_formats = (
        "%Y-%b-%d",
        "%Y-%b",
        "%Y-%m-%d",
        "%Y-%m",
    )
    for fmt in known_formats:
        try:
            return datetime.strptime(date_str, fmt).date().isoformat()
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(date_str).date().isoformat()
    except ValueError:
        pass

    month_match = re.fullmatch(r"(\d{4})-([A-Za-z]{3})", date_str)
    if month_match:
        try:
            return datetime.strptime(date_str, "%Y-%b").date().isoformat()
        except ValueError:
            return date_str

    return date_str


def infer_subjects(title: str, journal: str, abstract: str, notes: str) -> str:
    text = " ".join(part for part in [title, journal, abstract, notes] if part)
    if not text.strip():
        return ""
    return "; ".join(assign_subjects(text))


def build_session_row(
    pmid: str,
    art: dict | None,
    manual: dict[str, str] | None,
    fieldnames: list[str],
) -> dict[str, str]:
    art = art or {}
    manual = manual or {}

    row = {field: manual.get(field, "") for field in fieldnames}

    publication_date = art.get("Publication_Date", art.get("PublicationDate", ""))
    title = first_nonempty(manual.get("title"), art.get("Title"))
    journal = first_nonempty(manual.get("journal"), art.get("Journal"))
    authors = first_nonempty(manual.get("authors"), art.get("Authors"))
    doi = first_nonempty(manual.get("doi"), art.get("DOI"))
    abstract = first_nonempty(manual.get("abstract"), art.get("Abstract"))
    notes = first_nonempty(manual.get("notes"))

    row["date"] = normalize_date(first_nonempty(manual.get("date"), publication_date))
    row["presenter"] = first_nonempty(manual.get("presenter"))
    row["pmid"] = pmid
    row["title"] = title
    row["journal"] = journal
    row["authors"] = authors
    row["doi"] = doi
    row["abstract"] = abstract
    row["notes"] = notes
    row["pdf"] = first_nonempty(
        manual.get("pdf"),
        f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
    )
    row["subjects"] = first_nonempty(
        manual.get("subjects"),
        infer_subjects(title, journal, abstract, notes),
    )
    row["highlight"] = first_nonempty(manual.get("highlight"))
    row["analysis"] = first_nonempty(manual.get("analysis"))
    row["images"] = first_nonempty(manual.get("images"))
    row["summary_month"] = first_nonempty(manual.get("summary_month"))
    row["summary_headline"] = first_nonempty(manual.get("summary_headline"))
    row["summary_paragraph"] = first_nonempty(manual.get("summary_paragraph"))
    row["summary_highlights"] = first_nonempty(manual.get("summary_highlights"))

    return row


def main():
    repo_root = Path(__file__).parent
    ent_index = load_ent_index(repo_root)
    sessions_path = repo_root / "sessions.csv"
    existing_fieldnames, manual_sessions, orphan_rows = load_existing_sessions(
        sessions_path
    )
    output_fieldnames = merge_fieldnames(existing_fieldnames)

    all_pmids = set(ent_index) | set(manual_sessions)
    rows: list[dict[str, str]] = []
    for pmid in all_pmids:
        art = ent_index.get(pmid)
        manual = manual_sessions.get(pmid)
        rows.append(build_session_row(pmid, art, manual, output_fieldnames))

    for orphan in orphan_rows:
        row = {field: orphan.get(field, "") for field in output_fieldnames}
        row["date"] = normalize_date(orphan.get("date", ""))
        rows.append(row)

    # Sort newest first by normalized date string
    rows.sort(key=lambda row: row.get("date", ""), reverse=True)

    with sessions_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=output_fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(
        f"Wrote {len(rows)} rows to {sessions_path} using ent_all_results.json files across the repo"
    )


if __name__ == "__main__":
    main()
