import os
import io
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


def _pdf_page_to_pil(pdf_path: str, page_index: int = 0) -> Image.Image:
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

    img  = _pdf_page_to_pil(template_path)
    draw = ImageDraw.Draw(img)
    w    = img.width

    # ── 이름 (길이에 따라 폰트 크기 자동 조절) ────────────
    name_font = _load_font_fit(
        config.NAME_FONT, english_name,
        config.NAME_FONT_SIZE, config.NAME_FONT_SIZE_MIN,
        config.NAME_MAX_WIDTH, draw,
    )
    name_y = config.NAME_Y[award_type]
    _draw_centered(draw, english_name, name_y, name_font, config.NAME_COLOR, w)

    # ── 반/레벨 이름 ───────────────────────────────────────
    class_font = _load_font(config.CLASS_FONT, config.CLASS_FONT_SIZE)
    class_y    = config.CLASS_Y[award_type]
    _draw_centered(draw, student_class, class_y, class_font, config.CLASS_COLOR, w)

    # ── 날짜 (Date 라인 위에 중앙 정렬) ───────────────────
    date_font = _load_font(config.DATE_FONT, config.DATE_FONT_SIZE)
    date_bbox = draw.textbbox((0, 0), month, font=date_font)
    date_x    = config.DATE_CENTER_X - (date_bbox[0] + date_bbox[2]) // 2
    draw.text((date_x, config.DATE_Y), month, font=date_font, fill=config.DATE_COLOR)

    # ── PDF 저장 ──────────────────────────────────────────
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    img.save(output_path, "PDF", resolution=config.DPI)
