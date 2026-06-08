# -*- coding: utf-8 -*-
"""
일산(Ilsan) 전용 상장 템플릿 베이킹.

정발 템플릿(templates/정발/*.pdf)을 복제하면서 박힌 캠퍼스 표기를
"Jeongbal" → "Ilsan" 으로 치환한다. **원본과 동일한 폰트를 그대로 사용**하여
영어 단어(Jeongbal→Ilsan)만 바뀌게 한다. 두 곳을 교체:
  1) 제목  : "POL Y Jeongbal is proud to honor" (PalaceScriptMT 54pt)
             → 시스템의 PalaceScriptMT(C:/Windows/Fonts/PALSCRI.TTF, 'Ilsan'의 대문자
               'I' 포함 전 글리프 보유)로 줄 전체를 동일 폰트·크기·중앙정렬로 다시 써넣음.
               (단어만 바뀌고 폰트는 원본과 동일. Ilsan이 짧아 줄이 약간 짧아질 뿐)
  2) 서명란: "POLY Jeongbal" (Calibri-Bold 18pt) → Calibri-Bold로 "POLY Ilsan" 재기입.

치환 폰트는 fitz가 PDF에 서브셋 임베드 → Streamlit Cloud(Linux)에서도 정상 렌더.
Ilsan은 Jeongbal보다 짧아 짤림/오버플로우 위험 없음.

산출물:
  templates/일산/achievement_certificate.pdf
  templates/일산/monthly_test_winner.pdf
  templates/일산/level_test_winner.pdf
  test_output/ilsan_preview_*.png  (육안 검증용)

재생성 가능: python build_ilsan_templates.py
"""
import os
import fitz  # PyMuPDF
from PIL import Image

import config

SRC_DIR = os.path.join(config.TEMPLATE_DIR, "정발")
DST_DIR = os.path.join(config.TEMPLATE_DIR, "일산")
PREVIEW_DIR = os.path.join(os.path.dirname(__file__), "test_output")

OLD = "Jeongbal"
NEW = "Ilsan"

PALACE_PATH = "C:/Windows/Fonts/PALSCRI.TTF"    # PalaceScriptMT (제목 원본 폰트)
CALIBRI_BOLD = "C:/Windows/Fonts/calibrib.ttf"  # 서명란 원본 폰트. 베이킹 머신(Windows)에만 필요


def _sample_bg(page: fitz.Page, rect: fitz.Rect) -> tuple[float, float, float]:
    """rect 위/아래의 깨끗한 띠에서 가장 밝은 픽셀(=배경색) 추출. 0~1 정규화."""
    candidates = []
    for clip in (
        fitz.Rect(rect.x0, rect.y0 - 16, rect.x1, rect.y0 - 8),   # 위쪽 띠
        fitz.Rect(rect.x0, rect.y1 + 6, rect.x1, rect.y1 + 14),   # 아래쪽 띠
    ):
        if clip.y0 < 0:
            continue
        pix = page.get_pixmap(clip=clip)
        if not (pix.samples and pix.width * pix.height):
            continue
        n = pix.n
        data = pix.samples
        for i in range(0, len(data), n):
            candidates.append((data[i], data[i + 1], data[i + 2]))
    if not candidates:
        return (1.0, 1.0, 1.0)
    b = max(candidates, key=sum)
    return (b[0] / 255.0, b[1] / 255.0, b[2] / 255.0)


def _find_span(page: fitz.Page, needle: str, big: bool):
    """needle 포함 span 반환. big=True면 제목(size>30), False면 서명(size<30)."""
    for blk in page.get_text("dict")["blocks"]:
        if blk["type"] != 0:
            continue
        for ln in blk["lines"]:
            for sp in ln["spans"]:
                if needle in sp["text"] and ((sp["size"] > 30) == big):
                    return sp
    return None


def _bake_one(src_path: str, dst_path: str) -> None:
    doc = fitz.open(src_path)
    page = doc[0]
    page_w = page.rect.width

    title = _find_span(page, OLD, big=True)
    sig = _find_span(page, OLD, big=False)
    if title is None or sig is None:
        raise RuntimeError(f"{os.path.basename(src_path)}: 제목/서명 span 미검출 "
                           f"(title={title is not None}, sig={sig is not None})")

    pal = fitz.Font(fontfile=PALACE_PATH)             # 제목: 원본과 동일 PalaceScriptMT
    cal = fitz.Font(fontfile=CALIBRI_BOLD)            # 서명: 원본과 동일 Calibri-Bold

    # ── 1) 제목: 원본 폰트(PalaceScriptMT)·크기 그대로, 단어만 Ilsan, 페이지 중앙 정렬 ──
    t_rect = fitz.Rect(title["bbox"])
    t_text = title["text"].replace(OLD, NEW)          # "POL Y Ilsan is proud to honor"
    t_base = title["origin"][1]

    # 원본 크기(54pt) 유지하되 페이지 폭 초과 시에만 축소(Ilsan은 더 짧아 사실상 미발동)
    t_size = float(title["size"])
    max_w = page_w - 120.0
    while t_size > 24 and pal.text_length(t_text, fontsize=t_size) > max_w:
        t_size -= 1.0
    t_w = pal.text_length(t_text, fontsize=t_size)
    t_x = (page_w - t_w) / 2.0                          # 페이지 중앙 정렬(원본도 중앙)

    # 채움 없이(fill=False) 글리프만 제거 → 배경 워터마크("P") 보존
    page.add_redact_annot(fitz.Rect(t_rect.x0 - 2, t_rect.y0 - 3,
                                    t_rect.x1 + 2, t_rect.y1 + 3), fill=False)

    # ── 2) 서명란: "POLY Ilsan" Calibri-Bold 재기입 (좌측 x 유지) ──
    s_rect = fitz.Rect(sig["bbox"])
    s_text = sig["text"].replace(OLD, NEW)             # "POLY Ilsan"
    s_base = sig["origin"][1]
    s_size = float(sig["size"])
    s_x = sig["origin"][0]
    s_clr_int = sig["color"]
    s_clr = (((s_clr_int >> 16) & 255) / 255.0,
             ((s_clr_int >> 8) & 255) / 255.0,
             (s_clr_int & 255) / 255.0)
    page.add_redact_annot(fitz.Rect(s_rect.x0 - 2, s_rect.y0 - 2,
                                    s_rect.x1 + 4, s_rect.y1 + 2), fill=False)

    # redaction 일괄 적용: 텍스트 글리프만 제거, 이미지(워터마크)·라인아트 보존
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE,
                          graphics=fitz.PDF_REDACT_LINE_ART_NONE)

    # 새 텍스트 기입
    tw_t = fitz.TextWriter(page.rect, color=(0.0, 0.0, 0.0))
    tw_t.append(fitz.Point(t_x, t_base), t_text, font=pal, fontsize=t_size)
    tw_t.write_text(page)

    tw_s = fitz.TextWriter(page.rect, color=s_clr)
    tw_s.append(fitz.Point(s_x, s_base), s_text, font=cal, fontsize=s_size)
    tw_s.write_text(page)

    doc.subset_fonts()  # 임베드 폰트 서브셋 → 클라우드 안전 + 파일 축소
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    doc.save(dst_path, garbage=4, deflate=True)
    doc.close()
    print(f"  [OK] {os.path.basename(dst_path)}  title={t_text!r} @ size {t_size:.0f}  sig={s_text!r}")


def _preview(pdf_path: str, png_path: str) -> None:
    doc = fitz.open(pdf_path)
    pix = doc[0].get_pixmap(matrix=fitz.Matrix(200 / 72, 200 / 72))
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    img.save(png_path)
    doc.close()


def main():
    names = ["achievement_certificate", "monthly_test_winner", "level_test_winner"]
    print(f"일산 템플릿 베이킹: {SRC_DIR} -> {DST_DIR}")
    for _fp, _nm in ((PALACE_PATH, "PalaceScriptMT(PALSCRI.TTF)"), (CALIBRI_BOLD, "Calibri-Bold")):
        if not os.path.exists(_fp):
            raise FileNotFoundError(f"{_nm} 없음(베이킹은 Windows에서): {_fp}")
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    for nm in names:
        src = os.path.join(SRC_DIR, f"{nm}.pdf")
        dst = os.path.join(DST_DIR, f"{nm}.pdf")
        _bake_one(src, dst)
        _preview(dst, os.path.join(PREVIEW_DIR, f"ilsan_preview_{nm}.png"))
    print("완료. 프리뷰:", PREVIEW_DIR)


if __name__ == "__main__":
    main()
