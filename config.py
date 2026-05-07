import os

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
FONT_DIR     = os.path.join(BASE_DIR, "fonts")

TEMPLATES = {
    "perfect_score": os.path.join(TEMPLATE_DIR, "perfect_score.pdf"),
    "honor_roll":    os.path.join(TEMPLATE_DIR, "honor_roll.pdf"),
    "best_writer":   os.path.join(TEMPLATE_DIR, "best_writer.pdf"),
}

# PDF → PNG 변환 해상도 (200 DPI → 2340×1655 px)
DPI = 200

# ── 이름 좌표 (상장별로 타이틀 높이가 달라 Y 값 분리) ──────────
# 이미지 크기: 2340 × 1655
# Perfect Score / Best Writer: 타이틀 1줄 → "AWARDED TO" y≈330
# Honor Roll: 타이틀 2줄(HONOR ROLL + AWARD) → "AWARDED TO" y≈497

NAME_Y = {
    "perfect_score": 470,
    "honor_roll":    610,
    "best_writer":   470,
}
NAME_FONT_SIZE  = 120
NAME_COLOR      = (13, 27, 62)    # 다크 네이비
NAME_FONT       = "DancingScript-Bold.ttf"

# Date: 하단 좌측 Date 라인 위
DATE_X          = 195
DATE_Y          = 1310
DATE_FONT_SIZE  = 42
DATE_COLOR      = (13, 27, 62)
DATE_FONT       = "Montserrat-Bold.ttf"
