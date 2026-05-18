"""
유성 캠퍼스 레이아웃 사전 계산 스크립트.

실행: python build_yuseong_layout.py
결과: yuseong_layout.json 생성

저장 내용:
  - 각 템플릿(PS/HR/SR) × 1~12월 별 최적 폰트 크기
  - 각 필드 bbox (px @200DPI)
  - 각 폰트의 알파벳 a-Z 문자 너비 메트릭 (이름/반 렌더링 참고용)

이 데이터를 generator.py 에서 조회하면 런타임에 폰트 크기 계산을 생략할 수 있어
월별/이름별 렌더링이 항상 일관됩니다.
"""
import os
import json
from PIL import Image, ImageDraw, ImageFont
from generator import _scan_yuseong_placeholders
import config

MONTHS = [
    "January", "February", "March", "April",
    "May", "June", "July", "August",
    "September", "October", "November", "December",
]

TEMPLATES = {
    "perfect_score": {
        "font": config.YUSEONG_CORSIVA_FONT,
        "month_suffix": "Monthly",
    },
    "honor_roll": {
        "font": config.YUSEONG_TREBUCHET_FONT,
        "month_suffix": "Level",
    },
    "best_sr": {
        "font": config.YUSEONG_BASKERVILLE_FONT,
        "month_suffix": None,   # SR은 월 필드 없음
    },
}

DPI = config.DPI
YEAR = "2026"

ALPHABET = (
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789 ()-."
)


def _fit_font(font_file, text, max_size, min_size, max_width):
    """주어진 너비에 맞는 최대 폰트 크기 반환."""
    dummy_img  = Image.new("RGB", (1, 1))
    dummy_draw = ImageDraw.Draw(dummy_img)
    size = max_size
    while size >= min_size:
        font = ImageFont.truetype(os.path.join(config.FONT_DIR, font_file), size)
        tb = dummy_draw.textbbox((0, 0), text, font=font)
        if (tb[2] - tb[0]) <= max_width:
            return size
        size -= 1
    return min_size


def _char_widths(font_file, font_size):
    """각 문자의 렌더링 너비 (px) 딕셔너리 반환."""
    dummy_img  = Image.new("RGB", (1, 1))
    dummy_draw = ImageDraw.Draw(dummy_img)
    font = ImageFont.truetype(os.path.join(config.FONT_DIR, font_file), font_size)
    widths = {}
    for ch in ALPHABET:
        tb = dummy_draw.textbbox((0, 0), ch, font=font)
        widths[ch] = tb[2] - tb[0]
    return widths


layout = {}

for award_type, tinfo in TEMPLATES.items():
    font_file = tinfo["font"]
    tmpl_path = os.path.join(config.TEMPLATE_DIR, "유성", f"{award_type}.pdf")
    if not os.path.exists(tmpl_path):
        print(f"  [SKIP] 템플릿 없음: {tmpl_path}")
        continue

    ph = _scan_yuseong_placeholders(tmpl_path, DPI)
    sc = DPI / 72.0

    body_fs_px = max(int(ph["body_fs"] * sc), 14)
    name_fs_px = max(int(ph["name_fs"] * sc), 20)

    entry = {
        "font":       font_file,
        "name_fs_px": name_fs_px,
        "body_fs_px": body_fs_px,
        "name_area":  list(ph["name"])  if ph["name"]      else None,
        "month_area": list(ph["month"]) if ph["month"]      else None,
        "date_area":  list(ph["date"])  if ph["date"]       else None,
        "date_line":  list(ph["date_line"]) if ph["date_line"] else None,
        "months": {},
        "char_widths": {},
    }

    # 월별 최적 폰트 크기 계산
    for mo in MONTHS:
        mo_entry = {}

        # 월 텍스트 (PS/HR만)
        if tinfo["month_suffix"] and ph["month"]:
            mx0, my0, mx1, my1 = ph["month"]
            avail_w = int(mx1 - mx0)
            month_text = f"{mo} {tinfo['month_suffix']}"
            mo_entry["month_fs"] = _fit_font(font_file, month_text, body_fs_px, 12, avail_w)

        # 날짜 텍스트
        if ph["date"]:
            if award_type == "best_sr":
                date_text = f"Presented in {mo} {YEAR}"
                dx0, dy0, dx1, dy1 = ph["date"]
                avail_w = int(dx1 - dx0)
            elif award_type == "perfect_score" and ph["date_line"]:
                date_text = f"{mo}, {YEAR}"
                dl_x0, dl_y, dl_x1 = ph["date_line"]
                avail_w = int(dl_x1 - dl_x0)
            else:
                date_text = f"{mo}, {YEAR}"
                dx0, dy0, dx1, dy1 = ph["date"]
                avail_w = int(dx1 - dx0)
            mo_entry["date_fs"] = _fit_font(font_file, date_text, body_fs_px, 12, avail_w)

        entry["months"][mo] = mo_entry

    # 대표 폰트 크기에서 알파벳 문자 너비 계산
    entry["char_widths"] = _char_widths(font_file, body_fs_px)

    layout[award_type] = entry
    print(f"  OK {award_type}: {len(entry['months'])} months done")

out_path = os.path.join(os.path.dirname(__file__), "yuseong_layout.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(layout, f, ensure_ascii=False, indent=2)

print(f"\nyuseong_layout.json 저장 완료: {out_path}")
