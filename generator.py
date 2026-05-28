from __future__ import annotations

import os
import io
import json
import functools
import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont
import config

# 유성 사전 계산 레이아웃 (build_yuseong_layout.py 로 생성)
# 없으면 빈 dict → _render_yuseong 내부에서 동적 계산으로 폴백
def _load_yuseong_layout() -> dict:
    path = os.path.join(config.BASE_DIR, "yuseong_layout.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

_YUSEONG_LAYOUT: dict = _load_yuseong_layout()


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


def _pdf_page_to_pil(pdf_path: str, page_index: int = 0, dpi: int | None = None) -> Image.Image:  # noqa: keep
    doc  = fitz.open(pdf_path)
    page = doc[page_index]
    _dpi = dpi or config.DPI
    mat  = fitz.Matrix(_dpi / 72, _dpi / 72)
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

    전략: GreatVibes 단일 폰트로 통일
      - PalaceScriptMT와 획 굵기·스타일 가장 유사한 무료 전체 폰트
      - 글자/숫자 혼용 없이 단일 폰트로 시각적 일관성 확보
      - extra_text: 오른쪽 여백(x=678pt) 초과 시 폰트 크기 자동 축소

    공통 조건:
      - 색상: 템플릿 텍스트와 동일한 검정 (0,0,0)
      - 크기: 40pt 기준, extra_text는 오버플로우 시 축소
      - 기준선: span origin y 정확히 사용
    """
    doc  = fitz.open(template_path)
    page = doc[0]

    bg_fill  = (231 / 255, 231 / 255, 232 / 255)  # 템플릿 배경색
    text_clr = (0.0, 0.0, 0.0)                     # 템플릿과 동일한 검정
    fontsize = 40.0
    RIGHT_MARGIN = 678.0  # POLY Jeongbal 열 시작 x (오버플로우 경계)

    # ── GreatVibes 로드 (PalaceScriptMT와 획 굵기 가장 유사) ──
    gv_path = os.path.join(config.FONT_DIR, "GreatVibes-Regular.ttf")
    if not os.path.exists(gv_path):
        raise FileNotFoundError(f"GreatVibes 폰트 없음: {gv_path}")
    gv_font = fitz.Font(fontfile=gv_path)

    def _text_width(text: str, fs: float) -> float:
        return sum(gv_font.text_length(ch, fontsize=fs) for ch in text)

    def _tw_append(tw: fitz.TextWriter, x: float, y: float,
                   text: str, fs: float) -> None:
        for ch in text:
            tw.append(fitz.Point(x, y), ch, font=gv_font, fontsize=fs)
            x += gv_font.text_length(ch, fontsize=fs)

    # ── span에서 ___ 포함 줄의 정확한 기준선 y · x 추출 ──
    page_h = page.rect.height
    baseline_date  = None
    baseline_extra = None
    date_x_span    = None
    extra_x_span   = None

    # PalaceScriptMT로 prefix 폭 계산 (span origin + prefix width = blank 시작 x)
    palace_font_calc = None
    for f in page.get_fonts(full=True):
        if "PalaceScript" in f[3]:
            fd = doc.extract_font(f[0])
            if fd[3]:
                palace_font_calc = fitz.Font(fontbuffer=fd[3])
            break

    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        for line in b["lines"]:
            for span in line["spans"]:
                if "___" not in span["text"]:
                    continue
                oy = span["origin"][1]
                prefix = span["text"].split("_")[0]
                prefix_w = (palace_font_calc.text_length(prefix, fontsize=span["size"])
                            if palace_font_calc else 0)
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
        _tw_append(tw, date_x, baseline_date, date_text, fontsize)

    if extra_x is not None and baseline_extra is not None and extra_text:
        # 오른쪽 여백 초과 시 폰트 크기 자동 축소
        avail_w = RIGHT_MARGIN - extra_x
        fs = fontsize
        while fs >= 20.0 and _text_width(extra_text, fs) > avail_w:
            fs -= 1.0
        _tw_append(tw, extra_x, baseline_extra, extra_text, fs)

    tw.write_text(page)

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@functools.lru_cache(maxsize=None)
def _scan_yuseong_placeholders(pdf_path: str, dpi: int) -> dict:
    """
    유성 템플릿에서 placeholder bbox + 가이드선 위치 감지 (캐시됨).
    반환: {'name', 'month', 'date', 'lines', 'name_fs', 'body_fs'}
    모두 @dpi 기준 픽셀 좌표.
    """
    sc = dpi / 72.0
    doc = fitz.open(pdf_path)
    page = doc[0]
    page_h = page.rect.height

    result = {
        "name":          None,
        "month":         None,
        "month_span":    None,   # full span bbox @dpi px (includes "test."/"Test.")
        "month_suffix":  None,   # text after underscores in span, e.g. "test." / "Test."
        "date":          None,
        "date_line":     None,   # (x0, y, x1) of narrow vector date underline if found
        "lines":         [],
        "name_fs":       48.0,
        "body_fs":       20.0,
    }

    # ── 언더스코어 패턴 전체 수집 (union) ───────────────────────
    # 모든 패턴 hit을 같은 y줄에서 union → 연속 언더스코어 전체 범위 확보
    all_hits = {}   # y_key → [x0, y0, x1, y1] pt (union)
    for pattern in ["______", "_____", "____", "___", "__"]:
        for h in page.search_for(pattern):
            y_key = round(h.y0, 1)
            if y_key not in all_hits:
                all_hits[y_key] = [h.x0, h.y0, h.x1, h.y1]
            else:
                all_hits[y_key][0] = min(all_hits[y_key][0], h.x0)
                all_hits[y_key][2] = max(all_hits[y_key][2], h.x1)

    # y 기준 정렬
    sorted_hits = sorted(all_hits.values(), key=lambda h: h[1])

    # ── 텍스트 span 분석 ─────────────────────────────────────
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        for line_obj in b["lines"]:
            for span in line_obj["spans"]:
                text = span["text"]
                bbox = span["bbox"]
                y_mid = (bbox[1] + bbox[3]) / 2

                # 이름 placeholder: 순수 언더스코어, 페이지 상단 70% 내
                if text.strip() and text.strip().replace("_", "") == "":
                    if y_mid < page_h * 0.7 and result["name"] is None:
                        result["name"] = tuple(v * sc for v in bbox)
                        result["name_fs"] = span["size"]

                # 날짜 – PS: 공백 + ", 2026"
                elif ", 2026" in text:
                    result["date"] = tuple(v * sc for v in bbox)
                    result["body_fs"] = span["size"]

                # 날짜 – HR: 순수 언더스코어 + 마침표 (e.g. "___.")
                elif (text.strip() and "___" in text
                      and text.strip().replace("_", "").replace(".", "").strip() == ""
                      and y_mid > page_h * 0.6):
                    result["date"] = tuple(v * sc for v in bbox)
                    result["body_fs"] = span["size"]

                # 날짜 – SR: "Presented in ___"
                elif "Presented in" in text and "___" in text:
                    result["date"] = tuple(v * sc for v in bbox)
                    result["body_fs"] = span["size"]

                # 월 placeholder: "___" 포함 + 다른 텍스트 존재 + name 이후 y
                elif ("___" in text and text.strip()
                      and text.strip().replace("_", "").strip() != ""):
                    if result["name"] is not None:
                        name_y1 = result["name"][3] / sc     # 픽셀 → pt
                        if y_mid > name_y1 and y_mid < page_h * 0.75:
                            # 해당 span 내 언더스코어 위치 찾기
                            for hx0, hy0, hx1, hy1 in sorted_hits:
                                if abs(hy0 - bbox[1]) < 3:
                                    result["month"] = tuple(
                                        v * sc for v in (hx0, hy0, hx1, hy1)
                                    )
                                    # 전체 span bbox 저장 (지우기 범위: "test."/"Test." 포함)
                                    result["month_span"] = tuple(v * sc for v in bbox)
                                    # 언더스코어 뒤의 suffix 추출 (e.g. "test." / "Test.")
                                    suffix = text.split("_")[-1].strip()
                                    result["month_suffix"] = suffix
                                    break

    # ── 가이드선 수집 ─────────────────────────────────────────
    for drawing in page.get_drawings():
        for item in drawing.get("items", []):
            if item[0] == "l":
                a, b2 = item[1], item[2]
                if abs(a.y - b2.y) < 1.0:
                    result["lines"].append((
                        a.y * sc,
                        min(a.x, b2.x) * sc,
                        max(a.x, b2.x) * sc,
                    ))

    # ── 날짜 벡터 언더라인 감지 (PS 전용: 좌측 좁은 선) ─────────
    # PS 템플릿의 날짜 span은 1215px 너비로 잘못 인식됨.
    # 실제 날짜 필드는 좌측 좁은 벡터 선(~326px) 위에 위치.
    page_h_px = page.rect.height * sc
    page_w_px = page.rect.width * sc
    date_guide = [
        (ly, lx0, lx1)
        for (ly, lx0, lx1) in result["lines"]
        if ly > page_h_px * 0.65    # 페이지 하단 35% 구간
        and lx0 < page_w_px * 0.4  # 좌측(서명선 제외)
        and (lx1 - lx0) > 80       # 최소 너비
    ]
    if date_guide:
        dl = min(date_guide, key=lambda l: l[0])   # 가장 위쪽 선
        result["date_line"] = (dl[1], dl[0], dl[2])  # (x0, y, x1)

    doc.close()
    return result


def _inject_bundang_text_pdf(
    template_path: str,
    award_type: str,
    english_name: str,
    student_class: str,
    month: str,
) -> bytes:
    """
    분당엠폴리 상장: 텍스트를 PDF에 벡터로 직접 써넣어 선명도 확보.
    placeholder 밑줄/이름선은 흰 사각형으로 덮어 지우고(가상의 선),
    이름·반·월을 NanumGothic 벡터 텍스트로 배치. 래스터화 없음.
    """
    month_name = month.rsplit(" ", 1)[0]
    year = month.rsplit(" ", 1)[1] if " " in month else "2026"

    doc  = fitz.open(template_path)
    page = doc[0]
    pw, ph_h = page.rect.width, page.rect.height
    WHITE = (1, 1, 1)

    nf_b = fitz.Font(fontfile=os.path.join(config.FONT_DIR, config.BUNDANG_KR_FONT_BOLD))
    nf_r = fitz.Font(fontfile=os.path.join(config.FONT_DIR, config.BUNDANG_KR_FONT))
    tw   = fitz.TextWriter(page.rect, color=(0, 0, 0))

    def _cover(x0, y0, x1, y1, pad=1.5):
        page.draw_rect(fitz.Rect(x0 - pad, y0 - pad, x1 + pad, y1 + pad),
                       color=None, fill=WHITE)

    def _fit(font, text, max_w, start, minsz=8.0):
        s = start
        while s > minsz and font.text_length(text, fontsize=s) > max_w:
            s -= 0.5
        return s

    def _centered(font, text, cx0, cx1, baseline_y, size):
        w = font.text_length(text, fontsize=size)
        tw.append(fitz.Point(cx0 + ((cx1 - cx0) - w) / 2, baseline_y),
                  text, font=font, fontsize=size)

    spans = [s for b in page.get_text("dict")["blocks"] if b["type"] == 0
             for l in b["lines"] for s in l["spans"]]

    def _us_hit(y_pt):
        for pat in ("______", "_____", "____", "___"):
            for h in page.search_for(pat):
                if abs(h.y0 - y_pt) < 6:
                    return h
        return None

    if award_type == "certificate_of_achievement":
        # 이름선(굵은 가로선) 감지 → 덮고 그 위에 "반 영문이름"
        nl = None
        for dr in page.get_drawings():
            for it in dr.get("items", []):
                if it[0] == "l":
                    a, b = it[1], it[2]
                    if abs(a.y - b.y) < 1.0 and ph_h * 0.45 < a.y < ph_h * 0.80:
                        nl = (min(a.x, b.x), max(a.x, b.x), a.y)
        if nl:
            lx0, lx1, ly = nl
            # 원본처럼 이름선은 유지하고 그 위에 이름 배치 (선 지우지 않음)
            name = f"{student_class} {english_name}".strip()
            sz = _fit(nf_b, name, (lx1 - lx0) * 1.05, 30.0)
            _centered(nf_b, name, lx0, lx1, ly - 8, sz)
        # 제목 월: "POLY ______"
        for s in spans:
            if "_" in s["text"] and "POLY" in s["text"] and s["bbox"][1] < ph_h * 0.4:
                h = _us_hit(s["bbox"][1])
                if h is not None:
                    _cover(h.x0, s["bbox"][1], s["bbox"][2], s["bbox"][3], pad=1)
                    tw.append(fitz.Point(h.x0 + 4, s["origin"][1]),
                              month_name, font=nf_b, fontsize=s["size"])
                break
    else:  # grammar_certification
        # 이름 placeholder(순수 언더스코어, 상단 75%) → 덮고 아래로 윗줄+이름
        nph = None
        for s in spans:
            t = s["text"].strip()
            if t and t.replace("_", "") == "" and (s["bbox"][1] + s["bbox"][3]) / 2 < ph_h * 0.75:
                if nph is None or s["bbox"][1] < nph[1]:
                    nph = s["bbox"]
        if nph:
            x0, y0, x1, y1 = nph
            _cover(x0 - 80, y0 - 2, x1 + 80, y1 + 2, pad=2)
            # 반코드(윗줄) — placeholder 위치
            if student_class:
                _centered(nf_r, student_class, 0, pw, y0 + 22, 24.0)
            # 이름(아랫줄) — 원본처럼 가장 큰 요소로 (제목 다음으로 지배적)
            nsz = _fit(nf_b, english_name, pw * 0.80, 58.0, minsz=28.0)
            name_baseline = y1 + 56
            _centered(nf_b, english_name, 0, pw, name_baseline, nsz)
            # 이름 밑 얇은 회색 구분선 (원본처럼 넓게, 아래로)
            nw = nf_b.text_length(english_name, fontsize=nsz)
            half = max(nw / 2 + 50, 290)
            cx, dy = pw / 2, name_baseline + 20
            page.draw_line(fitz.Point(cx - half, dy), fitz.Point(cx + half, dy),
                           color=(0.55, 0.55, 0.55), width=0.8)
        # 월 줄 전체 재작성: "During the month of {month} {year}"
        for s in spans:
            if "month of" in s["text"].lower() and "_" in s["text"]:
                _cover(s["bbox"][0], s["bbox"][1], s["bbox"][2], s["bbox"][3], pad=2)
                _centered(nf_r, f"During the month of {month_name} {year}",
                          s["bbox"][0], s["bbox"][2], s["origin"][1], s["size"])
                break
        # 연도 줄 전체 재작성: "on the {year} POLY Grammar Proficiency Test,"
        for s in spans:
            if "_" in s["text"] and "Proficiency" in s["text"]:
                _cover(s["bbox"][0], s["bbox"][1], s["bbox"][2], s["bbox"][3], pad=2)
                _centered(nf_r, f"on the {year} POLY Grammar Proficiency Test,",
                          s["bbox"][0], s["bbox"][2], s["origin"][1], s["size"])
                break

    tw.write_text(page)
    try:
        doc.subset_fonts()
    except Exception:
        pass
    out = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    return out


def _render_yuseong(
    img: "Image.Image",
    draw: "ImageDraw.ImageDraw",
    template_path: str,
    award_type: str,
    english_name: str,
    student_class: str,
    month: str,
    dpi: int = 200,
) -> None:
    """
    유성 캠퍼스 상장: 이름·반·월·날짜 텍스트 삽입 + 가이드선 제거.
    img/draw는 이미 PDF → PIL 변환된 상태. 직접 수정.
    """
    parts = month.rsplit(" ", 1)
    month_name = parts[0]                       # "April"
    year = parts[1] if len(parts) > 1 else "2026"

    ph = _scan_yuseong_placeholders(template_path, dpi)
    sc = dpi / 72.0

    # ── 폰트 선택 (템플릿별 통일) ───────────────────────────────
    # 각 템플릿의 내장 폰트와 동일한 전체 TTF를 이름·본문 공통으로 사용
    # → 삽입 텍스트 글씨체가 템플릿 기존 텍스트와 일치, 상장 내 일관성 확보
    if award_type == "perfect_score":
        name_font_file = config.YUSEONG_CORSIVA_FONT      # MonotypeCorsiva.ttf
        body_font_file = config.YUSEONG_CORSIVA_FONT
    elif award_type == "honor_roll":
        name_font_file = config.YUSEONG_TREBUCHET_FONT    # TrebuchetMS-Bold.ttf
        body_font_file = config.YUSEONG_TREBUCHET_FONT
    else:  # best_sr
        name_font_file = config.YUSEONG_BASKERVILLE_FONT  # BaskOldFace.ttf
        body_font_file = config.YUSEONG_BASKERVILLE_FONT

    name_fs_pt  = ph["name_fs"]
    body_fs_pt  = ph["body_fs"]
    name_fs_px  = max(int(name_fs_pt * sc), 20)
    body_fs_px  = max(int(body_fs_pt * sc), 14)

    # 사전 계산 레이아웃에서 월별 폰트 크기 조회
    _lyt      = _YUSEONG_LAYOUT.get(award_type, {})
    _lyt_mo   = _lyt.get("months", {}).get(month_name, {})
    pre_month_fs = _lyt_mo.get("month_fs")   # None이면 동적 계산으로 폴백
    pre_date_fs  = _lyt_mo.get("date_fs")    # None이면 동적 계산으로 폴백

    def _erase(bbox_px, pad=8):
        """
        언더스코어(밑줄)가 있는 행만 배경색으로 덮어씀.
        - 배경: bbox 내 밝은 픽셀(sum>500)의 평균 → PS 흰 배경 / HR 회색 워터마크 모두 대응
        - 어두운 행만 지움 → HR 워터마크 텍스처를 최대한 보존
        """
        x0, y0, x1, y1 = bbox_px
        step_x = max(1, int((x1 - x0) / 25))

        # ① 배경색 추출: bbox 내 밝은 픽셀(sum>500) 평균
        # (언더라인·텍스트 픽셀은 sum≈0~300이어서 자동 제외됨)
        bg_samples = []
        for sx in range(int(x0), int(x1), step_x):
            for sy in range(int(y0), int(y1) + 1):
                try:
                    px = img.getpixel((max(0, min(img.width - 1, sx)),
                                       max(0, min(img.height - 1, sy))))
                    c = tuple(px[:3]) if len(px) >= 3 else (px, px, px)
                    if sum(c) > 500:
                        bg_samples.append(c)
                except Exception:
                    pass
        fill = (tuple(int(sum(c[i] for c in bg_samples) / len(bg_samples)) for i in range(3))
                if bg_samples else (255, 255, 255))

        # ② 어두운 행만 지우기 (dark-pixel 감지, 전 구역 동일 적용)
        # bottom zone 무조건 지우기 제거 → 워터마크 텍스처 보존
        check_step = max(1, min(step_x // 4, 8))
        for sy in range(int(y0), int(y1) + 6):  # +6: bbox 아래 살짝 연장해 언더라인 포함
            has_dark = False
            for sx in range(int(x0), int(x1) + 1, check_step):
                try:
                    px = img.getpixel((max(0, min(img.width - 1, sx)),
                                       max(0, min(img.height - 1, sy))))
                    c = tuple(px[:3]) if len(px) >= 3 else (px, px, px)
                    if sum(c) < 550:
                        has_dark = True
                        break
                except Exception:
                    pass
            if has_dark:
                draw.line([(int(x0) - 2, sy), (int(x1) + pad, sy)], fill=fill)

    def _copy_rows_below(y_start, y_end, x_start, x_end, offset=2):
        """언더라인(y_start~y_end)을 offset px 아래 깨끗한 배경 픽셀로 역방향 복사."""
        pixels = img.load()
        for sy in range(y_end, y_start - 1, -1):
            src_y = min(img.height - 1, sy + offset)
            for sx in range(max(0, x_start), min(img.width, x_end + 1)):
                pixels[sx, sy] = pixels[sx, src_y]

    def _centered_x(text, font, x0, x1):
        tb = draw.textbbox((0, 0), text, font=font)
        return x0 + ((x1 - x0) - (tb[2] - tb[0])) // 2

    # ── 이름 + 반 ─────────────────────────────────────────────
    if ph["name"] is not None:
        nx0, ny0, nx1, ny1 = ph["name"]
        if award_type == "honor_roll":
            # HR 이름 bbox에는 밑줄(underscores)만 있고 다른 pre-printed 텍스트 없음
            # _erase 생략 → bottom zone 균일 fill이 워터마크 텍스처 파괴하지 않음
            # 밑줄 행(ny1-9~ny1-3)만 아래 배경 픽셀로 직접 교체 (원본 배경 보장)
            _copy_rows_below(int(ny1) - 9, int(ny1) - 3, 0, img.width - 1, offset=8)
        else:
            # HR처럼 언더라인이 bbox 왼쪽 바깥(x≈30)까지 뻗는 경우 대응 → x0 확장
            _erase((max(0, int(nx0) - 340), ny0, nx1, ny1), pad=20)

        name_text = f"{english_name} ({student_class})"
        avail_w   = int(nx1 - nx0)
        name_font = _load_font_fit(
            name_font_file, name_text,
            name_fs_px, 16, avail_w, draw,
        )
        tb   = draw.textbbox((0, 0), name_text, font=name_font)
        tx   = _centered_x(name_text, name_font, int(nx0), int(nx1))
        ty   = int(ny0) + (int(ny1 - ny0) - (tb[3] - tb[1])) // 2 - tb[1]
        draw.text((tx, ty), name_text, font=name_font, fill=(0, 0, 0))

    # 2/5/8/11월 = Level test, 나머지 = Monthly test (PS·HR 공통)
    _LEVEL_TEST_MONTHS = {"February", "May", "August", "November"}

    # ── 월 (PS / HR) ──────────────────────────────────────────
    if ph["month"] is not None and award_type in ("perfect_score", "honor_roll"):
        mx0, my0, mx1, my1 = ph["month"]

        # 템플릿 suffix 추출 ("test." / "Test." 등)
        suffix = ph.get("month_suffix") or ""

        # 지우기 범위: 언더스코어 시작 ~ suffix 끝 (전체 span x1)
        if ph.get("month_span") is not None:
            ex1 = ph["month_span"][2]   # full span x1 (suffix 포함)
        else:
            ex1 = mx1
        if award_type == "honor_roll":
            # HR 월 bbox: 밑줄만 있고 pre-printed 텍스트 없음 (y=928-986 dark=0%)
            # _erase 생략 → 균일 fill이 워터마크 그라디언트 파괴하는 문제 방지
            # ① 전체 너비로 밑줄 행(my1-10~my1-2) 아래 원본 배경으로 교체
            _copy_rows_below(int(my1) - 10, int(my1) - 2, 0, img.width - 1, offset=17)
            # ② suffix "." glyph 제거: y=my1-22~my1-11(=975-986), x=mx1 오른쪽만
            #    src_y = sy+22 ≥ my1 = 997 → 깨끗한 배경 보장
            _copy_rows_below(int(my1) - 22, int(my1) - 11,
                             max(0, int(mx1) - 10), img.width - 1, offset=22)
        else:
            _erase((max(0, int(mx0) - 20), my0, ex1, my1), pad=10)

        # 월별 test 종류 결정
        test_type  = "Level" if month_name in _LEVEL_TEST_MONTHS else "Monthly"
        # 항상 "test"를 포함 ("April Monthly test." / "February Level test.")
        if suffix and suffix[0] in ".,:;":
            month_text = f"{month_name} {test_type} test{suffix}"
        else:
            month_text = f"{month_name} {test_type} test {suffix}".strip()
        avail_w    = int(ex1 - mx0)

        # 동적 폰트 크기 (step=2 for fine-grained fit)
        size = body_fs_px
        body_font = _load_font(body_font_file, size)
        while size >= 12:
            body_font = _load_font(body_font_file, size)
            tb_check  = draw.textbbox((0, 0), month_text, font=body_font)
            if (tb_check[2] - tb_check[0]) <= avail_w:
                break
            size -= 2

        tb = draw.textbbox((0, 0), month_text, font=body_font)
        ty = int(my0) + (int(my1 - my0) - (tb[3] - tb[1])) // 2 - tb[1]
        tx = int(mx0) - tb[0]   # 왼쪽 정렬: 언더스코어 시작 위치에서 시작
        draw.text((tx, ty), month_text, font=body_font, fill=(0, 0, 0))

    # ── 가이드선 제거 (날짜 텍스트 그리기 전에 실행) ──────────────
    # 선 위쪽 깨끗한 배경에서 샘플링 → 안티앨리어싱 오염 없음
    # PS: 같은 y에 서명 언더라인도 있으므로 date_line만 지움
    # HR/SR: content 구역 내 모든 선 지움 (하단 30% 서명 보호)
    page_safe_y = img.height * 0.70
    if award_type == "perfect_score":
        # date_line(x0,y,x1) → (y,x0,x1) 형식으로 변환
        _guide_lines = (
            [(ph["date_line"][1], ph["date_line"][0], ph["date_line"][2])]
            if ph["date_line"] is not None else []
        )
    else:
        _guide_lines = [(ly, lx0, lx1) for (ly, lx0, lx1) in ph["lines"]
                        if ly <= page_safe_y]
    for (ly, lx0, lx1) in _guide_lines:
        step_x = max(1, int((lx1 - lx0) / 20))
        bg = []
        for sx in range(int(lx0), int(lx1), step_x):
            for dy in range(5, 12):          # 선 5~11px 위 구간
                sy = int(ly) - dy
                if 0 <= sy < img.height:
                    try:
                        px = img.getpixel((max(0, min(img.width - 1, sx)), sy))
                        c = tuple(px[:3]) if len(px) >= 3 else (px, px, px)
                        bg.append(c)
                    except Exception:
                        pass
        fill = (tuple(int(sum(c[i] for c in bg) / len(bg)) for i in range(3))
                if bg else (255, 255, 255))
        for sy in range(int(ly) - 3, int(ly) + 5):
            if 0 <= sy < img.height:
                draw.line([(int(lx0) - 6, sy), (int(lx1) + 6, sy)], fill=fill)

    # ── 날짜 ──────────────────────────────────────────────────
    if ph["date"] is not None:
        if award_type == "perfect_score" and ph["date_line"] is not None:
            # PS: date_area(x=253-1468)는 엠블럼(x=910-1237)과 겹침 → 전체 지우면 엠블럼 파괴
            # 날짜 필드(date_line x=390-717) 왼쪽 영역만 흰색 사각형으로 지움
            da = ph["date"]           # (x0, y0, x1, y1)
            dl_x0, dl_y, dl_x1 = ph["date_line"]
            draw.rectangle(
                [int(da[0]) - 2, int(da[1]) - 2,
                 int(dl_x1) + 10, int(dl_y) + 4],
                fill=(255, 255, 255),
            )
        else:
            _erase(ph["date"], pad=60)

        if award_type == "best_sr":
            date_text = f"Presented in {month}"
        else:
            date_text = f"{month_name}, {year}"

        if award_type == "perfect_score" and ph["date_line"] is not None:
            # PS: 좌측 벡터 언더라인 위에 배치
            dl_x0, dl_y, dl_x1 = ph["date_line"]
            avail_w = int(dl_x1 - dl_x0)
            if pre_date_fs is not None:
                body_font = _load_font(body_font_file, pre_date_fs)
            else:
                size = body_fs_px
                while size >= 12:
                    body_font = _load_font(body_font_file, size)
                    tb = draw.textbbox((0, 0), date_text, font=body_font)
                    if (tb[2] - tb[0]) <= avail_w:
                        break
                    size -= 2
            tb = draw.textbbox((0, 0), date_text, font=body_font)
            tx = int(dl_x0) + (avail_w - (tb[2] - tb[0])) // 2
            # visual bottom(tb[3]) 기준으로 ty 계산 → 텍스트 하단이 선 8px 위에 위치
            ty = int(dl_y) - tb[3] - 8
            draw.text((tx, ty), date_text, font=body_font, fill=(0, 0, 0))
        else:
            # HR / SR: 감지된 날짜 bbox 내 중앙 배치
            dx0, dy0, dx1, dy1 = ph["date"]
            avail_w = int(dx1 - dx0)
            if pre_date_fs is not None:
                body_font = _load_font(body_font_file, pre_date_fs)
            else:
                size = body_fs_px
                while size >= 12:
                    body_font = _load_font(body_font_file, size)
                    tb = draw.textbbox((0, 0), date_text, font=body_font)
                    if (tb[2] - tb[0]) <= avail_w:
                        break
                    size -= 2
            tb  = draw.textbbox((0, 0), date_text, font=body_font)
            tx  = _centered_x(date_text, body_font, int(dx0), int(dx1))
            ty  = int(dy0) + (int(dy1 - dy0) - (tb[3] - tb[1])) // 2 - tb[1]
            draw.text((tx, ty), date_text, font=body_font, fill=(0, 0, 0))


def build_certificate(
    award_type:        str,
    english_name:      str,
    student_class:     str,
    month:             str,
    output_path:       str,
    template_override: str | None = None,
    extra_text:        str | None = None,   # 정발: 반 이름 or 레벨 이름
    campus:            str | None = None,
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

    is_jungbal  = award_type in config.JUNGBAL_AWARD_TYPES
    is_yuseong  = (campus is not None and "유성" in campus
                   and award_type in config.YUSEONG_AWARD_TYPES)
    is_bundang  = (campus is not None and "분당" in campus
                   and award_type in config.BUNDANG_AWARD_TYPES)

    if is_bundang:
        # ── 분당엠폴리: 벡터 텍스트 직접 주입 (래스터화 없음 → 선명, 파일 작음)
        pdf_bytes = _inject_bundang_text_pdf(
            template_path, award_type, english_name, student_class, month)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "wb") as _f:
            _f.write(pdf_bytes)
        return

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

    if is_yuseong:
        # ── 유성: 커스텀 placeholder 기반 텍스트 삽입
        _render_yuseong(img, draw, template_path, award_type,
                        english_name, student_class, month, config.DPI)
    elif is_jungbal:
        # ── 정발: 반 이름 (Pinyon Script)
        _class_font_file = config.JUNGBAL_SCRIPT_FONT
        class_font = _load_font(_class_font_file, config.CLASS_FONT_SIZE)
        class_y    = config.CLASS_Y.get(award_type, 520)
        _draw_centered(draw, student_class, class_y, class_font, config.CLASS_COLOR, w)

        lines     = _scan_template_lines(template_path, config.DPI, 0)
        divider_y = _find_divider_y(lines, config.DIVIDER_LINE_Y_FALLBACK.get(award_type, 870))

        name_font = _load_font_fit(
            config.JUNGBAL_SCRIPT_FONT, english_name,
            config.NAME_FONT_SIZE.get(award_type, 140), config.NAME_FONT_SIZE_MIN,
            config.NAME_MAX_WIDTH, draw,
        )
        name_bbox = draw.textbbox((0, 0), english_name, font=name_font)
        name_y    = divider_y - name_bbox[3] - config.NAME_LINE_GAP
        _draw_centered(draw, english_name, name_y, name_font, config.NAME_COLOR, w)
    else:
        # ── 기존 캠퍼스: 고정 Y 기반 텍스트 배치 ─────────────
        class_font = _load_font(config.CLASS_FONT, config.CLASS_FONT_SIZE)
        class_y    = config.CLASS_Y.get(award_type, 520)
        _draw_centered(draw, student_class, class_y, class_font, config.CLASS_COLOR, w)

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
