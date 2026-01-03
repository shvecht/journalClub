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


def parse_bool(val):
    if isinstance(val, bool):
        return val
    if val is None:
        return False
    return str(val).strip().lower() in {"1", "true", "yes", "y", "highlight", "t"}


def parse_images(field):
    images = []
    if not field:
        return images

    def normalise_image(img):
        if isinstance(img, str):
            url = img.strip()
            if url:
                return {"url": url, "caption": ""}
            return None
        if isinstance(img, dict):
            url = str(img.get("url") or img.get("src") or "").strip()
            caption = str(img.get("caption") or img.get("alt") or "").strip()
            if url:
                return {"url": url, "caption": caption}
        return None

    raw_list = None
    if isinstance(field, list):
        raw_list = field
    else:
        text = str(field).strip()
        if not text:
            return images
        try:
            parsed = json.loads(text)
            raw_list = parsed if isinstance(parsed, list) else [parsed]
        except Exception:
            entries = [part.strip() for part in re.split(r"[;\n]+", text) if part.strip()]
            raw_list = []
            for entry in entries:
                if "|" in entry:
                    url, caption = entry.split("|", 1)
                elif "," in entry:
                    url, caption = entry.split(",", 1)
                else:
                    url, caption = entry, ""
                raw_list.append({"url": url.strip(), "caption": caption.strip()})

    for img in raw_list or []:
        normalised = normalise_image(img)
        if normalised:
            images.append(normalised)

    return images


def parse_subjects(subjects_field):
    """Parse a comma-separated subjects string into a clean list."""
    if not subjects_field:
        return []
    return [part.strip() for part in subjects_field.split(";") for part in part.split(",") if part.strip()]


def parse_highlights(highlights_field):
    """Parse a highlights string or list into a clean list."""
    if not highlights_field:
        return []

    if isinstance(highlights_field, list):
        raw_items = highlights_field
    else:
        text = str(highlights_field).strip()
        if not text:
            return []
        raw_items = re.split(r"[;\n]+", text)

    return [item.strip() for item in raw_items if str(item).strip()]


def normalize_month(month_field, date_iso=""):
    """Return a YYYY-MM string derived from a month field or a full date."""
    raw_month = (month_field or "").strip()
    if not raw_month and date_iso:
        return date_iso[:7]

    try:
        if re.fullmatch(r"\d{4}-[A-Za-z]{3}", raw_month):
            dt = datetime.strptime(f"{raw_month}-01", "%Y-%b-%d")
        elif re.fullmatch(r"\d{4}-\d{2}", raw_month):
            dt = datetime.strptime(f"{raw_month}-01", "%Y-%m-%d")
        else:
            dt = datetime.fromisoformat(raw_month)
        return dt.strftime("%Y-%m")
    except Exception:
        if raw_month:
            return raw_month[:7]
        return ""

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
    monthly_summaries = {}

    for s in sessions:
        pmid = str(s.get("pmid", "")).strip()
        art = ent_index.get(pmid)
        if not art:
            print(f"WARNING: PMID {pmid} from sessions.csv not found in any ent_all_results.json")
            continue

        pub_date = art.get("Publication_Date") or art.get("PublicationDate")
        date_iso = normalize_date(s.get("date"), pub_date)

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
        highlight = parse_bool(s.get("highlight"))
        analysis = (s.get("analysis") or "").strip()
        images = parse_images(s.get("images"))

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
                "highlight": highlight,
                "analysis": analysis,
                "images": images,
            }
        )

        summary_month = normalize_month(s.get("summary_month"), date_iso)
        summary_headline = (s.get("summary_headline") or "").strip()
        summary_paragraph = (s.get("summary_paragraph") or "").strip()
        summary_highlights = parse_highlights(s.get("summary_highlights"))

        if summary_month and (
            summary_headline or summary_paragraph or summary_highlights
        ):
            monthly_summaries.setdefault(
                summary_month,
                {
                    "month": summary_month,
                    "headline": summary_headline,
                    "paragraph": summary_paragraph,
                    "key_highlights": summary_highlights,
                },
            )

    # newest first
    out.sort(key=lambda r: r["date"], reverse=True)

    data_dir = ROOT / "data"
    data_dir.mkdir(exist_ok=True)
    out_file = data_dir / "journal_club.json"
    payload = {
        "sessions": out,
        "monthly_summaries": [
            monthly_summaries[m]
            for m in sorted(monthly_summaries.keys(), reverse=True)
        ],
    }
    out_file.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(
        f"Wrote {len(out)} sessions and {len(payload['monthly_summaries'])} summaries to {out_file}"
    )

if __name__ == "__main__":
    main()
