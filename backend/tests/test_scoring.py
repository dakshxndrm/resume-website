import pytest

from app.services import scoring
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


# ---------------------------------------------------------------- SBERT semantic
def _semantic_of(resume_text, jd):
    return scoring._semantic_score(resume_text, jd)


# Same job, described in words the JD never uses. The lexical signals score this
# near zero; SBERT is the reason it should not.
PARAPHRASED_RESUME = (
    "Server-side developer. I design and ship HTTP web services using Django and "
    "Flask, store data in relational databases, containerise everything and run it "
    "on cloud infrastructure with automated build pipelines."
)
UNRELATED_RESUME = (
    "Barista and latte artist. Managed cafe inventory, trained staff on espresso "
    "machines and handled customer complaints during peak hours."
)


@pytest.fixture
def fresh_model_cache():
    """_sbert() memoises with lru_cache — clear it around any test that changes
    whether the model is available, or the previous test's answer leaks in."""
    scoring._sbert.cache_clear()
    yield
    # a test may have monkeypatched _sbert outright, in which case there is no cache
    getattr(scoring._sbert, "cache_clear", lambda: None)()


@pytest.fixture
def sbert_required(fresh_model_cache):
    if not scoring.warm_semantic_model():
        pytest.skip("SBERT unavailable (not installed, or SBERT_DISABLED set)")


def test_sbert_separates_paraphrased_match_from_unrelated(sbert_required):
    """The whole point of adding SBERT: a semantic match with no shared vocabulary
    must beat an unrelated resume by a wide margin, not a rounding error."""
    match = _semantic_of(PARAPHRASED_RESUME, BACKEND_JD)
    unrelated = _semantic_of(UNRELATED_RESUME, BACKEND_JD)

    assert match > unrelated + 10, (match, unrelated)


def test_sbert_ranks_exact_match_above_paraphrase_above_unrelated(sbert_required):
    exact = _semantic_of(
        "Backend engineer building REST APIs in Python with FastAPI and PostgreSQL, "
        "deployed with Docker on AWS.", BACKEND_JD)
    paraphrase = _semantic_of(PARAPHRASED_RESUME, BACKEND_JD)
    unrelated = _semantic_of(UNRELATED_RESUME, BACKEND_JD)

    assert exact > paraphrase > unrelated, (exact, paraphrase, unrelated)


def test_sbert_disabled_falls_back_to_lexical(monkeypatch, fresh_model_cache):
    """SBERT_DISABLED=1 must reproduce the pre-SBERT score exactly, not a
    deflated one — the lexical half is renormalised, not left at 55%."""
    monkeypatch.setenv("SBERT_DISABLED", "1")
    assert scoring._sbert() is None

    resume = PARAPHRASED_RESUME
    coverage_and_bm25 = scoring._semantic_score(resume, BACKEND_JD)

    # recompute the old formula by hand and require an exact match
    jd_tokens = scoring._tokens(BACKEND_JD)
    resume_tokens = scoring._tokens(resume)
    jd_set = set(jd_tokens)
    coverage = len(jd_set & set(resume_tokens)) / len(jd_set)
    from rank_bm25 import BM25Okapi
    raw = BM25Okapi([resume_tokens]).get_scores(jd_tokens)[0]
    expected = round(min(100, (0.6 * coverage + 0.4 * min(1.0, raw / len(jd_tokens))) * 100))

    assert coverage_and_bm25 == expected


def test_missing_package_falls_back_and_warns(monkeypatch, fresh_model_cache, caplog):
    """Simulate sentence-transformers not being installed at all."""
    import builtins

    real_import = builtins.__import__

    def no_sentence_transformers(name, *args, **kwargs):
        if name.startswith("sentence_transformers"):
            raise ImportError("No module named 'sentence_transformers'")
        return real_import(name, *args, **kwargs)

    monkeypatch.delenv("SBERT_DISABLED", raising=False)
    monkeypatch.setattr(builtins, "__import__", no_sentence_transformers)

    assert scoring._sbert() is None
    assert scoring.warm_semantic_model() is False
    assert "falling back" in caplog.text.lower()

    # and a real score request still works
    r = score_resume({"skills": ["Python"], "work": [{}], "education": [],
                      "projects": [], "raw_text": PARAPHRASED_RESUME, "word_count": 30},
                     BACKEND_JD)
    assert 0 <= next(c["score"] for c in r["categories"] if c["key"] == "semantic") <= 100


def test_broken_encode_never_crashes_a_score_request(monkeypatch, fresh_model_cache):
    """Model loads but encoding blows up mid-request — must degrade, not 500."""
    class ExplodingModel:
        def encode(self, *_a, **_kw):
            raise RuntimeError("CUDA out of memory")

    monkeypatch.setattr(scoring, "_sbert", lambda: ExplodingModel())

    assert scoring._sbert_similarity(PARAPHRASED_RESUME, BACKEND_JD) is None
    r = score_resume({"skills": [], "work": [], "education": [], "projects": [],
                      "raw_text": PARAPHRASED_RESUME, "word_count": 30}, BACKEND_JD)
    assert 0 <= r["total"] <= 100


def test_no_job_description_stays_neutral_regardless_of_sbert(fresh_model_cache):
    """The neutral-60 shortcut must run before any model is touched."""
    assert scoring._semantic_score("Backend engineer with FastAPI", None) == 60
    assert scoring._semantic_score("", BACKEND_JD) == 60
