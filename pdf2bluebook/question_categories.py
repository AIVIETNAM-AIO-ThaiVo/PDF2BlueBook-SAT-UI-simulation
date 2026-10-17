"""Canonical SAT Reading and Writing question categories used by parsing and UI."""

from __future__ import annotations


QUESTION_CATEGORIES: dict[str, tuple[str, ...]] = {
    "Craft and Structure": (
        "Words in Context",
        "Text Structure and Purpose",
        "Cross-Text Connections",
    ),
    "Information and Ideas": (
        "Central Ideas and Details",
        "Inferences",
        "Command of Evidence — Textual",
        "Command of Evidence — Quantitative",
    ),
    "Standard English Conventions": (
        "Boundaries (Punctuation and Sentence Boundaries)",
        "Form, Structure, and Sense",
    ),
    "Expression of Ideas": (
        "Transitions",
        "Rhetorical Synthesis",
    ),
}

ALL_CATEGORIES = tuple(QUESTION_CATEGORIES)
ALL_SUBCATEGORIES = tuple(subcategory for values in QUESTION_CATEGORIES.values() for subcategory in values)


def category_prompt_text() -> str:
    """Return the taxonomy in a compact format suitable for the Gemini prompt."""
    return "\n".join(
        f'- {category}: {", ".join(subcategories)}'
        for category, subcategories in QUESTION_CATEGORIES.items()
    )


def normalize_category(value: object) -> str | None:
    value = str(value or "").strip()
    return value if value in QUESTION_CATEGORIES else None


def normalize_subcategory(value: object, category: str | None) -> str | None:
    value = str(value or "").strip()
    allowed = QUESTION_CATEGORIES.get(category or "", ())
    return value if value in allowed else None
