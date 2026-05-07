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
NAME_FONT_SIZE     = 120          # 최대 폰트 크기 (이름 길이에 따라 자동 축소)
NAME_FONT_SIZE_MIN = 60           # 최소 폰트 크기
NAME_MAX_WIDTH     = 1500         # 이름이 차지할 수 있는 최대 px 너비 (2340 기준 ~64%)
NAME_COLOR         = (13, 27, 62) # 다크 네이비
NAME_FONT          = "DancingScript-Bold.ttf"

# 반/레벨 이름: 학생 이름 바로 아래
CLASS_Y = {
    "perfect_score": 625,
    "honor_roll":    765,
    "best_writer":   625,
}
CLASS_FONT_SIZE = 55
CLASS_COLOR     = (13, 27, 62)
CLASS_FONT      = "Montserrat-Bold.ttf"

# Date: 하단 좌측 Date 라인 위에 중앙 정렬
DATE_CENTER_X   = 338             # Date 라인 중심 X 좌표 (2340px 기준)
DATE_Y          = 1258
DATE_FONT_SIZE  = 42
DATE_COLOR      = (13, 27, 62)
DATE_FONT       = "Montserrat-Bold.ttf"
