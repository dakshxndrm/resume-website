"""LLM router — STUB for Phase 1.

Plan: Gemini free tier primary (1,500 req/day), Groq fallback. Every consented
call's (resume, output) pair is logged to training_examples for JEPA distillation.
"""


async def generate_suggestions(resume: dict, gaps: list[str]) -> list[dict]:
    raise NotImplementedError("Wire Gemini/Groq in Phase 1 — see docs/PROJECT_PLAN.md")
