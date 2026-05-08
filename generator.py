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
def _scan_jungbal_placeholders(pdf_path: str, dpi: int) -> dict:
    """
    정발 템플릿에서 ___ 자리표시자 bbox를 자동 감지 (캐시됨).
    Returns: {'date': (x0,y0,x1,y1), 'extra': (x0,y0,x1,y1) or None}
    모두 @dpi 기준 픽셀 좌표.
    """
    sc = dpi / 72.0
    doc = fitz.open(pdf_path)
    page = doc[0]
    result = {"date": None, "extra": None}

    # 긴 순서로 검색해 가장 긴 ___ 패턴을 먼저 잡음
    for pattern in ["______", "_____", "____", "___"]:
        hits = page.search_for(pattern)
        for h in hits:
            y0_img = h.y0 * sc
            bbox = (h.x0 * sc, h.y0 * sc, h.x1 * sc, h.y1 * sc)
            if y0_img > 1050:          # 하단 = 날짜 영역
                if result["date"] is None:
                    result["date"] = bbox
            else:                       # 상단 = 반/레벨 이름 영역
                if result["extra"] is None:
                    result["extra"] = bbox

    doc.close()
    return result


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


def _draw_on_placeholder(
    draw: ImageDraw.ImageDraw,
    img,
    text: str,
    bbox: tuple,
    font_file: str,
    color: tuple,
    max_font_size: int = 52,
) -> None:
    """
    자리표시자(_____) 위에 텍스트를 그린다.
    1) 흰색 사각형으로 ___ 를 덮음
    2) bbox 안에 맞는 폰트 크기로 텍스트를 왼쪽 정렬, 수직 중앙 정렬
    """
    x0, y0, x1, y1 = bbox
    # 흰색으로 덮기 (양옆 약간 여유)
    draw.rectangle([x0 - 4, y0, x1 + 4, y1], fill=(255, 255, 255))

    ph_w = x1 - x0
    ph_h = y1 - y0

    # 폰트 크기 자동 조절
    size = max_font_size
    while size >= 24:
        font = _load_font(font_file, size)
        tb = draw.textbbox((0, 0), text, font=font)
        if (tb[2] - tb[0]) <= ph_w:
            break
        size -= 3
    else:
        font = _load_font(font_file, 24)

    tb = draw.textbbox((0, 0), text, font=font)
    text_h = tb[3] - tb[1]
    text_y = y0 + (ph_h - text_h) // 2 - tb[1]
    draw.text((x0, text_y), text, font=font, fill=color)


def build_certificate(
    award_type:        str,
    english_name:      str,
    student_class:     str,
    month:             str,
    output_path:       str,
    template_override: str | None = None,
    extra_text:        str | None = None,   # 정발: 반 이름 or 레벨 이름
) -> None:
    """
    상장 PDF 생성.
    award_type: 'perfect_score' | 'honor_roll' | 'best_writer' |
                'achievement_certificate' | 'monthly_test_winner' | 'level_test_winner'
    extra_text: 정발 monthly/level winner의 "highest score in ___" 에 들어갈 텍스트
    """
    template_path = template_override or config.TEMPLATES.get(award_type)
    if not template_path or not os.path.exists(template_path):
        raise FileNotFoundError(f"템플릿 없음: {template_path}")

    img  = _pdf_page_to_pil(template_path, 0)
    draw = ImageDraw.Draw(img)
    w    = img.width

    is_jungbal = award_type in config.JUNGBAL_AWARD_TYPES

    # ── 반/레벨 이름 (AWARDED TO 아래 고정 Y) ─────────────
    class_font = _load_font(config.CLASS_FONT, config.CLASS_FONT_SIZE)
    class_y    = config.CLASS_Y.get(award_type, 520)
    _draw_centered(draw, student_class, class_y, class_font, config.CLASS_COLOR, w)

    # ── 학생 이름: 구분선 바로 위 (bbox 하단 정렬) ─────────
    lines     = _scan_template_lines(template_path, config.DPI, 0)
    divider_y = _find_divider_y(lines, config.DIVIDER_LINE_Y_FALLBACK.get(award_type, 870))

    name_font = _load_font_fit(
        config.NAME_FONT, english_name,
        config.NAME_FONT_SIZE.get(award_type, 140), config.NAME_FONT_SIZE_MIN,
        config.NAME_MAX_WIDTH, draw,
    )
    name_bbox = draw.textbbox((0, 0), english_name, font=name_font)
    name_y    = divider_y - name_bbox[3] - config.NAME_LINE_GAP
    _draw_centered(draw, english_name, name_y, name_font, config.NAME_COLOR, w)

    if is_jungbal:
        # ── 정발: 자리표시자(_____) 기반으로 날짜 및 반/레벨 이름 삽입 ──
        placeholders = _scan_jungbal_placeholders(template_path, config.DPI)

        # 날짜 (_____  아래쪽)
        date_bbox = placeholders["date"] or config.JUNGBAL_DATE_BBOX_FALLBACK
        _draw_on_placeholder(
            draw, img, month, date_bbox,
            config.DATE_FONT, config.DATE_COLOR,
            max_font_size=config.JUNGBAL_PLACEHOLDER_FONT_SIZE,
        )

        # 반/레벨 이름 (monthly/level winner 전용, 위쪽 _____)
        if extra_text:
            extra_bbox = placeholders["extra"] or config.JUNGBAL_EXTRA_BBOX_FALLBACK
            _draw_on_placeholder(
                draw, img, extra_text, extra_bbox,
                config.CLASS_FONT, config.CLASS_COLOR,
                max_font_size=config.JUNGBAL_PLACEHOLDER_FONT_SIZE,
            )

    else:
        # ── 기존 캠퍼스: 선 기반 날짜 배치 ───────────────────
        date_line_y = _find_date_line_y(lines, config.DATE_LINE_Y_FALLBACK)
        date_font   = _load_font(config.DATE_FONT, config.DATE_FONT_SIZE)
        date_bbox_t = draw.textbbox((0, 0), month, font=date_font)
        date_y      = date_line_y - date_bbox_t[3] - config.DATE_LINE_GAP
        date_x      = config.DATE_CENTER_X - (date_bbox_t[0] + date_bbox_t[2]) // 2
        draw.text((date_x, date_y), month, font=date_font, fill=config.DATE_COLOR)

    # ── PDF 저장 ──────────────────────────────────────────
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    img.save(output_path, "PDF", resolution=config.DPI)
