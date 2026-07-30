"""Load O*NET's public "Skills" and "Technology Skills" datasets into onet_skills.

Source: the O*NET Database, developed by the National Center for O*NET Development
under a grant from the U.S. Department of Labor, Employment and Training
Administration (USDOL/ETA). O*NET content is released under a Creative Commons
Attribution 4.0 License (CC BY 4.0) — see https://www.onetcenter.org/citations.html.
Required attribution: "This product was developed by the National Center for
O*NET Development. Used under the CC BY 4.0 license." Verify the current terms at
onetcenter.org before redistributing anything derived from this ingest.

This script does not download anything itself — no scraping, no credentials.
Grab the files yourself from https://www.onetcenter.org/database.html — as of the
current release they ship as "Essential Skills.csv" (formerly "Skills.txt") and
"Software Skills.csv" (formerly "Technology Skills.txt"), comma-delimited. Drop
them in scripts/data/ (gitignored, same pattern as eval/external/data/) and run
with no flags, or point elsewhere explicitly:

    cd backend
    python scripts/ingest_onet.py
    python scripts/ingest_onet.py --skills "path/to/essential_skills.csv" \
        --technology-skills "path/to/software_skills.csv"

Idempotent: upserts on (occupation, skill), so re-running against a newer O*NET
release updates importance in place instead of duplicating rows.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: E402

from app.core.db import Base, SessionLocal, engine  # noqa: E402
from app.models.models import OnetSkill  # noqa: E402

DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_SKILLS = DATA_DIR / "essential_skills.csv"
DEFAULT_TECH_SKILLS = DATA_DIR / "software_skills.csv"

# Essential Skills.csv carries several rating scales (Importance, Level, ...) per
# row; only "IM" is the 1-5 importance rating this table wants.
IMPORTANCE_SCALE_ID = "IM"

# Software Skills.csv has no numeric importance column, only a Hot Technology flag
# (Y/blank). This heuristic weight lets both files share one importance scale.
# ponytail: heuristic, not measured — replace if O*NET ever publishes real weights
# for this file, or if get_canonical_skills() ranking looks off in practice.
HOT_TECH_IMPORTANCE = 5.0
COLD_TECH_IMPORTANCE = 3.0


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def rows_from_skills(path: Path) -> list[dict]:
    """Essential Skills.csv: one row per (occupation, skill, scale). Importance only."""
    rows = []
    for row in _read_csv(path):
        if row["Scale ID"] != IMPORTANCE_SCALE_ID:
            continue
        rows.append({
            "occupation": row["Title"].strip(),
            "skill": row["Element Name"].strip(),
            "importance": float(row["Data Value"]),
            "source": "skills",
        })
    return rows


def rows_from_technology_skills(path: Path) -> list[dict]:
    """Software Skills.csv: one row per (occupation, named tool/technology)."""
    rows = []
    for row in _read_csv(path):
        hot = row.get("Hot Technology", "").strip().upper() == "Y"
        rows.append({
            "occupation": row["Title"].strip(),
            "skill": row["Workplace Example"].strip(),
            "importance": HOT_TECH_IMPORTANCE if hot else COLD_TECH_IMPORTANCE,
            "source": "technology_skills",
        })
    return rows


def upsert(rows: list[dict]) -> int:
    """Insert or update by (occupation, skill). Returns rows written."""
    if not rows:
        return 0
    stmt = pg_insert(OnetSkill).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["occupation", "skill"],
        set_={"importance": stmt.excluded.importance, "source": stmt.excluded.source},
    )
    with SessionLocal() as session:
        session.execute(stmt)
        session.commit()
    return len(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skills", type=Path, default=DEFAULT_SKILLS,
                     help=f"path to O*NET Essential Skills.csv (default: {DEFAULT_SKILLS})")
    ap.add_argument("--technology-skills", type=Path, default=DEFAULT_TECH_SKILLS,
                     help=f"path to O*NET Software Skills.csv (default: {DEFAULT_TECH_SKILLS})")
    args = ap.parse_args()

    skills_path = args.skills if args.skills.exists() else None
    tech_path = args.technology_skills if args.technology_skills.exists() else None
    if skills_path is None and tech_path is None:
        ap.error(
            f"neither file found — put them in {DATA_DIR} or pass --skills/--technology-skills explicitly"
        )

    Base.metadata.create_all(bind=engine, tables=[OnetSkill.__table__])

    total = 0
    if skills_path:
        rows = rows_from_skills(skills_path)
        total += upsert(rows)
        print(f"Essential Skills.csv: {len(rows)} importance rows upserted")
    if tech_path:
        rows = rows_from_technology_skills(tech_path)
        total += upsert(rows)
        print(f"Software Skills.csv: {len(rows)} rows upserted")

    print(f"done — {total} rows written to onet_skills")


if __name__ == "__main__":
    main()
