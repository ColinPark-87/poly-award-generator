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
    1) 이미지 배경색을 샘플링해 ___ 를 덮음 (하드코딩 흰색 대신)
    2) bbox 안에 맞는 폰트 크기로 텍스트를 왼쪽 정렬, 수직 중앙 정렬
    """
    x0, y0, x1, y1 = bbox
    # 배경색 샘플링: bbox 중앙 x, bbox 상단 40px 위 지점
    sample_x = max(0, min(img.width - 1, int((x0 + x1) / 2)))
    sample_y = max(0, int(y0) - 40)
    try:
        px = img.getpixel((sample_x, sample_y))
        bg_color = tuple(px[:3]) if len(px) >= 3 else (px, px, px)
    except Exception:
        bg_color = (255, 255, 255)
    draw.rectangle([x0 - 4, y0, x1 + 4, y1], fill=bg_color)

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


def _inject_jungbal_text_pdf(
    template_path: str,
    date_text: str,
    extra_text: str | None,
) -> bytes:
    """
    정발 템플릿 PDF에 날짜/반이름 직접 삽입.

    전략: 글자마다 폰트 우선순위 결정
      1) 내장 PalaceScriptMT에 글리프 있으면 → 그대로 사용 (템플릿과 완전 동일)
      2) 없으면 (숫자, Sep/Nov/Dec 일부 대소문자) → Pinyon Script fallback

    공통 조건:
      - 색상: 템플릿 텍스트와 동일한 검정 (0,0,0)
      - 크기: 40pt (템플릿 텍스트와 동일)
      - 기준선: span origin y 정확히 사용
    """
    doc  = fitz.open(template_path)
    page = doc[0]

    bg_fill  = (231 / 255, 231 / 255, 232 / 255)  # 템플릿 배경색
    text_clr = (0.0, 0.0, 0.0)                     # 템플릿과 동일한 검정
    fontsize = 40.0

    # ── 내장 PalaceScriptMT 추출 ──────────────────────────
    palace_font = None
    for f in page.get_fonts(full=True):
        if "PalaceScript" in f[3]:
            fd = doc.extract_font(f[0])
            if fd[3]:
                palace_font = fitz.Font(fontbuffer=fd[3])
            break

    # ── Pinyon Script (숫자·누락 글자 fallback) ──────────
    pinyon_path = os.path.join(config.FONT_DIR, "PinyonScript-Regular.ttf")
    pinyon_font = fitz.Font(fontfile=pinyon_path) if os.path.exists(pinyon_path) else palace_font

    def _pick_font(ch: str) -> fitz.Font | None:
        """글자별 폰트 선택: PalaceScriptMT 우선, 없으면 Pinyon."""
        if palace_font and palace_font.has_glyph(ord(ch)):
            return palace_font
        return pinyon_font

    def _tw_append(tw: fitz.TextWriter, x: float, y: float, text: str) -> None:
        """글자마다 최적 폰트로 삽입, x를 글자 폭만큼 전진."""
        for ch in text:
            font = _pick_font(ch)
            if font:
                tw.append(fitz.Point(x, y), ch, font=font, fontsize=fontsize)
                x += font.text_length(ch, fontsize=fontsize)

    # ── span에서 ___ 포함 줄의 정확한 기준선 y · x 추출 ──
    page_h = page.rect.height
    baseline_date  = None
    baseline_extra = None
    date_x_span    = None
    extra_x_span   = None

    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        for line in b["lines"]:
            for span in line["spans"]:
                if "___" not in span["text"]:
                    continue
                oy = span["origin"][1]
                # span 내에서 ___ 시작 x를 정확히 계산
                prefix = span["text"].split("_")[0]
                prefix_w = fitz.Font(fontbuffer=doc.extract_font(
                    next(f[0] for f in page.get_fonts(full=True)
                         if "PalaceScript" in f[3]))[3]
                ).text_length(prefix, fontsize=span["size"]) if palace_font else 0
                x_start = span["origin"][0] + prefix_w

                if oy > page_h * 0.65:
                    if baseline_date is None:
                        baseline_date = oy
                        date_x_span   = x_start
                else:
                    if baseline_extra is None:
                        baseline_extra = oy
                        extra_x_span   = x_start

    # ── ___ 패턴 위치 찾기 · 배경 덮기 ───────────────────
    # x는 span 계산 우선, 없을 때만 search_for 사용
    date_x_hit  = None
    extra_x_hit = None

    for pattern in ["______", "_____", "____", "___"]:
        for h in page.search_for(pattern):
            r = fitz.Rect(h.x0 - 2, h.y0 - 1, h.x1 + 2, h.y1 + 1)
            page.draw_rect(r, color=None, fill=bg_fill)
            if h.y0 > page_h * 0.65:
                if date_x_hit is None:
                    date_x_hit = h.x0
            else:
                if extra_x_hit is None:
                    extra_x_hit = h.x0

    date_x  = date_x_span  if date_x_span  is not None else date_x_hit
    extra_x = extra_x_span if extra_x_span is not None else extra_x_hit

    # ── TextWriter로 삽입 ─────────────────────────────────
    tw = fitz.TextWriter(page.rect, color=text_clr)
    if date_x is not None and baseline_date is not None:
        _tw_append(tw, date_x, baseline_date, date_text)
    if extra_x is not None and baseline_extra is not None and extra_text:
        _tw_append(tw, extra_x, baseline_extra, extra_text)
    tw.write_text(page)

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


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

    is_jungbal = award_type in config.JUNGBAL_AWARD_TYPES

    if is_jungbal:
        # ── 정발: 내장 PalaceScriptMT로 날짜/반이름 PDF에 직접 삽입 후 래스터라이즈
        modified_bytes = _inject_jungbal_text_pdf(template_path, month, extra_text)
        _doc  = fitz.open(stream=modified_bytes, filetype="pdf")
        _pix  = _doc[0].get_pixmap(matrix=fitz.Matrix(config.DPI / 72, config.DPI / 72))
        img   = Image.frombytes("RGB", [_pix.width, _pix.height], _pix.samples)
        _doc.close()
    else:
        img = _pdf_page_to_pil(template_path, 0)

    draw = ImageDraw.Draw(img)
    w    = img.width

    # ── 반/레벨 이름 (AWARDED TO 아래 고정 Y) ─────────────
    # 정발: PalaceScriptMT와 유사한 Pinyon Script로 통일
    _class_font_file = config.JUNGBAL_SCRIPT_FONT if is_jungbal else config.CLASS_FONT
    class_font = _load_font(_class_font_file, config.CLASS_FONT_SIZE)
    class_y    = config.CLASS_Y.get(award_type, 520)
    _draw_centered(draw, student_class, class_y, class_font, config.CLASS_COLOR, w)

    # ── 학생 이름: 구분선 바로 위 (bbox 하단 정렬) ─────────
    lines     = _scan_template_lines(template_path, config.DPI, 0)
    divider_y = _find_divider_y(lines, config.DIVIDER_LINE_Y_FALLBACK.get(award_type, 870))

    _name_font_file = config.JUNGBAL_SCRIPT_FONT if is_jungbal else config.NAME_FONT
    name_font = _load_font_fit(
        _name_font_file, english_name,
        config.NAME_FONT_SIZE.get(award_type, 140), config.NAME_FONT_SIZE_MIN,
        config.NAME_MAX_WIDTH, draw,
    )
    name_bbox = draw.textbbox((0, 0), english_name, font=name_font)
    name_y    = divider_y - name_bbox[3] - config.NAME_LINE_GAP
    _draw_centered(draw, english_name, name_y, name_font, config.NAME_COLOR, w)

    if not is_jungbal:
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
