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
    x = (img_width - (bbox[2] - bbox[0])) // 2
    draw.text((x, y), text, font=font, fill=color)


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

    # ── 이름 ──────────────────────────────────────────────
    name_font = _load_font(config.NAME_FONT, config.NAME_FONT_SIZE)
    name_y    = config.NAME_Y[award_type]
    _draw_centered(draw, english_name, name_y, name_font, config.NAME_COLOR, w)

    # ── 날짜 ──────────────────────────────────────────────
    date_font = _load_font(config.DATE_FONT, config.DATE_FONT_SIZE)
    draw.text((config.DATE_X, config.DATE_Y), month, font=date_font, fill=config.DATE_COLOR)

    # ── PDF 저장 ──────────────────────────────────────────
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    img.save(output_path, "PDF", resolution=config.DPI)
