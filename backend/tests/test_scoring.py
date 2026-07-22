from app.services.scoring import score_resume, WEIGHTS


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
