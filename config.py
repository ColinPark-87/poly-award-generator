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

# ── 반/레벨 이름: AWARDED TO 바로 아래 ────────────────────────
# 이미지: 2340×1655px / AWARDED TO 하단 y≈490 (honor_roll y≈600)
CLASS_Y = {
    "perfect_score": 520,
    "honor_roll":    625,
    "best_writer":   520,
}
CLASS_FONT_SIZE = 52
CLASS_COLOR     = (13, 27, 62)
CLASS_FONT      = "Montserrat-Bold.ttf"

# ── 학생 이름: 가로 구분선 바로 위 ────────────────────────────
# perfect_score/best_writer: 구분선 y≈870 → NAME_Y=690 (폰트 160px)
# honor_roll: 구분선 y≈824, 공간 좁음 → NAME_Y=710 (폰트 110px)
NAME_Y = {
    "perfect_score": 690,
    "honor_roll":    710,
    "best_writer":   690,
}
NAME_FONT_SIZE = {             # award_type별 최대 폰트 크기
    "perfect_score": 160,
    "honor_roll":    110,      # 공간 제한으로 작게
    "best_writer":   160,
}
NAME_FONT_SIZE_MIN = 70
NAME_MAX_WIDTH     = 1600
NAME_COLOR         = (13, 27, 62)
NAME_FONT          = "DancingScript-Bold.ttf"

# ── Date: Date 밑줄(y≈1295) 바로 위 ──────────────────────────
# 폰트 크기 52px 기준 높이≈52px → top y = 1295 - 52 - 10gap = 1233
# Date 라인 중심 X: 스크린샷 측정 기준 x≈565 (2340px 이미지)
DATE_CENTER_X   = 706
DATE_Y          = 1233
DATE_FONT_SIZE  = 52
DATE_COLOR      = (13, 27, 62)
DATE_FONT       = "Montserrat-Bold.ttf"
