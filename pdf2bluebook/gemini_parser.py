from __future__ import annotations

import json
from dataclasses import dataclass

from .pdf_extract import normalize_blanks, normalize_bullets


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
                    "choices": {"type": "OBJECT", "properties": {key: {"type": "STRING"} for key in "ABCD"}},
                    "answer": {"type": "STRING"}, "confidence": {"type": "NUMBER"},
                },
                "required": ["id", "passage", "question", "choices", "source_page", "confidence"],
            },
        },
    },
    "required": ["has_answer_key", "questions"],
}


def build_parser_prompt(raw_text: str) -> str:
    return """Extract SAT Digital Verbal multiple-choice questions from this PDF text.

Return only JSON matching the supplied schema. Each question must have exactly choices A, B, C, D. Copy the intended source wording faithfully. Use null for answer if no answer key exists. Do not infer answers.

PDF cleanup rules - apply before writing JSON:
1. Fix obvious text-extraction spelling, word-boundary, and spacing mistakes. Join a word split by a line-end hyphen (for example, "comprehen-\nsive" becomes "comprehensive"). Join broken fragments of one word, separate accidentally merged words, and correct an obvious misspelling when the intended standard American English word is unambiguous.
2. Do not rewrite, simplify, paraphrase, or change the meaning of a valid SAT question, passage, answer choice, proper noun, quotation, title, number, or punctuation. If a correction is uncertain, preserve the extracted text and lower confidence.
3. Tables and graphs are supplied separately as cropped images. Do not create `[TABLE]` markers or copy table cells into the passage, question, or answer choices.
4. Preserve every existing <u>, <b>, and <i> tag exactly in its original place. These tags are meaningful source formatting: underline often marks the evidence to analyze. Never remove, add, move, or convert these tags.
5. Treat one or more underscore blank rules separated only by spaces as one blank. Always output exactly 4 underscores (`____`) for each blank and never output multiple adjacent blanks for the same source line.
6. Every bullet item must be on a separate line in the form `• item text`; never combine bullet items into one line. Preserve line breaks between bullet items in the passage field.

Keep a shared passage with every question that uses it. source_page must be the number following the closest preceding '--- PAGE N ---' marker.

PDF TEXT:
""" + raw_text


def parse_questions(raw_text: str, *, api_key: str, model: str) -> ParseResult:
    from google import genai
    from google.genai import types

    prompt = build_parser_prompt(raw_text)
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=SCHEMA),
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
        answer = question.get("answer")
        normalized.append({
            "id": question.get("id") or f"q{position:02d}",
            "passage": normalize_blanks(normalize_bullets(str(question.get("passage", "")).strip())),
            "question": normalize_blanks(normalize_bullets(str(question.get("question", "")).strip())), "choices": choices,
            "answer": answer if answer in {"A", "B", "C", "D"} else None,
            "confidence": confidence, "source_page": int(question.get("source_page", 0) or 0), "image_id": None,
        })
    if not normalized:
        raise ValueError("Gemini không nhận diện được câu hỏi ABCD nào. Hãy kiểm tra PDF hoặc thử lại.")
    return ParseResult(normalized, bool(payload.get("has_answer_key")), errors)
