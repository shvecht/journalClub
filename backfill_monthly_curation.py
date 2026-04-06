from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from openai import OpenAI


ROOT = Path(__file__).parent
SEPARATOR = "; "
TRUE_VALUES = {"1", "true", "yes", "y", "highlight", "t"}

MODEL_CANDIDATES = [
    "gpt-5-mini",
    "gpt-4.1-mini",
    "gpt-4o-mini",
]

JOURNAL_WEIGHTS = {
    "new england journal of medicine": 10,
    "nejm": 10,
    "the lancet": 9,
    "jama": 8,
    "bmj": 7,
    "journal of clinical oncology": 7,
    "annals of oncology": 6,
    "nature medicine": 7,
    "the laryngoscope": 5,
    "international forum of allergy & rhinology": 5,
    "otolaryngology--head and neck surgery": 5,
    "otolaryngology-head and neck surgery": 5,
    "head & neck": 5,
    "head and neck": 5,
    "sleep": 5,
    "sleep medicine": 4,
    "chest": 5,
    "thyroid": 4,
    "oral oncology": 5,
    "auris, nasus, larynx": 3,
}

POSITIVE_PATTERNS = {
    r"\brandomi[sz]ed\b": 6,
    r"\bmeta-analysis\b": 6,
    r"\bsystematic review\b": 5,
    r"\bclinical trial\b": 5,
    r"\bphase (ii|iii|iv)\b": 4,
    r"\bprospective\b": 3,
    r"\bmulticent(?:er|re)\b": 3,
    r"\bnational\b": 2,
    r"\bregistry\b": 2,
    r"\bpopulation-based\b": 3,
    r"\bcohort\b": 2,
    r"\bdatabase\b": 2,
    r"\bguideline\b": 5,
    r"\bconsensus\b": 4,
    r"\bquality of life\b": 2,
    r"\bcost-utility\b": 2,
    r"\bcost-effectiveness\b": 2,
    r"\bmachine learning\b": 1,
    r"\bartificial intelligence\b": 1,
}

NEGATIVE_PATTERNS = {
    r"^correction\b": -30,
    r"^error in\b": -30,
    r"^title of article updated\b": -30,
    r"\breply\b": -10,
    r"\bcomment\b": -8,
    r"\bletter\b": -8,
    r"\berratum\b": -30,
    r"\bcorrigendum\b": -30,
    r"\bretraction\b": -40,
    r"\bcase report\b": -5,
    r"\bcase series\b": -3,
    r"\btechnical note\b": -3,
    r"\bprotocol\b": -4,
}

SYSTEM_PROMPT = """You are curating a monthly academic journal club in otolaryngology, sleep medicine, rhinology, laryngology, head and neck oncology, otology, and related perioperative topics.

Choose the papers most worth discussing in a faculty-level journal club. Prioritize:
- stronger study design or unusually important expert guidance
- likely clinical impact, practice change, or decision relevance
- novelty or broad signal value for the field
- a useful spread across subspecialties when possible

Avoid selecting corrections, replies, letters, and minor case reports unless the signal is exceptionally important.

Return valid JSON only with this exact shape:
{
  "headline": "short headline",
  "paragraph": "2-4 sentence monthly synthesis",
  "key_highlights": ["bullet", "..."],
  "highlight_pmids": ["pmid1", "..."],
  "rationales": [{"pmid": "pmid", "reason": "short reason"}]
}

Requirements:
- "headline" should be concise and specific to the month.
- "paragraph" should summarize the month's themes and why the selected papers matter.
- "key_highlights" should contain 4 to 6 short bullets.
- "highlight_pmids" must contain exactly the requested number of PMIDs, all drawn from the candidate list.
- "rationales" should include one short reason for each selected PMID.
"""


@dataclass
class ScoredRow:
    row: dict[str, str]
    score: int
    abstract_snippet: str
    subjects: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill monthly journal club summaries and highlighted papers."
    )
    parser.add_argument(
        "--months",
        nargs="*",
        help="Specific months to curate in YYYY-MM format. Defaults to all months in sessions.csv.",
    )
    parser.add_argument(
        "--model",
        help="Preferred OpenAI model. Falls back to a small model list if omitted.",
    )
    parser.add_argument(
        "--candidate-limit",
        type=int,
        default=36,
        help="How many candidate papers to send to the model per month.",
    )
    parser.add_argument(
        "--highlights-per-month",
        type=int,
        default=10,
        help="How many standout papers to mark for each month.",
    )
    parser.add_argument(
        "--overwrite-summaries",
        action="store_true",
        help="Replace existing monthly summary fields instead of only filling missing ones.",
    )
    parser.add_argument(
        "--overwrite-highlights",
        action="store_true",
        help="Replace existing highlight flags instead of only filling missing months.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print proposed curation without writing sessions.csv.",
    )
    return parser.parse_args()


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_rows(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def normalize_month(date_str: str) -> str:
    return (date_str or "").strip()[:7]


def parse_subjects(text: str) -> list[str]:
    if not text:
        return []
    return [
        part.strip()
        for part in text.replace(";", ",").split(",")
        if part.strip()
    ]


def parse_bool(text: str) -> bool:
    return str(text or "").strip().lower() in TRUE_VALUES


def clean_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def trim_abstract(text: str, limit: int = 700) -> str:
    text = clean_whitespace(text)
    if len(text) <= limit:
        return text
    clipped = text[: limit - 1].rsplit(" ", 1)[0].strip()
    return f"{clipped}…"


def score_row(row: dict[str, str]) -> ScoredRow:
    title = clean_whitespace(row.get("title", ""))
    journal = clean_whitespace(row.get("journal", ""))
    abstract = clean_whitespace(row.get("abstract", ""))
    subjects = parse_subjects(row.get("subjects", ""))
    text = f"{title}\n{abstract}".lower()
    score = 0

    journal_lower = journal.lower()
    for needle, weight in JOURNAL_WEIGHTS.items():
        if needle in journal_lower:
            score += weight

    for pattern, weight in POSITIVE_PATTERNS.items():
        if re.search(pattern, text):
            score += weight

    for pattern, weight in NEGATIVE_PATTERNS.items():
        if re.search(pattern, title.lower()) or re.search(pattern, text):
            score += weight

    abstract_len = len(abstract)
    if abstract_len >= 450:
        score += 1
    if abstract_len >= 900:
        score += 1

    if subjects:
        score += min(len(subjects), 3)

    return ScoredRow(
        row=row,
        score=score,
        abstract_snippet=trim_abstract(abstract),
        subjects=subjects,
    )


def month_groups(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    groups: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        month = normalize_month(row.get("date", ""))
        if month:
            groups.setdefault(month, []).append(row)
    return groups


def month_has_summary(rows: list[dict[str, str]]) -> bool:
    return any(
        clean_whitespace(row.get("summary_headline"))
        or clean_whitespace(row.get("summary_paragraph"))
        or clean_whitespace(row.get("summary_highlights"))
        for row in rows
    )


def month_has_highlights(rows: list[dict[str, str]]) -> bool:
    return any(parse_bool(row.get("highlight")) for row in rows)


def build_candidate_pool(
    rows: list[dict[str, str]],
    candidate_limit: int,
) -> list[ScoredRow]:
    scored = [score_row(row) for row in rows]
    scored.sort(
        key=lambda item: (
            item.score,
            len(item.abstract_snippet),
            item.row.get("title", ""),
        ),
        reverse=True,
    )

    by_subject: dict[str, list[ScoredRow]] = {}
    subject_counts = Counter()
    for item in scored:
        for subject in item.subjects:
            subject_counts[subject] += 1
            by_subject.setdefault(subject, []).append(item)

    selected: list[ScoredRow] = []
    seen_pmids: set[str] = set()

    for subject, _count in subject_counts.most_common(8):
        for item in by_subject.get(subject, [])[:3]:
            pmid = clean_whitespace(item.row.get("pmid"))
            if pmid and pmid not in seen_pmids:
                selected.append(item)
                seen_pmids.add(pmid)
            if len(selected) >= candidate_limit:
                return selected

    for item in scored:
        pmid = clean_whitespace(item.row.get("pmid"))
        if pmid and pmid not in seen_pmids:
            selected.append(item)
            seen_pmids.add(pmid)
        if len(selected) >= candidate_limit:
            break

    return selected


def month_prompt(
    month: str,
    candidates: list[ScoredRow],
    requested_highlights: int,
) -> str:
    payload = []
    for item in candidates:
        row = item.row
        payload.append(
            {
                "pmid": clean_whitespace(row.get("pmid")),
                "title": clean_whitespace(row.get("title")),
                "journal": clean_whitespace(row.get("journal")),
                "subjects": item.subjects,
                "score_hint": item.score,
                "abstract": item.abstract_snippet,
            }
        )

    return (
        f"Curate the month {month}.\n"
        f"Select exactly {requested_highlights} standout papers from the candidate list below.\n"
        "Use only the provided PMIDs.\n\n"
        f"Candidates:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def extract_json_object(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def request_curation(
    client: OpenAI,
    month: str,
    candidates: list[ScoredRow],
    requested_highlights: int,
    preferred_model: str | None,
) -> tuple[str, dict]:
    models = [preferred_model] if preferred_model else []
    models.extend(model for model in MODEL_CANDIDATES if model not in models)
    last_error: Exception | None = None

    for model in models:
        try:
            response = client.responses.create(
                model=model,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": month_prompt(
                            month=month,
                            candidates=candidates,
                            requested_highlights=requested_highlights,
                        ),
                    },
                ],
            )
            parsed = extract_json_object(response.output_text)
            return model, parsed
        except Exception as exc:  # pragma: no cover - best effort fallback
            last_error = exc
            time.sleep(1)

    if last_error is None:
        raise RuntimeError("No model candidates available")
    raise last_error


def validate_curation(
    payload: dict,
    candidates: Iterable[ScoredRow],
    requested_highlights: int,
) -> dict:
    allowed_pmids = {
        clean_whitespace(item.row.get("pmid"))
        for item in candidates
        if clean_whitespace(item.row.get("pmid"))
    }
    headline = clean_whitespace(payload.get("headline"))
    paragraph = clean_whitespace(payload.get("paragraph"))
    key_highlights = [
        clean_whitespace(item)
        for item in payload.get("key_highlights", [])
        if clean_whitespace(item)
    ]
    highlight_pmids = [
        clean_whitespace(item)
        for item in payload.get("highlight_pmids", [])
        if clean_whitespace(item)
    ]
    rationales = payload.get("rationales", [])

    deduped_pmids: list[str] = []
    seen = set()
    for pmid in highlight_pmids:
        if pmid in allowed_pmids and pmid not in seen:
            deduped_pmids.append(pmid)
            seen.add(pmid)

    if len(deduped_pmids) != requested_highlights:
        raise ValueError(
            f"Expected {requested_highlights} selected PMIDs, got {len(deduped_pmids)}"
        )
    if not headline or not paragraph:
        raise ValueError("Missing summary headline or paragraph")
    if not (4 <= len(key_highlights) <= 6):
        raise ValueError("Expected 4 to 6 monthly highlight bullets")

    rationale_map: dict[str, str] = {}
    for item in rationales if isinstance(rationales, list) else []:
        if not isinstance(item, dict):
            continue
        pmid = clean_whitespace(item.get("pmid"))
        reason = clean_whitespace(item.get("reason"))
        if pmid in seen and reason:
            rationale_map[pmid] = reason

    return {
        "headline": headline,
        "paragraph": paragraph,
        "key_highlights": key_highlights,
        "highlight_pmids": deduped_pmids,
        "rationales": rationale_map,
    }


def clear_month_summary(rows: list[dict[str, str]]) -> None:
    for row in rows:
        row["summary_month"] = ""
        row["summary_headline"] = ""
        row["summary_paragraph"] = ""
        row["summary_highlights"] = ""


def apply_summary(month: str, rows: list[dict[str, str]], curation: dict) -> None:
    clear_month_summary(rows)
    anchor = rows[0]
    anchor["summary_month"] = month
    anchor["summary_headline"] = curation["headline"]
    anchor["summary_paragraph"] = curation["paragraph"]
    anchor["summary_highlights"] = SEPARATOR.join(curation["key_highlights"])


def apply_highlights(rows: list[dict[str, str]], selected_pmids: set[str]) -> None:
    for row in rows:
        row["highlight"] = "yes" if clean_whitespace(row.get("pmid")) in selected_pmids else ""


def print_plan(month: str, model: str, curation: dict, rows: list[dict[str, str]]) -> None:
    titles_by_pmid = {
        clean_whitespace(row.get("pmid")): clean_whitespace(row.get("title"))
        for row in rows
    }
    print(f"\n[{month}] model={model}")
    print(f"headline: {curation['headline']}")
    print(f"paragraph: {curation['paragraph']}")
    print("key_highlights:")
    for bullet in curation["key_highlights"]:
        print(f"  - {bullet}")
    print("selected papers:")
    for pmid in curation["highlight_pmids"]:
        reason = curation["rationales"].get(pmid, "")
        label = titles_by_pmid.get(pmid, pmid)
        if reason:
            print(f"  - {pmid}: {label} [{reason}]")
        else:
            print(f"  - {pmid}: {label}")


def main() -> int:
    args = parse_args()
    sessions_path = ROOT / "sessions.csv"
    rows = load_rows(sessions_path)
    fieldnames = list(rows[0].keys()) if rows else []
    groups = month_groups(rows)

    requested_months = args.months or sorted(groups.keys())
    missing = [month for month in requested_months if month not in groups]
    if missing:
        raise SystemExit(f"Unknown months in sessions.csv: {', '.join(missing)}")

    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    touched_months = 0

    for month in requested_months:
        month_rows = groups[month]
        should_fill_summary = args.overwrite_summaries or not month_has_summary(month_rows)
        should_fill_highlights = args.overwrite_highlights or not month_has_highlights(month_rows)

        if not should_fill_summary and not should_fill_highlights:
            print(f"Skipping {month}: summary and highlights already present")
            continue

        candidates = build_candidate_pool(
            rows=month_rows,
            candidate_limit=args.candidate_limit,
        )
        if len(candidates) < args.highlights_per_month:
            raise RuntimeError(
                f"Month {month} has only {len(candidates)} candidates for "
                f"{args.highlights_per_month} requested highlights"
            )

        model, payload = request_curation(
            client=client,
            month=month,
            candidates=candidates,
            requested_highlights=args.highlights_per_month,
            preferred_model=args.model,
        )
        curation = validate_curation(
            payload=payload,
            candidates=candidates,
            requested_highlights=args.highlights_per_month,
        )
        print_plan(month, model, curation, month_rows)

        if should_fill_summary:
            apply_summary(month, month_rows, curation)
        if should_fill_highlights:
            apply_highlights(month_rows, set(curation["highlight_pmids"]))
        touched_months += 1

    if args.dry_run:
        print(f"\nDry run complete for {touched_months} month(s); no files written.")
        return 0

    save_rows(sessions_path, rows, fieldnames)
    print(f"\nUpdated {sessions_path} for {touched_months} month(s).")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        raise SystemExit(130)
