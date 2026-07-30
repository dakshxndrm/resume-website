from pathlib import Path

from scripts.ingest_onet import rows_from_skills, rows_from_technology_skills

ESSENTIAL_SKILLS_CSV = (
    "O*NET-SOC Code,Title,Element ID,Element Name,Scale ID,Scale Name,Data Value\n"
    "11-1011.00,Chief Executives,2.A.1.a,Reading Comprehension,IM,Importance,4.12\n"
    "11-1011.00,Chief Executives,2.A.1.a,Reading Comprehension,LV,Level,4.62\n"
)

SOFTWARE_SKILLS_CSV = (
    "O*NET-SOC Code,Title,Workplace Example,Element ID,Element Name,Hot Technology,In Demand\n"
    "11-1011.00,Chief Executives,Adobe Acrobat,2.E.5.b,Document management software,Y,N\n"
    "11-1011.00,Chief Executives,AdSense Tracker,2.E.6.f,Data base user interface software,N,N\n"
)


def test_rows_from_skills_keeps_only_importance_scale(tmp_path: Path):
    path = tmp_path / "Essential Skills.csv"
    path.write_text(ESSENTIAL_SKILLS_CSV, encoding="utf-8")
    rows = rows_from_skills(path)
    assert rows == [{
        "occupation": "Chief Executives",
        "skill": "Reading Comprehension",
        "importance": 4.12,
        "source": "skills",
    }]


def test_rows_from_technology_skills_weights_hot_technology_higher(tmp_path: Path):
    path = tmp_path / "Software Skills.csv"
    path.write_text(SOFTWARE_SKILLS_CSV, encoding="utf-8")
    rows = rows_from_technology_skills(path)
    by_skill = {r["skill"]: r["importance"] for r in rows}
    assert by_skill["Adobe Acrobat"] > by_skill["AdSense Tracker"]
