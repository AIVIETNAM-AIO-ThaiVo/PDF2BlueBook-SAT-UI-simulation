from __future__ import annotations

import json
from dataclasses import dataclass

from .pdf_extract import normalize_blanks, normalize_bullets
from .question_categories import (
    ALL_CATEGORIES,
    ALL_SUBCATEGORIES,
    category_prompt_text,
    normalize_category,
    normalize_subcategory,
)


@dataclass
class ParseResult:
    questions: list[dict]
    has_answer_key: bool
    errors: list[dict[str, str]]


SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "has_answer_key": {"type": "BOOLEAN"},
        "questions": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "id": {"type": "STRING"}, "passage": {"type": "STRING"},
                    "question": {"type": "STRING"},
                    "source_page": {"type": "INTEGER"},
                    "module": {"type": "STRING", "enum": ["Module 1", "Module 2", "None"]},
                    "choices": {"type": "OBJECT", "properties": {key: {"type": "STRING"} for key in "ABCD"}},
                    "answer": {"type": "STRING"}, "confidence": {"type": "NUMBER"},
                    "category": {"type": "STRING", "enum": list(ALL_CATEGORIES)},
                    "subcategory": {"type": "STRING", "enum": list(ALL_SUBCATEGORIES)},
                },
                "required": ["id", "passage", "question", "choices", "source_page", "module", "confidence", "category", "subcategory"],
            },
        },
    },
    "required": ["has_answer_key", "questions"],
}


def build_parser_prompt(raw_text: str, *, answer_key_attached: bool = False) -> str:
    answer_key_instruction = (
        "Answer-key page images are attached after this prompt. Use them as the authoritative answer key and map answers to the parsed questions."
        if answer_key_attached else
        "No answer-key page image was selected. Use answer information from the extracted PDF text only; if it is absent, output no answer."
    )
    return f"""Extract SAT Digital Verbal multiple-choice questions from this PDF text.

Return only JSON matching the supplied schema. Each question must have exactly choices A, B, C, D. Copy the intended source wording faithfully. Use null for answer if no answer key exists. Do not infer answers.
{answer_key_instruction}

PDF cleanup rules - apply before writing JSON:
1. Fix obvious text-extraction spelling, word-boundary, and spacing mistakes. Join a word split by a line-end hyphen (for example, "comprehen-\nsive" becomes "comprehensive"). Join broken fragments of one word, separate accidentally merged words, and correct an obvious misspelling when the intended standard American English word is unambiguous.
2. Do not rewrite, simplify, paraphrase, or change the meaning of a valid SAT question, passage, answer choice, proper noun, quotation, title, number, or punctuation. If a correction is uncertain, preserve the extracted text and lower confidence.
3. Tables and graphs are supplied separately as cropped images. Do not create `[TABLE]` markers or copy table cells into the passage, question, or answer choices.
4. Preserve every existing <u>, <b>, and <i> tag exactly in its original place. These tags are meaningful source formatting: underline often marks the evidence to analyze. Never remove, add, move, or convert these tags.
5. Treat one or more underscore blank rules separated only by spaces as one blank. Always output exactly 4 underscores (`____`) for each blank and never output multiple adjacent blanks for the same source line.
6. Every bullet item must be on a separate line in the form `• item text`; never combine bullet items into one line. Preserve line breaks between bullet items in the passage field.
7. Classify every question using exactly one category and one matching subcategory from this taxonomy. Do not invent or translate labels:
""" + category_prompt_text() + """

Keep a shared passage with every question that uses it. source_page must be the number following the closest preceding '--- PAGE N ---' marker. Determine module from the extracted PDF text: if the closest preceding module marker is Module 1 or Module 2, return that exact value in the question's `module` metadata; if no module marker exists, return "None". Do not infer a module from question content or answer-key images.

PDF TEXT:
""" + raw_text


def parse_questions(
    raw_text: str,
    *,
    api_key: str,
    model: str,
    answer_key_images: list[bytes] | None = None,
) -> ParseResult:
    from google import genai
    from google.genai import types

    answer_key_images = answer_key_images or []
    prompt = build_parser_prompt(raw_text, answer_key_attached=bool(answer_key_images))
    client = genai.Client(api_key=api_key)
    contents: list[object] = [prompt]
    contents.extend(
        types.Part.from_bytes(data=image_bytes, mime_type="image/png")
        for image_bytes in answer_key_images
    )
    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=SCHEMA,
            temperature=0.0,
        ),
    )
    payload = json.loads(response.text)
    errors: list[dict[str, str]] = []
    normalized: list[dict] = []
    for position, question in enumerate(payload.get("questions", []), 1):
        choices = {
            key: normalize_blanks(str(question.get("choices", {}).get(key, "")).strip())
            for key in "ABCD"
        }
        missing = [key for key, value in choices.items() if not value]
        confidence = float(question.get("confidence", 0))
        if missing:
            errors.append({"level": "warning", "code": "MISSING_CHOICE", "message": f"Câu {position} thiếu đáp án: {', '.join(missing)}."})
        if confidence < 0.8:
            errors.append({"level": "warning", "code": "LOW_CONFIDENCE", "message": f"Câu {position} có confidence {confidence:.2f}; cần review."})
        category = normalize_category(question.get("category"))
        subcategory = normalize_subcategory(question.get("subcategory"), category)
        if category is None or subcategory is None:
            errors.append({
                "level": "warning", "code": "INVALID_CATEGORY",
                "message": f"Câu {position} có category/subcategory không hợp lệ; cần review.",
            })
        answer = question.get("answer")
        source_page = int(question.get("source_page", 0) or 0)
        module_value = question.get("module")
        module = module_value if module_value in {"Module 1", "Module 2"} else None
        normalized.append({
            "id": question.get("id") or f"q{position:02d}",
            "passage": normalize_blanks(normalize_bullets(str(question.get("passage", "")).strip())),
            "question": normalize_blanks(normalize_bullets(str(question.get("question", "")).strip())), "choices": choices,
            "answer": answer if answer in {"A", "B", "C", "D"} else None,
            "category": category or "Uncategorized",
            "subcategory": subcategory or "Uncategorized",
            "confidence": confidence, "source_page": source_page, "module": module, "image_id": None,
        })
    if not normalized:
        raise ValueError("Gemini không nhận diện được câu hỏi ABCD nào. Hãy kiểm tra PDF hoặc thử lại.")
    return ParseResult(normalized, bool(payload.get("has_answer_key")) or bool(answer_key_images), errors)
