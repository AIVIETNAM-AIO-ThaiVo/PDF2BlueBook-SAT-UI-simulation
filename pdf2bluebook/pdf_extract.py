from __future__ import annotations

import base64
import html
import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import fitz
from PIL import Image
from pydantic import BaseModel, Field
from google import genai
from google.genai import types


# ---------------------------------------------------------------------------
# Gemini config
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Gemini config
# ---------------------------------------------------------------------------
GEMINI_DEFAULT_MODEL = "gemini-3-flash-preview"
GEMINI_RENDER_SCALE = 2.0
GEMINI_CROP_PADDING = 10


def _get_gemini_client(api_key: str) -> genai.Client:
    if not api_key:
        raise RuntimeError("Thiếu Gemini API key. Nhập key ở sidebar trước khi phân tích PDF.")
    return genai.Client(api_key=api_key)

_gemini_client: Optional[genai.Client] = None


class GraphBox(BaseModel):
    page: int = Field(description="Số trang thực tế, đúng theo số trang được ghi trong nhãn 'Trang N' đi kèm mỗi ảnh")
    has_graph: bool = Field(description="True nếu trang có biểu đồ/đồ thị dữ liệu (chart/graph), False nếu không")
    box_2d: Optional[list[int]] = Field(
        default=None,
        description="[ymin, xmin, ymax, xmax] normalized 0-1000. Bắt buộc có nếu has_graph=True, để null nếu has_graph=False",
    )
    label: Optional[str] = Field(default=None, description="Loại biểu đồ, ví dụ 'bar chart', 'line graph'")
    has_table: bool = Field(default=False, description="True nếu trang có bảng dữ liệu cần crop")
    table_box_2d: Optional[list[int]] = Field(
        default=None,
        description="[ymin, xmin, ymax, xmax] normalized 0-1000, bắt buộc nếu has_table=True",
    )


class PageResults(BaseModel):
    results: list[GraphBox]


GEMINI_PROMPT_TEMPLATE = """Bạn đang xem {n} trang của một đề thi SAT, mỗi ảnh được gắn nhãn "Trang N" ngay phía trước.

Với MỖI trang, xác định trang đó CÓ chứa một biểu đồ dữ liệu (data chart/graph — bar chart,
line graph, scatter plot, pie chart, histogram... có trục số và dữ liệu vẽ) hay KHÔNG.

Đồng thời, hãy xác định mọi bảng dữ liệu (table) trên trang. Bảng không phải graph.
Nếu có bảng, trả has_table=true và table_box_2d là bounding box bao trọn toàn bộ bảng.
Nếu không có bảng, trả has_table=false và table_box_2d=null.

QUAN TRỌNG - Quy tắc dưới đây chỉ dùng để quyết định has_graph; không dùng chúng để bỏ qua table:
- Bảng metadata ở đầu mỗi câu hỏi ghi "Assessment / Test / Domain / Skill / Difficulty"
  (ví dụ: SAT | Reading and Writing | Information and Ideas | Command of Evidence | Hard)
- Thanh/ô hiển thị mức độ khó (Easy/Medium/Hard) dạng các ô đen liền kề
- Bảng dữ liệu dạng text thuần (câu hỏi, đáp án, bảng số liệu không có trục biểu đồ)

Nếu trang không có graph nào đúng nghĩa, trả has_graph=false, box_2d=null.
Nếu có graph, trả has_graph=true kèm box_2d bao sát đúng vùng graph và vùng legend của graph đó luôn.
(không bao luôn tiêu đề câu hỏi hay đoạn văn bên cạnh nếu tách biệt được)

Trả kết quả (field "page") đúng theo số trang đã ghi trong nhãn "Trang N" của từng ảnh.
Trả kết quả cho TẤT CẢ {n} trang, không bỏ trang nào."""


def _detect_graphs_batch(
    page_numbers: list[int],
    page_images: list[Image.Image],
    api_key: str,
    model: str = GEMINI_DEFAULT_MODEL,
) -> PageResults:
    """Gửi 1 request duy nhất chứa nhiều ảnh trang cho Gemini, trả bbox theo từng trang."""
    client = _get_gemini_client(api_key)
    n = len(page_images)
    prompt = GEMINI_PROMPT_TEMPLATE.format(n=n)

    parts: list = [prompt]
    for page_number, img in zip(page_numbers, page_images):
        parts.append(f"Trang {page_number}:")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        parts.append(types.Part.from_bytes(data=buffer.getvalue(), mime_type="image/png"))

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=PageResults,
        temperature=0.0,
    )

    response = client.models.generate_content(model=model, contents=parts, config=config)
    return PageResults.model_validate_json(response.text)

def _crop_graphs_from_results(
    page_numbers: list[int],
    page_images: list[Image.Image],
    results: PageResults,
    padding: int = GEMINI_CROP_PADDING,
) -> dict[str, dict[str, str]]:
    """Map kết quả Gemini về đúng ảnh trang, crop và encode base64."""
    image_by_page = {pn: img for pn, img in zip(page_numbers, page_images)}
    output: dict[str, dict[str, str]] = {}

    for i, r in enumerate(results.results):
        if not r.has_graph or not r.box_2d or len(r.box_2d) != 4:
            continue
        img = image_by_page.get(r.page)
        if img is None:
            continue

        w, h = img.size
        ymin, xmin, ymax, xmax = r.box_2d  # Gemini trả theo thứ tự y trước x
        x0 = max(int(xmin / 1000 * w) - padding, 0)
        y0 = max(int(ymin / 1000 * h) - padding, 0)
        x1 = min(int(xmax / 1000 * w) + padding, w)
        y1 = min(int(ymax / 1000 * h) + padding, h)
        if x1 <= x0 or y1 <= y0:
            continue

        cropped = img.crop((x0, y0, x1, y1))
        buffer = io.BytesIO()
        cropped.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")

        image_id = f"p{r.page}_graph{i + 1}"
        output[image_id] = {
            "data": encoded,
            "mime": "image/png",
            "page": str(r.page),
            "bbox": f"{x0},{y0},{x1},{y1}",
            "source": "gemini",
            "label": r.label or "",
        }

    return output


def _crop_tables_from_results(
    page_numbers: list[int],
    page_images: list[Image.Image],
    results: PageResults,
    padding: int = GEMINI_CROP_PADDING,
) -> dict[str, dict[str, str]]:
    """Crop table regions from Gemini's normalized table bounding boxes."""
    image_by_page = {pn: img for pn, img in zip(page_numbers, page_images)}
    output: dict[str, dict[str, str]] = {}
    table_index = 0
    for r in results.results:
        if not r.has_table or not r.table_box_2d or len(r.table_box_2d) != 4:
            continue
        img = image_by_page.get(r.page)
        if img is None:
            continue
        w, h = img.size
        ymin, xmin, ymax, xmax = r.table_box_2d
        x0 = max(int(xmin / 1000 * w) - padding, 0)
        y0 = max(int(ymin / 1000 * h) - padding, 0)
        x1 = min(int(xmax / 1000 * w) + padding, w)
        y1 = min(int(ymax / 1000 * h) + padding, h)
        if x1 <= x0 or y1 <= y0:
            continue
        cropped = img.crop((x0, y0, x1, y1))
        buffer = io.BytesIO()
        cropped.save(buffer, format="PNG")
        table_index += 1
        output[f"p{r.page}_table{table_index}"] = {
            "data": base64.b64encode(buffer.getvalue()).decode("ascii"),
            "mime": "image/png",
            "page": str(r.page),
            "bbox": f"{x0},{y0},{x1},{y1}",
            "source": "gemini-table",
            "label": "table",
        }
    return output


@dataclass
class ExtractionResult:
    text: str
    images: dict[str, dict[str, str]]
    page_count: int
    errors: list[dict[str, str]]


def get_pdf_page_count(path: Path) -> int:
    """Return the total number of pages without extracting the document."""
    document = fitz.open(path)
    try:
        return len(document)
    finally:
        document.close()


def render_page_preview(path: Path, page_index: int, *, max_width: int = 240, zoom: float = 1.0) -> bytes:
    """Render one PDF page as a PNG preview without altering the source PDF."""
    document = fitz.open(path)
    try:
        page = document[page_index]
        page_width = max(float(page.rect.width), 1.0)
        scale = max(max_width / page_width * zoom, 0.1)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        return pixmap.tobytes("png")
    finally:
        document.close()


BULLET_CHARS = "•◦▪‣∙●○■□◆◇▪▫·"
BULLET_PATTERN = re.compile(rf"(?<!^)(?<!\n)[ \t]*([{re.escape(BULLET_CHARS)}])[ \t]*")
LINE_BULLET_PATTERN = re.compile(rf"(?m)^[ \t]*([{re.escape(BULLET_CHARS)}])[ \t]*")


BLANK_LENGTH = 4
BLANK_SEQUENCE_PATTERN = re.compile(r"_{3,}(?:[ \t]+_{3,})*")


def normalize_bullets(text: str) -> str:
    """Give inline PDF bullets their own line without touching answer labels."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    text = BULLET_PATTERN.sub(lambda match: f"\n{match.group(1)} ", text)
    return LINE_BULLET_PATTERN.sub(lambda match: f"{match.group(1)} ", text)


def normalize_blanks(text: str) -> str:
    """Collapse separated PDF blank rules to one fixed-width blank."""
    return BLANK_SEQUENCE_PATTERN.sub("_" * BLANK_LENGTH, text)


def _format_span(span: dict) -> str:
    """Convert reliable PDF span styling to a deliberately small, safe HTML subset."""
    text = html.escape(span.get("text", ""))
    if not text:
        return ""
    flags = int(span.get("flags", 0))
    char_flags = int(span.get("char_flags", 0))
    if char_flags & (1 << 1):
        text = f"<u>{text}</u>"
    if flags & (1 << 4):
        text = f"<b>{text}</b>"
    if flags & (1 << 1):
        text = f"<i>{text}</i>"
    return text


def _vector_blanks(page: fitz.Page) -> list[fitz.Rect]:
    """Return short horizontal vector rules that are likely answer blanks.

    SAT PDFs often draw a blank with a line instead of storing underscore
    characters in the text layer.  The limits deliberately exclude page
    rules, table borders, and most graph lines.
    """
    blanks: list[fitz.Rect] = []
    for drawing in page.get_drawings():
        rect = drawing.get("rect")
        if not rect:
            continue
        rule = fitz.Rect(rect)
        if not (14 <= rule.width <= 250 and rule.height <= 2.5):
            continue
        # A filled rectangle is commonly a UI/table decoration, not a blank.
        if drawing.get("fill") is not None:
            continue
        blanks.append(rule)
    return blanks


def _blank_placeholder(rule: fitz.Rect, line_height: float) -> str:
    """Approximate the visual width of a vector blank with readable text."""
    return "_" * BLANK_LENGTH


def _format_line_with_vector_blanks(line: dict, blanks: list[fitz.Rect]) -> str:
    """Merge nearby vector blanks into a text line in their x-coordinate order."""
    spans = line.get("spans", [])
    if not spans:
        return ""

    span_rects = [fitz.Rect(span["bbox"]) for span in spans if span.get("text")]
    if not span_rects:
        return ""
    line_top = min(rect.y0 for rect in span_rects)
    line_bottom = max(rect.y1 for rect in span_rects)
    line_height = max(line_bottom - line_top, 1.0)

    fragments: list[tuple[float, int, str]] = [
        (fitz.Rect(span["bbox"]).x0, 1, _format_span(span)) for span in spans if span.get("text")
    ]
    for rule in blanks:
        # Underlines are placed around the text baseline.  A short horizontal
        # rule must also touch a text fragment on this line to be considered a
        # blank; this avoids turning table borders into underscores.
        # A vector blank is normally drawn on the text baseline, not anywhere
        # in the vertical gap between two lines.  Keep this window tight so a
        # blank from the previous line cannot be duplicated on the next line.
        if rule.y0 < line_bottom - 2 or rule.y0 > line_bottom + 2:
            continue
        if any(rule.intersects(rect) for rect in span_rects):
            continue
        adjacent = any(
            abs(rule.x1 - rect.x0) <= 12 or abs(rule.x0 - rect.x1) <= 12 for rect in span_rects
        )
        if adjacent:
            fragments.append((rule.x0, 0, _blank_placeholder(rule, line_height)))

    fragments.sort(key=lambda fragment: (fragment[0], fragment[1]))
    return "".join(fragment[2] for fragment in fragments)


def extract_formatted_text(page: fitz.Page) -> str:
    """Extract text in reading order while retaining underline, bold, and italic spans."""
    lines: list[str] = []
    vector_blanks = _vector_blanks(page)
    for block in page.get_text("dict", sort=True).get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            lines.append(_format_line_with_vector_blanks(line, vector_blanks))
    return normalize_blanks(normalize_bullets("\n".join(lines).strip()))


def extract_pdf(
    path: Path,
    gemini_api_key: str | None = None,
    gemini_model: str = GEMINI_DEFAULT_MODEL,
    selected_page_indices: list[int] | None = None,
) -> ExtractionResult:
    document = fitz.open(path)
    pages: list[str] = []
    images: dict[str, dict[str, str]] = {}
    errors: list[dict[str, str]] = []

    pages_needing_gemini: list[int] = []
    selected_pages = (
        set(range(len(document)))
        if selected_page_indices is None
        else {index for index in selected_page_indices if 0 <= index < len(document)}
    )

    for page_index, page in enumerate(document):
        if page_index not in selected_pages:
            continue
        page_number = page_index + 1
        text = extract_formatted_text(page)

        pages.append(f"\n--- PAGE {page_number} ---\n{text}")

        found_raster = False
        for block_index, block in enumerate(page.get_text("dict").get("blocks", [])):
            if block.get("type") != 1 or not block.get("image"):
                continue
            found_raster = True
            image_id = f"p{page_index + 1}_img{block_index + 1}"
            extension = block.get("ext", "png").lower()
            mime = "image/jpeg" if extension in {"jpg", "jpeg"} else f"image/{extension}"
            images[image_id] = {
                "data": base64.b64encode(block["image"]).decode("ascii"),
                "mime": mime,
                "page": str(page_index + 1),
                "bbox": ",".join(str(round(value, 2)) for value in block.get("bbox", [])),
                "source": "raster",
            }

        # Gemini is also responsible for detecting and reading vector tables,
        # so inspect every page instead of skipping pages that contain images.
        pages_needing_gemini.append(page_index)

    # --- Batch 1 request Gemini duy nhất, chỉ chạy nếu có api_key được truyền vào ---
    if gemini_api_key and pages_needing_gemini:
        try:
            mat = fitz.Matrix(GEMINI_RENDER_SCALE, GEMINI_RENDER_SCALE)
            page_numbers = [idx + 1 for idx in pages_needing_gemini]
            page_images = []
            for idx in pages_needing_gemini:
                pix = document[idx].get_pixmap(matrix=mat)
                page_images.append(Image.open(io.BytesIO(pix.tobytes("png"))))

            results = _detect_graphs_batch(page_numbers, page_images, gemini_api_key, gemini_model)
            graph_images = _crop_graphs_from_results(page_numbers, page_images, results)
            table_images = _crop_tables_from_results(page_numbers, page_images, results)

            if graph_images or table_images:
                images.update(graph_images)
                images.update(table_images)
                errors.append({
                    "level": "info", "code": "GEMINI_VISUALS_FOUND",
                    "message": f"Gemini đã crop {len(graph_images)} graph và {len(table_images)} table trên {len(pages_needing_gemini)} trang.",
                })
            else:
                errors.append({
                    "level": "info", "code": "GEMINI_NO_VISUALS",
                    "message": f"Gemini không phát hiện graph/table trên {len(pages_needing_gemini)} trang được kiểm tra.",
                })
        except Exception as exc:
            errors.append({
                "level": "warning", "code": "GEMINI_EXTRACTION_FAILED",
                "message": f"Không thể chạy Gemini detection: {exc}",
            })
    elif not gemini_api_key and pages_needing_gemini:
        errors.append({
            "level": "info", "code": "GEMINI_SKIPPED_NO_KEY",
            "message": f"Bỏ qua Gemini detection cho {len(pages_needing_gemini)} trang vì chưa có API key.",
        })

    document.close()

    combined = "\n".join(pages).strip()
    if not combined or not any(
        page.strip().replace(f"--- PAGE {i + 1} ---", "").strip()
        for i, page in enumerate(pages)
    ):
        raise ValueError("PDF không có text layer hoặc không thể trích xuất text. MVP chưa hỗ trợ PDF scan.")

    if not images:
        errors.append({
            "level": "info", "code": "NO_IMAGES",
            "message": "Không phát hiện ảnh nhúng hoặc biểu đồ trong PDF.",
        })

    return ExtractionResult(combined, images, len(pages), errors)
