from app.services.scoring import WEIGHTS, score_resume

SEVERITIES = {"high", "medium", "low"}

BACKEND_JD = (
    "Backend Engineer. We are hiring an engineer to build REST APIs in Python "
    "with FastAPI and PostgreSQL, deployed with Docker on AWS."
)


def _resume(**over):
    base = {"skills": [], "work": [], "education": [], "projects": [], "raw_text": "", "word_count": 0}
    return {**base, **over}


# ---------------------------------------------------------------- existing
def test_weights_sum_to_one():
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def test_score_bounds():
    empty = score_resume({"skills": [], "work": [], "education": [], "projects": []})
    full = score_resume({
        "skills": ["a"] * 10,
        "work": [{}] * 4,
        "education": [{}] * 2,
        "projects": [{}] * 3,
    })
    assert 0 <= empty["total"] <= 100
    assert 0 <= full["total"] <= 100
    assert full["total"] > empty["total"]


def test_report_shape():
    r = score_resume({"skills": ["python"], "work": [], "education": [], "projects": []})
    assert {c["key"] for c in r["categories"]} == set(WEIGHTS.keys())
    assert isinstance(r["suggestions"], list) and r["suggestions"]


# ---------------------------------------------------------------- bounds / stress
def test_score_bounds_under_stress():
    """Absurd inputs must still land in 0..100 — nothing overflows the caps."""
    extremes = [
        score_resume({}),
        score_resume(_resume(skills=["x"] * 1000, work=[{}] * 500,
                             education=[{}] * 200, projects=[{}] * 300)),
        score_resume(_resume(raw_text="python " * 20000, word_count=20000), BACKEND_JD),
        score_resume(_resume(raw_text="a"), "b" * 5000),
    ]
    for r in extremes:
        assert 0 <= r["total"] <= 100
        for cat in r["categories"]:
            assert 0 <= cat["score"] <= 100


# ---------------------------------------------------------------- shape contract
def test_report_contract_has_every_key_the_frontend_needs():
    r = score_resume(_resume(skills=["Python"], raw_text="Python engineer", word_count=2), BACKEND_JD)

    assert set(r) == {"total", "verdict", "categories", "suggestions", "missingSkills"}
    assert isinstance(r["total"], int) and isinstance(r["verdict"], str) and r["verdict"]
    assert isinstance(r["missingSkills"], list)

    # categories match WEIGHTS exactly — same keys, same weights, same order
    assert [c["key"] for c in r["categories"]] == list(WEIGHTS)
    for cat in r["categories"]:
        assert set(cat) == {"key", "label", "score", "weight"}
        assert isinstance(cat["label"], str) and cat["label"]
        assert isinstance(cat["score"], int)
        assert cat["weight"] == WEIGHTS[cat["key"]]


def test_suggestions_always_present_and_well_formed():
    reports = [
        score_resume({}),
        score_resume(_resume(skills=["Python"] * 12, work=[{}] * 3, education=[{}] * 2,
                             projects=[{}] * 3, raw_text="Python " * 400, word_count=400)),
        score_resume(_resume(skills=["Python"], raw_text="Python", word_count=1), BACKEND_JD),
    ]
    for r in reports:
        assert isinstance(r["suggestions"], list) and r["suggestions"]
        for s in r["suggestions"]:
            assert set(s) == {"id", "severity", "category", "title", "why"}
            assert s["severity"] in SEVERITIES
            assert s["category"] in WEIGHTS
            assert s["title"] and s["why"]


# ---------------------------------------------------------------- job description
def test_no_job_description_is_neutral():
    r = score_resume(_resume(skills=["Python"], raw_text="Python engineer", word_count=2))
    semantic = next(c for c in r["categories"] if c["key"] == "semantic")
    assert semantic["score"] == 60, "no JD means nothing to compare against — stay neutral"
    assert r["missingSkills"] == []


def test_missing_skills_reflects_job_description():
    jd = "We need Python, Kubernetes, Rust and GraphQL for this platform role."
    resume = _resume(
        skills=["Python", "Docker"],
        raw_text="Experienced Python developer who ships with Docker.",
        word_count=8,
    )
    missing = {s.lower() for s in score_resume(resume, jd)["missingSkills"]}

    assert {"kubernetes", "rust", "graphql"} <= missing   # asked for, not present
    assert "python" not in missing                        # asked for AND present
    assert "docker" not in missing                        # present, JD never asked


def test_relevant_resume_beats_unrelated_resume_on_same_jd():
    common = {"skills": ["Python"], "work": [{}], "education": [{}], "projects": [{}]}
    relevant = score_resume({**common, "raw_text": (
        "Backend engineer building REST APIs in Python with FastAPI and "
        "PostgreSQL, deployed with Docker on AWS."
    ), "word_count": 18}, BACKEND_JD)
    unrelated = score_resume({**common, "raw_text": (
        "Barista and latte artist. Managed cafe inventory, trained staff on "
        "espresso machines and handled customer complaints."
    ), "word_count": 18}, BACKEND_JD)

    def semantic(r):
        return next(c["score"] for c in r["categories"] if c["key"] == "semantic")

    assert semantic(relevant) > semantic(unrelated)
    assert relevant["total"] > unrelated["total"]
