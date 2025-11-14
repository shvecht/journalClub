import json
import csv
from pathlib import Path
from datetime import datetime

def find_latest_ent_file(root: Path) -> Path | None:
    """Find the most recent YYYY/MM/ent_all_results.json in the repo."""
    latest_path = None
    latest_date = None

    for year_dir in root.glob("20[0-9][0-9]"):
        if not year_dir.is_dir():
            continue
        for month_dir in year_dir.iterdir():
            ent_file = month_dir / "ent_all_results.json"
            if ent_file.is_file():
                # Parse year/month into a date for comparison
                try:
                    dt = datetime.strptime(f"{year_dir.name}-{month_dir.name}", "%Y-%Y-%m")
                except Exception:
                    continue
                if latest_date is None or dt > latest_date:
                    latest_date = dt
                    latest_path = ent_file
    return latest_path

def main():
    repo_root = Path(__file__).parent
    ent_file = find_latest_ent_file(repo_root)
    if not ent_file:
        raise SystemExit("No ent_all_results.json files found")

    with ent_file.open(encoding="utf-8") as f:
        articles = json.load(f)

    # Write sessions.csv in repo root
    sessions_path = repo_root / "sessions.csv"
    with sessions_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "presenter", "pmid", "notes", "pdf"])
        for art in articles:
            pub_date = art.get("Publication_Date", "")
            try:
                dt = datetime.strptime(pub_date, "%Y-%b-%d")
                iso_date = dt.strftime("%Y-%m-%d")
            except Exception:
                iso_date = pub_date
            writer.writerow([iso_date, "", art.get("PMID", ""), "", ""])

    print(f"Wrote {len(articles)} rows to {sessions_path} from {ent_file}")

if __name__ == "__main__":
    main()
