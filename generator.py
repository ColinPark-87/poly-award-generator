import os
import io
import functools
import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont
import config


def _load_font(filename: str, size: int) -> ImageFont.FreeTypeFont:
    path = os.path.join(config.FONT_DIR, filename)
    if os.path.exists(path):
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _draw_centered(draw: ImageDraw.ImageDraw, text: str, y: int,
                   font: ImageFont.FreeTypeFont, color: tuple, img_width: int) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    # bbox[0]이 0이 아닐 때(script 폰트 등)도 정확히 시각적 중앙 정렬
    x = (img_width - bbox[0] - bbox[2]) // 2
    draw.text((x, y), text, font=font, fill=color)


def _load_font_fit(filename: str, text: str, max_size: int, min_size: int,
                   max_width: int, draw: ImageDraw.ImageDraw) -> ImageFont.FreeTypeFont:
    """이름 길이에 맞게 폰트 크기를 자동 조절."""
    size = max_size
    while size >= min_size:
        font = _load_font(filename, size)
        bbox = draw.textbbox((0, 0), text, font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            return font
        size -= 5
    return _load_font(filename, min_size)


@functools.lru_cache(maxsize=None)
def _scan_template_lines(pdf_path: str, dpi: int, page_index: int = 0) -> tuple:
    """
    템플릿 PDF에서 수평선 목록을 추출한다 (lru_cache로 한 번만 실행).
    반환: ((y, width), ...) 형태의 tuple (y 오름차순)
    """
    doc  = fitz.open(pdf_path)
    page = doc[page_index]
    sc   = dpi / 72.0
    rows = []
    for p in page.get_drawings():
        for item in p.get("items", []):
            if item[0] == "l":                        # 직선
                a, b = item[1], item[2]
                if abs(a.y - b.y) < 0.5:             # 수평선
                    rows.append((round(a.y * sc), abs(b.x - a.x) * sc))
            elif item[0] == "re":                     # 얇은 직사각형
                rect = item[1]
                if rect.height * sc < 5 and rect.width * sc > 100:
                    rows.append((round(rect.y0 * sc), rect.width * sc))
    doc.close()
    return tuple(sorted(rows, key=lambda r: r[0]))


def _find_divider_y(lines: tuple, fallback: int) -> int:
    """y 500-1050 범위에서 가장 긴 수평선 = 이름/텍스트 구분선."""
    mid = [l for l in lines if 500 < l[0] < 1050]
    return max(mid, key=lambda l: l[1])[0] if mid else fallback


def _find_date_line_y(lines: tuple, fallback: int) -> int:
    """y 1100-1420 범위의 선 중 가장 위 = Date 밑줄."""
    bot = [l for l in lines if 1100 < l[0] < 1420]
    return min(bot, key=lambda l: l[0])[0] if bot else fallback


def pdf_to_preview_png(pdf_bytes: bytes, preview_width: int = 700) -> bytes:
    """PDF bytes → PNG bytes (미리보기용)."""
    doc  = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]
    scale = preview_width / page.rect.width
    mat  = fitz.Matrix(scale, scale)
    pix  = page.get_pixmap(matrix=mat)
    png  = pix.tobytes("png")
    doc.close()
    return png


def _pdf_page_to_pil(pdf_path: str, page_index: int = 0) -> Image.Image:  # noqa: keep
    doc  = fitz.open(pdf_path)
    page = doc[page_index]
    mat  = fitz.Matrix(config.DPI / 72, config.DPI / 72)
    pix  = page.get_pixmap(matrix=mat)
    img  = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    doc.close()
    return img


def build_certificate(
    award_type:        str,
    english_name:      str,
    student_class:     str,
    month:             str,
    output_path:       str,
    template_override: str | None = None,
) -> None:
    """
    상장 PDF 생성.
    award_type: 'perfect_score' | 'honor_roll' | 'best_writer'
    """
    template_path = template_override or config.TEMPLATES[award_type]
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"템플릿 없음: {template_path}")

    img  = _pdf_page_to_pil(template_path, 0)
    draw = ImageDraw.Draw(img)
    w    = img.width

    # ── 선 위치 자동 감지 (캐시됨) ────────────────────────
    lines       = _scan_template_lines(template_path, config.DPI, 0)
    divider_y   = _find_divider_y(lines, config.DIVIDER_LINE_Y_FALLBACK[award_type])
    date_line_y = _find_date_line_y(lines, config.DATE_LINE_Y_FALLBACK)

    # ── 반/레벨 이름 (AWARDED TO 아래 고정 Y) ─────────────
    class_font = _load_font(config.CLASS_FONT, config.CLASS_FONT_SIZE)
    class_y    = config.CLASS_Y[award_type]
    _draw_centered(draw, student_class, class_y, class_font, config.CLASS_COLOR, w)

    # ── 학생 이름: 구분선 바로 위 (bbox 하단 정렬) ─────────
    # 어떤 대소문자 조합이 와도 텍스트 하단이 항상 선 위 NAME_LINE_GAP px
    name_font = _load_font_fit(
        config.NAME_FONT, english_name,
        config.NAME_FONT_SIZE[award_type], config.NAME_FONT_SIZE_MIN,
        config.NAME_MAX_WIDTH, draw,
    )
    name_bbox = draw.textbbox((0, 0), english_name, font=name_font)
    name_y    = divider_y - name_bbox[3] - config.NAME_LINE_GAP
    _draw_centered(draw, english_name, name_y, name_font, config.NAME_COLOR, w)

    # ── 날짜: Date 밑줄 바로 위 (bbox 하단 정렬) ──────────
    # January~December 어떤 월이 와도 텍스트 하단이 항상 밑줄 위 DATE_LINE_GAP px
    date_font = _load_font(config.DATE_FONT, config.DATE_FONT_SIZE)
    date_bbox = draw.textbbox((0, 0), month, font=date_font)
    date_y    = date_line_y - date_bbox[3] - config.DATE_LINE_GAP
    date_x    = config.DATE_CENTER_X - (date_bbox[0] + date_bbox[2]) // 2
    draw.text((date_x, date_y), month, font=date_font, fill=config.DATE_COLOR)

    # ── PDF 저장 ──────────────────────────────────────────
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    img.save(output_path, "PDF", resolution=config.DPI)
