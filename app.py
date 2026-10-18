"""Local Streamlit application for turning text PDFs into offline SAT practice HTML."""

from __future__ import annotations

import json
import base64
import hashlib
import os
import re
import tempfile
from pathlib import Path

import streamlit as st

from pdf2bluebook.pdf_extract import extract_pdf, get_pdf_page_count, render_page_preview
from pdf2bluebook.gemini_parser import parse_questions
from pdf2bluebook.modern_html_renderer import render_exam_html
from pdf2bluebook.question_categories import ALL_CATEGORIES, QUESTION_CATEGORIES


st.set_page_config(page_title="PDF to BlueBook", page_icon="📘", layout="wide")


def _new_session() -> None:
    st.session_state.questions = []
    st.session_state.images = {}
    st.session_state.errors = []
    st.session_state.source_name = ""
    st.session_state.has_answer_key = None
    st.session_state.review_index = 0
    st.session_state.preview_signature = ""
    st.session_state.preview_path = ""
    st.session_state.preview_page_count = 0
    st.session_state.focus_overlay_page = None


if "questions" not in st.session_state:
    _new_session()
else:
    st.session_state.setdefault("preview_signature", "")
    st.session_state.setdefault("preview_path", "")
    st.session_state.setdefault("preview_page_count", 0)
    st.session_state.setdefault("focus_overlay_page", None)


def _save_upload(upload) -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix="pdf2bluebook_"))
    target = temp_dir / upload.name
    target.write_bytes(upload.getvalue())
    return target


@st.cache_data(show_spinner=False)
def _cached_page_preview(path: str, page_index: int, max_width: int, zoom: float) -> bytes:
    return render_page_preview(Path(path), page_index, max_width=max_width, zoom=zoom)


def _display_preview(image_bytes: bytes, *, alt: str) -> None:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    st.html(
        f'<div style="width:100%;overflow:hidden;border-radius:4px;">'
        f'<img src="data:image/png;base64,{encoded}" alt="{alt}" '
        'style="display:block;width:100%;height:auto;">'
        "</div>"
    )


def _request_page_focus(page_index: int) -> None:
    st.session_state.focus_overlay_page = page_index


def _clear_page_focus() -> None:
    st.session_state.focus_overlay_page = None


@st.dialog("Preview trang", width="large", icon=":material/center_focus_strong:", on_dismiss=_clear_page_focus)
def _show_page_focus(path: str, page_index: int) -> None:
    st.caption(f"Trang {page_index + 1}")
    _display_preview(
        _cached_page_preview(path, page_index, max_width=1400, zoom=1.0),
        alt=f"Preview lớn trang {page_index + 1}",
    )


def _set_page_selection(selected: bool) -> None:
    for page_index in range(st.session_state.preview_page_count):
        st.session_state[f"page-selected-{page_index}"] = selected


def _set_review_index(index: int) -> None:
    st.session_state.review_index = index
    st.session_state.review_selector = index


def _sync_subcategory_filter() -> None:
    categories = st.session_state.get("filter_categories", list(ALL_CATEGORIES))
    if isinstance(categories, str):
        categories = [categories]
    categories = [category for category in categories if category in QUESTION_CATEGORIES]
    st.session_state.filter_subcategories = [
        subcategory
        for category in categories
        for subcategory in QUESTION_CATEGORIES[category]
    ]


def _review_question(index: int, review_indices: list[int] | None = None) -> None:
    question = st.session_state.questions[index]
    review_indices = review_indices or list(range(len(st.session_state.questions)))
    position = review_indices.index(index)
    st.subheader(f"Review câu {index + 1}")
    with st.container(horizontal=True, horizontal_alignment="distribute"):
        st.button(
            "Câu trước", disabled=position == 0, key=f"previous-review-{index}",
            on_click=_set_review_index, args=(review_indices[position - 1],),
        )
        st.caption(f"Câu {position + 1} / {len(review_indices)} câu đã lọc")
        st.button(
            "Câu kế tiếp", disabled=position == len(review_indices) - 1,
            key=f"next-review-{index}", on_click=_set_review_index, args=(review_indices[position + 1],),
        )

    image_options = ["(Không có ảnh)", *st.session_state.images.keys()]
    existing_image = question.get("image_id") or "(Không có ảnh)"
    image_id = st.selectbox(
        "Ảnh đặt sau passage, trước câu hỏi", image_options,
        index=image_options.index(existing_image) if existing_image in image_options else 0,
        key=f"image-review-{index}",
    )
    if image_id != "(Không có ảnh)" and image_id in st.session_state.images:
        metadata = st.session_state.images[image_id]
        st.image(
            base64.b64decode(metadata["data"]),
            caption=f"Preview: {image_id} (trang {metadata.get('page', '?')})",
            width="stretch",
        )
    else:
        st.caption("Chưa chọn ảnh cho câu hỏi này.")

    with st.form(f"review-{index}"):
        passage = st.text_area("Passage", value=question.get("passage", ""), height=180)
        text = st.text_area("Câu hỏi", value=question.get("question", ""), height=100)
        category_options = list(ALL_CATEGORIES)
        current_category = question.get("category") if question.get("category") in category_options else category_options[0]
        category = st.selectbox(
            "Category", category_options,
            index=category_options.index(current_category),
        )
        subcategory_options = list(QUESTION_CATEGORIES[category])
        current_subcategory = question.get("subcategory") if question.get("subcategory") in subcategory_options else subcategory_options[0]
        subcategory = st.selectbox(
            "Subcategory", subcategory_options,
            index=subcategory_options.index(current_subcategory),
        )
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
        if st.form_submit_button("Lưu thay đổi", type="primary"):
            question.update({
                "passage": passage.strip(), "question": text.strip(), "choices": choices,
                "answer": None if answer == "(Không có đáp án)" else answer,
                "category": category, "subcategory": subcategory,
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
selected_page_indices: list[int] = []
if upload:
    upload_bytes = upload.getvalue()
    upload_signature = hashlib.sha256(upload_bytes).hexdigest()
    if upload_signature != st.session_state.preview_signature:
        preview_path = _save_upload(upload)
        st.session_state.preview_signature = upload_signature
        st.session_state.preview_path = str(preview_path)
        st.session_state.preview_page_count = get_pdf_page_count(preview_path)
        st.session_state.focus_overlay_page = None
        for page_index in range(st.session_state.preview_page_count):
            st.session_state[f"page-selected-{page_index}"] = True

    st.subheader("Chọn trang cần xử lý")
    st.caption("Thumbnail chỉ dùng để xem nhanh. Pipeline sẽ chỉ chạy trên các trang được chọn.")
    controls_left, controls_right = st.columns(2)
    with controls_left:
        st.button("Chọn tất cả", on_click=_set_page_selection, args=(True,), key="select-all-pages")
    with controls_right:
        st.button("Bỏ chọn tất cả", on_click=_set_page_selection, args=(False,), key="deselect-all-pages")

    st.markdown(
        "<style>div[data-testid='stVerticalBlockBorderWrapper'] { border: 2px solid #111827 !important; border-radius: 8px; padding: 8px; }</style>",
        unsafe_allow_html=True,
    )
    grid_columns = st.columns(4)
    for page_index in range(st.session_state.preview_page_count):
        with grid_columns[page_index % 4]:
            with st.container(border=True):
                label_col, check_col = st.columns([4, 1])
                with label_col:
                    st.caption(f"Trang {page_index + 1}")
                with check_col:
                    st.checkbox(
                        "Đã chọn",
                        key=f"page-selected-{page_index}",
                        label_visibility="collapsed",
                    )
                _display_preview(
                    _cached_page_preview(st.session_state.preview_path, page_index, max_width=240, zoom=1.0),
                    alt=f"Preview trang {page_index + 1}",
                )
                _, focus_col = st.columns([3, 1])
                with focus_col:
                    st.button(
                        ":material/center_focus_strong:",
                        help="Mở trang này ở preview lớn",
                        key=f"focus-page-{page_index}",
                        on_click=_request_page_focus,
                        args=(page_index,),
                    )

    selected_page_indices = [
        page_index
        for page_index in range(st.session_state.preview_page_count)
        if st.session_state.get(f"page-selected-{page_index}", False)
    ]
    st.info(f"Đã chọn **{len(selected_page_indices)} / {st.session_state.preview_page_count}** trang.")
    overlay_page = st.session_state.get("focus_overlay_page")
    if overlay_page is not None and 0 <= overlay_page < st.session_state.preview_page_count:
        _show_page_focus(st.session_state.preview_path, overlay_page)

if upload and st.session_state.preview_path and st.button("Phân tích các trang đã chọn", type="primary", disabled=not selected_page_indices):
    if not api_key:
        st.error("Hãy nhập Gemini API key ở thanh bên trước khi bắt đầu xử lý.")
        st.stop()
    with st.status("Đang xử lý PDF...", expanded=True) as status:
        try:
            pdf_path = Path(st.session_state.preview_path)
            result = extract_pdf(
                pdf_path,
                gemini_api_key=api_key,
                gemini_model=model,
                selected_page_indices=selected_page_indices,
            )
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
            st.session_state.review_index = 0
            st.session_state.images = result.images
            st.session_state.errors = [*result.errors, *parsed.errors]
            st.session_state.source_name = upload.name
            st.session_state.has_answer_key = parsed.has_answer_key
            st.session_state.pop("filter_categories", None)
            st.session_state.pop("filter_subcategories", None)
            status.update(label="Đã sẵn sàng để review.", state="complete")
        except Exception as exc:
            status.update(label="Không thể xử lý PDF.", state="error")
            st.error(str(exc))

if st.session_state.questions:
    st.divider()
    questions = st.session_state.questions
    answered = sum(bool(q.get("answer")) for q in questions)
    st.info(f"Đã parse **{len(questions)}** câu; có đáp án cho **{answered}** câu.")

    st.subheader("Chọn câu để render")
    st.caption("Mặc định chọn tất cả. Bộ lọc này chỉ áp dụng cho file HTML xuất ra; phần review vẫn hiển thị toàn bộ câu.")
    filter_left, filter_right = st.columns(2)
    with filter_left:
        selected_categories = st.multiselect(
            "Category",
            options=list(ALL_CATEGORIES),
            default=list(ALL_CATEGORIES),
            key="filter_categories",
            on_change=_sync_subcategory_filter,
        )
    available_subcategories = [
        subcategory
        for category in selected_categories
        for subcategory in QUESTION_CATEGORIES[category]
    ]
    with filter_right:
        selected_subcategories = st.multiselect(
            "Subcategory",
            options=available_subcategories,
            default=(available_subcategories if "filter_subcategories" not in st.session_state else None),
            key="filter_subcategories",
        )
    filtered_questions = [
        question for question in questions
        if question.get("category") in selected_categories
        and question.get("subcategory") in selected_subcategories
    ]
    filtered_indices = [
        index for index, question in enumerate(questions)
        if question.get("category") in selected_categories
        and question.get("subcategory") in selected_subcategories
    ]
    if filtered_questions:
        st.success(f"Sẽ render **{len(filtered_questions)} / {len(questions)}** câu.")
    else:
        st.warning("Bộ lọc hiện không chọn câu nào. Hãy chọn ít nhất một category và subcategory.")

    if st.session_state.has_answer_key is False:
        choice = st.radio(
            "PDF không có answer key. Bạn muốn làm gì?",
            ["Không đáp án - vẫn tạo HTML", "Bỏ - không render HTML"], horizontal=True,
        )
    else:
        choice = "Có đáp án"

    left, right = st.columns([1, 3])
    with left:
        if filtered_indices:
            current_review = st.session_state.get("review_index", filtered_indices[0])
            if current_review not in filtered_indices:
                current_review = filtered_indices[0]
                st.session_state.review_selector = current_review
                st.session_state.review_index = current_review
            selected = st.selectbox(
                "Chọn câu để review", filtered_indices,
                index=filtered_indices.index(current_review),
                format_func=lambda i: f"Câu {i + 1}", key="review_selector",
            )
            st.session_state.review_index = selected
        else:
            selected = None
            st.info("Không có câu nào trong bộ lọc để review.")
        st.metric("Ảnh phát hiện", len(st.session_state.images))
        if st.session_state.errors:
            st.warning(f"Có {len(st.session_state.errors)} cảnh báo/lỗi.")
    with right:
        if selected is not None:
            _review_question(selected, filtered_indices)

    if st.session_state.errors:
        st.subheader("Báo cáo lỗi")
        st.json(st.session_state.errors)
        st.download_button(
            "Tải error_report.json", json.dumps(st.session_state.errors, ensure_ascii=False, indent=2),
            file_name="error_report.json", mime="application/json",
        )

    if choice != "Bỏ - không render HTML":
        if st.button("Render HTML offline", type="primary", disabled=not filtered_questions):
            html = render_exam_html(filtered_questions, st.session_state.images, int(duration), st.session_state.source_name)
            safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", Path(st.session_state.source_name).stem) or "exam"
            st.download_button(
                "Tải file HTML", html, file_name=f"{safe_name}_bluebook.html", mime="text/html",
            )
            st.success("HTML đã được tạo. Mở file vừa tải bằng trình duyệt để luyện tập offline.")
