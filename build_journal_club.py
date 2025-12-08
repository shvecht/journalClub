import json
from pathlib import Path
import csv
from datetime import datetime
import re

ROOT = Path(__file__).parent

def load_ent_index():
    """Index all ent_all_results.json files by PMID."""
    index = {}
    for year_dir in ROOT.glob("20[0-9][0-9]"):
        if not year_dir.is_dir():
            continue
        for month_dir in year_dir.glob("[01][0-9]"):
            jf = month_dir / "ent_all_results.json"
            if jf.is_file():
                articles = json.loads(jf.read_text(encoding="utf-8"))
                for a in articles:
                    pmid = str(a.get("PMID", "")).strip()
                    if pmid:
                        index[pmid] = a
    return index

def load_sessions():
    """Load curated JC sessions from sessions.csv."""
    sessions_file = ROOT / "sessions.csv"
    sessions = []
    with sessions_file.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sessions.append(row)
    return sessions


def parse_subjects(subjects_field):
    """Parse a comma-separated subjects string into a clean list."""
    if not subjects_field:
        return []
    return [part.strip() for part in subjects_field.split(";") for part in part.split(",") if part.strip()]

def normalize_date(date_str_from_session, date_str_from_pub):
    date_str = (date_str_from_session or date_str_from_pub or "").strip()
    if not date_str:
        return ""
    try:
        # ent format: 2025-Oct-31
        if len(date_str) == 11 and date_str[4] == "-" and date_str[8] == "-":
            dt = datetime.strptime(date_str, "%Y-%b-%d")
        # month-only: 2025-Oct
        elif re.fullmatch(r"\d{4}-[A-Za-z]{3}", date_str):
            dt = datetime.strptime(f"{date_str}-01", "%Y-%b-%d")
        # month-only numeric: 2025-10
        elif re.fullmatch(r"\d{4}-\d{2}", date_str):
            dt = datetime.strptime(f"{date_str}-01", "%Y-%m-%d")
        else:
            dt = datetime.fromisoformat(date_str)
        return dt.date().isoformat()
    except Exception:
        return date_str  # worst case, just pass through

def main():
    ent_index = load_ent_index()
    sessions = load_sessions()
    out = []

    for s in sessions:
        pmid = str(s.get("pmid", "")).strip()
        art = ent_index.get(pmid)
        if not art:
            print(f"WARNING: PMID {pmid} from sessions.csv not found in any ent_all_results.json")
            continue

        date_iso = normalize_date(s.get("date"), art.get("Publication_Date"))

        # Allow curated CSV fields to override extracted metadata when present
        s_title = (s.get("title") or "").strip()
        s_journal = (s.get("journal") or "").strip()
        s_authors = (s.get("authors") or "").strip()
        s_abstract = (s.get("abstract") or "").strip()
        subjects = parse_subjects(s.get("subjects"))

        title = s_title or (art.get("Title", "") or "").strip()
        journal = s_journal or (art.get("Journal", "") or "").strip()
        authors = s_authors or (art.get("Authors", "") or "").strip()
        abstract = s_abstract or (art.get("Abstract", "") or "").strip()
        doi = (art.get("DOI", "") or "").strip()

        out.append(
            {
                "date": date_iso,
                "presenter": s.get("presenter", "").strip(),
                "title": title,
                "journal": journal,
                "authors": authors,
                "abstract": abstract,
                "doi": doi,
                "pmid": pmid,
                "pdf": (s.get("pdf", "") or f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/").strip(),
                "notes": s.get("notes", "").strip(),
                "subjects": subjects,
            }
        )

    # newest first
    out.sort(key=lambda r: r["date"], reverse=True)

    data_dir = ROOT / "data"
    data_dir.mkdir(exist_ok=True)
    out_file = data_dir / "journal_club.json"
    out_file.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(out)} sessions to {out_file}")

if __name__ == "__main__":
    main()
