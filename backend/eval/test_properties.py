"""Property tests for the live scorer.

Not example-based tests ("this resume scores 73") — those break whenever anything
is tuned, and tell you nothing about why. These assert properties that must hold
for *any* sane scorer, whatever the weights are set to.

    cd backend && python -m pytest eval/test_properties.py -v

Deliberately not under tests/ and not in pytest.ini's testpaths: this suite is
allowed to fail. It measures the scorer's honest behaviour; the app test suite
verifies contracts. Mixing them would create pressure to weaken a measurement to
keep CI green.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.scoring import score_resume  # noqa: E402
from eval.run_benchmark import resume_dict  # noqa: E402

JD = ("Backend Engineer. Build and scale REST APIs in Python with FastAPI and "
      "PostgreSQL. You will design services, own deployments with Docker on AWS, "
      "and improve CI/CD. Requirements: 4+ years Python, strong SQL, Docker, cloud "
      "experience, testing discipline. Nice to have: Redis, Kubernetes.")

MATCHED = """MARIA SANTOS
Backend Engineer

EXPERIENCE
Backend Engineer, Corvid Systems - 2020 - Present
Built REST APIs in Python with FastAPI, backed by PostgreSQL. Deployed with Docker
on AWS and maintained the CI/CD pipeline. Wrote pytest suites for every service.
Software Engineer, Halden Labs - 2018 - 2020
Maintained a Python service layer and its SQL schema.

EDUCATION
BSc Computer Science, University of Porto, 2014 - 2018

SKILLS
Python, FastAPI, PostgreSQL, SQL, Docker, AWS, CI/CD, Git, pytest"""

UNRELATED = """TOM BRADLEY

Barista at Kettle & Co, 2021 to now. Trained six staff on espresso machines,
managed opening stock counts and handled customer complaints during peak hours.

SKILLS
Espresso, Latte art, Stock control, Customer service"""


def total(text: str, jd: str | None = JD) -> int:
    return score_resume(resume_dict(text), jd)["total"]


def category(text: str, key: str, jd: str | None = JD) -> int:
    report = score_resume(resume_dict(text), jd)
    return next(c["score"] for c in report["categories"] if c["key"] == key)


# ---------------------------------------------------------------- determinism
def test_identical_input_scores_identically():
    """Same bytes in, same number out. A scorer users cannot reproduce is a
    scorer they cannot trust, and it makes every other measurement here noise."""
    scores = {total(MATCHED) for _ in range(5)}
    assert len(scores) == 1, f"non-deterministic: {sorted(scores)}"


def test_full_report_is_stable_not_just_the_total():
    a = score_resume(resume_dict(MATCHED), JD)
    b = score_resume(resume_dict(MATCHED), JD)
    assert a == b


# ---------------------------------------------------------------- monotonicity
def test_adding_a_jd_required_skill_raises_the_score():
    without = MATCHED.replace(", Docker, AWS", "").replace("Deployed with Docker\non AWS and m", "M")
    with_skill = MATCHED
    assert total(with_skill) > total(without), (total(with_skill), total(without))


def test_removing_all_experience_lowers_the_score():
    stripped = MATCHED.split("EXPERIENCE")[0] + MATCHED.split("EDUCATION")[1]
    assert total(stripped) < total(MATCHED), (total(stripped), total(MATCHED))


def test_adding_a_missing_skill_never_lowers_the_score():
    """Weaker but broader: appending a JD skill must not make things worse."""
    for skill in ("Redis", "Kubernetes"):
        before = total(MATCHED)
        after = total(MATCHED + f", {skill}")
        assert after >= before, f"adding {skill} dropped the score {before} -> {after}"


# ---------------------------------------------------------------- discrimination
def test_matched_resume_beats_unrelated_by_a_wide_margin():
    matched, unrelated = total(MATCHED), total(UNRELATED)
    assert matched > unrelated + 25, (
        f"only {matched - unrelated} points between a perfect match and a barista")


def test_same_resume_scores_higher_against_its_own_jd():
    frontend_jd = ("Frontend Engineer. React, TypeScript, Next.js and Tailwind CSS. "
                   "Accessibility and web performance ownership.")
    assert total(MATCHED, JD) > total(MATCHED, frontend_jd)


# ---------------------------------------------------------------- bounds
ADVERSARIAL = {
    "empty": "",
    "whitespace": "   \n\t  \n",
    "one word": "python",
    "enormous": "python fastapi postgresql docker aws " * 4000,
    "one word repeated": "python " * 5000,
    "punctuation": "!@#$%^&*()_+{}|:\"<>?" * 200,
    "unicode": "简历 résumé Ingénieur ✅ " * 200,
    "newlines": "\n" * 5000,
}


JDS = {"real jd": JD, "no jd": None, "empty jd": "", "huge jd": "x" * 10000}


# explicit ids: the inputs are megabytes long and pytest would put them in the test name
@pytest.mark.parametrize("name,text", list(ADVERSARIAL.items()),
                         ids=list(ADVERSARIAL))
@pytest.mark.parametrize("jd", list(JDS.values()), ids=list(JDS))
def test_score_stays_in_bounds_on_adversarial_input(name, text, jd):
    report = score_resume(resume_dict(text), jd)
    assert 0 <= report["total"] <= 100, f"{name}: total {report['total']}"
    for cat in report["categories"]:
        assert 0 <= cat["score"] <= 100, f"{name}: {cat['key']} = {cat['score']}"


def test_empty_resume_does_not_crash_or_score_well():
    assert total("") < 50


# ---------------------------------------------------------------- gaming
STUFFED = (JD + "\n") * 20


def test_keyword_stuffing_does_not_beat_a_real_resume():
    """The adversarial case that matters: paste the job ad 20 times and submit it.

    It contains every keyword, so any coverage/BM25/embedding signal will love it.
    Nothing in the current scorer detects that it is not a resume — no employment
    dates, no achievements, no structure. This test states the bar; whether the
    scorer clears it is a finding, not a formality.
    """
    stuffed, real = total(STUFFED), total(MATCHED)
    assert stuffed < real, (
        f"keyword stuffing ({stuffed}) beat a genuine matched resume ({real})")


def test_keyword_stuffing_does_not_score_near_the_top():
    """Passes, but by 3 points (67 vs the 70 bar) — treat that as a warning light,
    not a clean result. A slightly longer paste would clear the threshold."""
    stuffed = total(STUFFED)
    assert stuffed < 70, f"pasted job ad scored {stuffed}/100 - that is a top-tier score"


def test_semantic_component_prefers_a_real_resume_over_the_pasted_ad():
    """Locates the weakness, so the fix has an address.

    KNOWN FAILURE as of this commit: semantic scores the pasted job ad 64 and the
    genuine matched resume 50. The component is pure text similarity, so the text
    most similar to the job description is the job description — a real resume,
    which describes the same work in its own words, looks *less* similar.

    Left failing on purpose. The scorer only survives keyword stuffing overall
    because the structural components (experience dates, education, projects)
    outvote the semantic one, which is luck rather than design.
    """
    real, stuffed = category(MATCHED, "semantic"), category(STUFFED, "semantic")
    assert real > stuffed, (
        f"semantic rates the pasted job ad ({stuffed}) above a real resume ({real})")
