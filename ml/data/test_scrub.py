"""Proof that the scrubber actually removes PII, on synthetic samples.

    cd ml && python data/test_scrub.py        # plain run, no pytest needed
    python -m pytest ml/data/test_scrub.py    # or under pytest, if it is installed

Synthetic on purpose: no real person's details belong in a test file. The samples
below imitate the shapes the OCR corpora actually produce, including the mangled
spacing OCR introduces around punctuation.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scrub import (alpha_ratio, broken_word_ratio, has_residual_pii,  # noqa: E402
                   is_usable, scrub)

# --- synthetic samples, each shaped like a real OCR'd resume header ----------
CLASSIC = """JANE ELIZABETH DOE
221B Baker Street, Apartment 4, London NW1 6XE
Phone: +44 7700 900123
Email: jane.doe@example.com
linkedin.com/in/janedoe

PROFESSIONAL SUMMARY
Backend engineer with 8 years building Python services. Cut p95 latency 40%
between 2019 - 2023 while scaling to 20,000 requests per minute.

EXPERIENCE
Senior Engineer, Acme Corp - 2021 - Present
Reported to Sarah Klein. Owned the payments service."""

INDIAN_FORMAT = """Rahul Sharma
Flat 302, Green Park Colony, Sector 12, Pincode 560037
Mobile : 98765 43210
E-Mail : rahul.sharma91@gmail.com

SKILLS
Java, Spring Boot, MySQL, Docker"""

OCR_MANGLED = """MARIA  SANTOS
Contact - (555) 010-9988
maria .santos @ example .org
www.mariasantos.dev/portfolio

EXPERIENCE
Data analyst, 2018 - 2021. Built reports in SQL."""

NO_PII = """PROFESSIONAL SUMMARY
Frontend developer focused on accessible interfaces. Shipped a design system of
60 React components used by four product teams, and cut Largest Contentful Paint
from 4.1s to 1.3s across the marketing site."""


def check(name: str, condition: bool, detail: str = "") -> None:
    assert condition, f"{name}: {detail}"


def test_emails_are_removed():
    for sample in (CLASSIC, INDIAN_FORMAT, OCR_MANGLED):
        out = scrub(sample)
        for leak in ("jane.doe@example.com", "rahul.sharma91@gmail.com",
                     "maria .santos @ example .org"):
            assert leak not in out, leak
        assert "@" not in out.replace("[email]", ""), out


def test_phone_numbers_are_removed():
    assert "7700 900123" not in scrub(CLASSIC)
    assert "98765 43210" not in scrub(INDIAN_FORMAT)
    assert "010-9988" not in scrub(OCR_MANGLED)
    assert "555" not in scrub(OCR_MANGLED)


def test_urls_and_profiles_are_removed():
    assert "linkedin.com/in/janedoe" not in scrub(CLASSIC)
    assert "mariasantos.dev/portfolio" not in scrub(OCR_MANGLED)


def test_header_name_lines_are_redacted():
    assert "JANE ELIZABETH DOE" not in scrub(CLASSIC)
    assert "Rahul Sharma" not in scrub(INDIAN_FORMAT)
    assert "MARIA  SANTOS" not in scrub(OCR_MANGLED)


def test_addresses_in_the_header_are_redacted():
    assert "Baker Street" not in scrub(CLASSIC)
    assert "Green Park Colony" not in scrub(INDIAN_FORMAT)


def test_the_training_signal_survives():
    """Over-redaction is a failure too — a corpus of [redacted] teaches nothing."""
    out = scrub(CLASSIC)
    for keep in ("Backend engineer", "Python", "20,000 requests", "2019 - 2023",
                 "40%", "Acme Corp", "payments service"):
        assert keep in out, keep

    skills = scrub(INDIAN_FORMAT)
    for keep in ("Java", "Spring Boot", "MySQL", "Docker"):
        assert keep in skills, keep


def test_section_headings_are_not_mistaken_for_names():
    """'PROFESSIONAL SUMMARY' matches the all-caps name shape; it must survive."""
    out = scrub(NO_PII)
    assert "PROFESSIONAL SUMMARY" in out
    assert out.strip() == NO_PII.strip(), "clean text should pass through untouched"


def test_known_limitation_names_in_body_text_survive():
    """Documents the gap honestly rather than implying the scrubber is complete."""
    assert "Sarah Klein" in scrub(CLASSIC), (
        "if this starts passing, NER landed — update the docstring in scrub.py")


def test_residual_check_agrees_with_the_scrubber():
    for sample in (CLASSIC, INDIAN_FORMAT, OCR_MANGLED):
        assert has_residual_pii(sample), "sample should contain PII before scrubbing"
        assert not has_residual_pii(scrub(sample)), scrub(sample)


def test_empty_and_garbage_input():
    assert scrub("") == ""
    assert scrub("\n\n\n").strip() == ""


# --- OCR quality signals -----------------------------------------------------
# Two distinct OCR failure modes, which is why there are two signals.
# Symbol soup: mostly punctuation, so alpha_ratio catches it.
SYMBOL_SOUP = "|_l1 ;: !I 4^ }{ 0O ll1 ;;; ~~ ][ %$# ||| §§ ¬¬ >> << ** ;;"
# Vowel-stripped fragments: high alpha_ratio, so only broken_word_ratio catches it.
VOWEL_STRIPPED = ("Wrk Exprnc ; Cmpny Nm ; Rspnsblts : mngd tm f ppl , dlvrd prjcts "
                  "n tm nd wthn bdgt ; skllz : sql , jvscrpt , pythn , dckr")


def test_clean_text_passes_both_quality_signals():
    assert alpha_ratio(NO_PII) > 0.80, alpha_ratio(NO_PII)
    assert broken_word_ratio(NO_PII) < 0.05, broken_word_ratio(NO_PII)
    assert is_usable(NO_PII)


def test_symbol_soup_is_caught_by_alpha_ratio():
    assert alpha_ratio(SYMBOL_SOUP) < 0.40, alpha_ratio(SYMBOL_SOUP)
    assert not is_usable(SYMBOL_SOUP)


def test_vowel_stripped_ocr_is_caught_by_broken_word_ratio():
    """The nastier failure mode: it is *mostly letters*, so alpha_ratio alone
    would wave it through."""
    assert alpha_ratio(VOWEL_STRIPPED) > 0.60, "sample should look alphabetic"
    assert broken_word_ratio(VOWEL_STRIPPED) > 0.30, broken_word_ratio(VOWEL_STRIPPED)
    assert not is_usable(VOWEL_STRIPPED)


def test_empty_text_is_not_usable():
    assert not is_usable("")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(tests)} scrub tests passed")
