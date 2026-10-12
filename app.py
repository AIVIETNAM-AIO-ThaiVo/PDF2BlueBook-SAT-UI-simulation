"""Local Streamlit application for turning text PDFs into offline SAT practice HTML."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

import streamlit as st

from pdf2bluebook.pdf_extract import extract_pdf
from pdf2bluebook.gemini_parser import parse_questions
from pdf2bluebook.modern_html_renderer import render_exam_html


st.set_page_config(page_title="PDF to BlueBook", page_icon="📘", layout="wide")


def _new_session() -> None:
    st.session_state.questions = []
    st.session_state.images = {}
    st.session_state.errors = []
    st.session_state.source_name = ""
    st.session_state.has_answer_key = None


if "questions" not in st.session_state:
    _new_session()


def _save_upload(upload) -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix="pdf2bluebook_"))
    target = temp_dir / upload.name
    target.write_bytes(upload.getvalue())
    return target


def _review_question(index: int) -> None:
    question = st.session_state.questions[index]
    st.subheader(f"Review câu {index + 1}")
    with st.form(f"review-{index}"):
        passage = st.text_area("Passage", value=question.get("passage", ""), height=180)
        text = st.text_area("Câu hỏi", value=question.get("question", ""), height=100)
        cols = st.columns(2)
        choices = {}
        for i, label in enumerate("ABCD"):
            with cols[i % 2]:
                choices[label] = st.text_area(
                    f"Đáp án {label}", value=question.get("choices", {}).get(label, ""), height=80
                )
        answer_options = ["(Không có đáp án)", "A", "B", "C", "D"]
        existing_answer = question.get("answer") or "(Không có đáp án)"
        answer = st.selectbox("Đáp án đúng", answer_options, index=answer_options.index(existing_answer))
        image_options = ["(Không có ảnh)", *st.session_state.images.keys()]
        existing_image = question.get("image_id") or "(Không có ảnh)"
        image_id = st.selectbox(
            "Ảnh đặt sau passage, trước câu hỏi", image_options,
            index=image_options.index(existing_image) if existing_image in image_options else 0,
        )
        if st.form_submit_button("Lưu thay đổi", type="primary"):
            question.update({
                "passage": passage.strip(), "question": text.strip(), "choices": choices,
                "answer": None if answer == "(Không có đáp án)" else answer,
                "image_id": None if image_id == "(Không có ảnh)" else image_id,
            })
            st.session_state.questions[index] = question
            st.success("Đã lưu câu hỏi.")


st.title("PDF to BlueBook")
st.caption("Chuyển PDF SAT Verbal có text layer thành một file HTML luyện tập offline.")

with st.sidebar:
    st.header("Thiết lập")
    api_key = st.text_input("Gemini API key", type="password", help="Key chỉ dùng trong phiên Streamlit này.")
    model = st.text_input("Gemini model", value="gemini-3-flash-preview")
    duration = st.number_input("Thời gian mỗi bài (phút)", min_value=1, max_value=240, value=32)
    st.divider()
    st.caption("MVP chỉ nhận PDF có text layer; PDF scan sẽ bị từ chối.")

upload = st.file_uploader("Chọn file PDF", type=["pdf"])
if upload and st.button("Phân tích PDF", type="primary", disabled=not api_key):
    with st.status("Đang xử lý PDF...", expanded=True) as status:
        try:
            pdf_path = _save_upload(upload)
            result = extract_pdf(pdf_path, gemini_api_key=api_key, gemini_model=model)
            st.write(f"Đã trích xuất {result.page_count} trang, {len(result.images)} ảnh.")
            parsed = parse_questions(result.text, api_key=api_key, model=model)
            page_images: dict[str, list[str]] = {}
            for image_id, metadata in result.images.items():
                page_images.setdefault(metadata["page"], []).append(image_id)
            for question in parsed.questions:
                candidates = page_images.get(str(question.get("source_page", "")), [])
                if len(candidates) == 1:
                    question["image_id"] = candidates[0]
            st.session_state.questions = parsed.questions
            st.session_state.images = result.images
            st.session_state.errors = [*result.errors, *parsed.errors]
            st.session_state.source_name = upload.name
            st.session_state.has_answer_key = parsed.has_answer_key
            status.update(label="Đã sẵn sàng để review.", state="complete")
        except Exception as exc:
            status.update(label="Không thể xử lý PDF.", state="error")
            st.error(str(exc))

if st.session_state.questions:
    st.divider()
    questions = st.session_state.questions
    answered = sum(bool(q.get("answer")) for q in questions)
    st.info(f"Đã parse **{len(questions)}** câu; có đáp án cho **{answered}** câu.")

    if st.session_state.has_answer_key is False:
        choice = st.radio(
            "PDF không có answer key. Bạn muốn làm gì?",
            ["Không đáp án - vẫn tạo HTML", "Bỏ - không render HTML"], horizontal=True,
        )
    else:
        choice = "Có đáp án"

    left, right = st.columns([1, 3])
    with left:
        selected = st.selectbox("Chọn câu để review", range(len(questions)), format_func=lambda i: f"Câu {i + 1}")
        st.metric("Ảnh phát hiện", len(st.session_state.images))
        if st.session_state.errors:
            st.warning(f"Có {len(st.session_state.errors)} cảnh báo/lỗi.")
    with right:
        _review_question(selected)

    if st.session_state.errors:
        st.subheader("Báo cáo lỗi")
        st.json(st.session_state.errors)
        st.download_button(
            "Tải error_report.json", json.dumps(st.session_state.errors, ensure_ascii=False, indent=2),
            file_name="error_report.json", mime="application/json",
        )

    if choice != "Bỏ - không render HTML":
        if st.button("Render HTML offline", type="primary"):
            html = render_exam_html(questions, st.session_state.images, int(duration), st.session_state.source_name)
            safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", Path(st.session_state.source_name).stem) or "exam"
            st.download_button(
                "Tải file HTML", html, file_name=f"{safe_name}_bluebook.html", mime="text/html",
            )
            st.success("HTML đã được tạo. Mở file vừa tải bằng trình duyệt để luyện tập offline.")
