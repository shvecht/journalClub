from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

DATA_PATH = Path("data/journal_club.json")
SUMMARY_PATH = Path("data/subject_summary.json")


@dataclass(frozen=True)
class SubjectRule:
    name: str
    patterns: Iterable[re.Pattern]

    def matches(self, text: str) -> bool:
        return any(pattern.search(text) for pattern in self.patterns)


def compile_rules() -> List[SubjectRule]:
    raw_rules = {
        "Rhinology & Allergy": [
            r"rhino",
            r"sinus",
            r"nasal",
            r"nose",
            r"septum",
            r"polyp",
            r"olfact",
            r"smell",
            r"sinonasal",
            r"nasophary",
            r"epistaxis",
        ],
        "Otology & Neurotology": [
            r"cochlea",
            r"ear",
            r"otic",
            r"tympan",
            r"mastoid",
            r"ossicul",
            r"vestib",
            r"tinnitus",
            r"hearing",
            r"ossicular",
            r"otos",
            r"eustachian",
        ],
        "Audiology & Hearing Science": [
            r"audiology",
            r"audiogram",
            r"speech perception",
            r"listening",
            r"hearing aid",
            r"cochlear implant",
        ],
        "Laryngology & Voice": [
            r"laryn",
            r"vocal cord",
            r"voice",
            r"phonation",
            r"glott",
            r"dysphonia",
            r"esophag",
        ],
        "Airway & Trachea": [
            r"airway",
            r"trache",
            r"bronch",
            r"intubat",
            r"decann",
            r"stent",
        ],
        "Sleep Medicine": [
            r"sleep",
            r"apnea",
            r"hypopnea",
            r"cpap",
            r"osa\b",
        ],
        "Head & Neck Oncology": [
            r"carcinoma",
            r"cancer",
            r"tumou?r",
            r"neoplasm",
            r"sarcoma",
            r"oncology",
            r"malignan",
            r"papilloma",
        ],
        "Endocrine (Thyroid/Parathyroid)": [
            r"thyroid",
            r"parathy",
            r"endocrine",
        ],
        "Salivary & Oral Cavity": [
            r"salivar",
            r"parotid",
            r"submandibular",
            r"sublingual",
            r"sialo",
            r"oral cavity",
            r"tongue",
            r"palate",
            r"tonsil",
        ],
        "Facial Plastics & Reconstruction": [
            r"facial",
            r"reconstruct",
            r"rhinoplast",
            r"cleft",
            r"aesthe",
            r"cosmetic",
            r"flap",
            r"graft",
            r"scar",
        ],
        "Skull Base & Cranial": [
            r"skull base",
            r"cranial",
            r"intracran",
            r"cerebrospinal",
            r"csf",
            r"pituitar",
            r"meningioma",
        ],
        "Trauma": [
            r"trauma",
            r"fracture",
            r"injur",
            r"gunshot",
            r"laceration",
        ],
        "Infectious Disease": [
            r"infect",
            r"viral",
            r"bacterial",
            r"fungal",
            r"abscess",
            r"mycobacter",
            r"sepsis",
        ],
    }
    return [SubjectRule(name, [re.compile(pat, re.IGNORECASE) for pat in patterns]) for name, patterns in raw_rules.items()]


SUBJECT_RULES = compile_rules()
PEDIATRIC_PATTERN = re.compile(r"\b(pediatric|child|children|infant|neonate|adolesc|toddler|newborn)\b", re.IGNORECASE)


def load_sessions():
    with DATA_PATH.open() as f:
        return json.load(f)["sessions"]


def assign_subjects(text: str) -> List[str]:
    matches = [rule.name for rule in SUBJECT_RULES if rule.matches(text)]
    if PEDIATRIC_PATTERN.search(text):
        matches.append("Pediatrics")

    if not matches:
        matches.append("General ENT/Other")

    return sorted(set(matches))


def update_sessions(sessions):
    for session in sessions:
        text = " ".join(
            filter(
                None,
                [
                    session.get("title", ""),
                    session.get("journal", ""),
                    session.get("abstract", ""),
                    session.get("notes", ""),
                ],
            )
        )
        session["subjects"] = assign_subjects(text)


def write_output(sessions):
    data = {"sessions": sessions}
    with DATA_PATH.open("w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    by_month: defaultdict[str, Counter] = defaultdict(Counter)
    for session in sessions:
        date = session.get("date", "")
        month = date[:7] if date else "unknown"
        for subject in session.get("subjects", []):
            by_month[month][subject] += 1

    summary = {month: dict(counter.most_common()) for month, counter in sorted(by_month.items())}
    with SUMMARY_PATH.open("w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
        f.write("\n")


def main():
    sessions = load_sessions()
    update_sessions(sessions)
    write_output(sessions)


if __name__ == "__main__":
    main()
