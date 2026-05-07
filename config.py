import os

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
FONT_DIR     = os.path.join(BASE_DIR, "fonts")

TEMPLATES = {
    "perfect_score": os.path.join(TEMPLATE_DIR, "perfect_score.pdf"),
    "honor_roll":    os.path.join(TEMPLATE_DIR, "honor_roll.pdf"),
    "best_writer":   os.path.join(TEMPLATE_DIR, "best_writer.pdf"),
    "best_sr":       os.path.join(TEMPLATE_DIR, "best_sr.pdf"),
}

# PDF → PNG 변환 해상도 (200 DPI → 2340×1655 px)
DPI = 200

# ── 이름 좌표 (상장별로 타이틀 높이가 달라 Y 값 분리) ──────────
# 이미지 크기: 2340 × 1655
# Perfect Score / Best Writer: 타이틀 1줄 → "AWARDED TO" y≈330
# Honor Roll: 타이틀 2줄(HONOR ROLL + AWARD) → "AWARDED TO" y≈497

# ── 반/레벨 이름: AWARDED TO 바로 아래 (고정 Y) ───────────────
CLASS_Y = {
    "perfect_score": 520,
    "honor_roll":    625,
    "best_writer":   520,
    "best_sr":       520,
}
CLASS_FONT_SIZE = 52
CLASS_COLOR     = (13, 27, 62)
CLASS_FONT      = "Montserrat-Bold.ttf"

# ── 학생 이름: 구분선 기준 하단 정렬 ─────────────────────────
# NAME_Y 대신 generator가 구분선 위치를 자동 감지 후 bbox 하단 정렬
# → 대소문자 조합, 이름 길이 상관없이 항상 선 바로 위에 위치
NAME_LINE_GAP  = 5             # 텍스트 하단 ~ 구분선 간격 (px)
NAME_FONT_SIZE = {             # award_type별 최대 폰트 크기
    "perfect_score": 160,
    "honor_roll":    110,      # 2줄 타이틀로 공간 좁음
    "best_writer":   160,
    "best_sr":       160,
}
NAME_FONT_SIZE_MIN = 70
NAME_MAX_WIDTH     = 1600
NAME_COLOR         = (13, 27, 62)
NAME_FONT          = "DancingScript-Bold.ttf"

# 자동 감지 실패 시 폴백 값
DIVIDER_LINE_Y_FALLBACK = {
    "perfect_score": 870,
    "honor_roll":    870,
    "best_writer":   870,
    "best_sr":       870,
}

# ── Date: Date 밑줄 기준 하단 정렬 ───────────────────────────
# DATE_Y 대신 generator가 밑줄 위치를 자동 감지 후 bbox 하단 정렬
# → January~December 어떤 월이 와도 항상 선 바로 위에 위치
DATE_LINE_GAP  = 5             # 텍스트 하단 ~ Date 밑줄 간격 (px)
DATE_CENTER_X  = 706           # Date 밑줄 중심 X (2340px 기준)
DATE_FONT_SIZE = 52
DATE_COLOR     = (13, 27, 62)
DATE_FONT      = "Montserrat-Bold.ttf"

# 자동 감지 실패 시 폴백
DATE_LINE_Y_FALLBACK = 1295
