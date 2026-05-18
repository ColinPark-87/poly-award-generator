import os
import json

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
FONT_DIR     = os.path.join(BASE_DIR, "fonts")

# 기본 템플릿 (캠퍼스별 템플릿 없을 때 폴백)
TEMPLATES = {
    "perfect_score": os.path.join(TEMPLATE_DIR, "perfect_score.pdf"),
    "honor_roll":    os.path.join(TEMPLATE_DIR, "honor_roll.pdf"),
    "best_writer":   os.path.join(TEMPLATE_DIR, "best_writer.pdf"),
    "best_sr":       os.path.join(TEMPLATE_DIR, "best_sr.pdf"),
}

_CAMPUS_CONFIG_PATH = os.path.join(BASE_DIR, "campus_config.json")
_DEFAULT_CAMPUS_CFG = {
    "perfect_score_min": 100.0,
    "honor_roll_min": 95.0,
    "bw_min_lc": {"GT": 27, "MGT": 27, "S": 27, "MAG": 27},
    "award_labels": {
        "perfect_score": "Perfect Score",
        "honor_roll":    "Honor Roll",
        "best_writer":   "Best Writer",
        "best_sr":       "Best SR",
    },
}

def load_campus_config() -> dict:
    if os.path.exists(_CAMPUS_CONFIG_PATH):
        with open(_CAMPUS_CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}

def get_campus_cfg(campus: str) -> dict:
    """캠퍼스 설정 반환. 없으면 기본값."""
    return load_campus_config().get(campus, _DEFAULT_CAMPUS_CFG)

def get_template_path(campus: str, award_type: str) -> str:
    """캠퍼스별 템플릿 경로. 없으면 기본 templates/ 폴더 사용."""
    campus_path = os.path.join(TEMPLATE_DIR, campus, f"{award_type}.pdf")
    if os.path.exists(campus_path):
        return campus_path
    return TEMPLATES[award_type]

# PDF → PNG 변환 해상도 (200 DPI → 2340×1655 px)
DPI = 200

# ── 이름 좌표 (상장별로 타이틀 높이가 달라 Y 값 분리) ──────────
# 이미지 크기: 2340 × 1655
# Perfect Score / Best Writer: 타이틀 1줄 → "AWARDED TO" y≈330
# Honor Roll: 타이틀 2줄(HONOR ROLL + AWARD) → "AWARDED TO" y≈497

# ── 반/레벨 이름: AWARDED TO 바로 아래 (고정 Y) ───────────────
CLASS_Y = {
    "perfect_score":          520,
    "honor_roll":             625,
    "best_writer":            520,
    "best_sr":                640,
    # 정발 캠퍼스
    "achievement_certificate": 680,
    "monthly_test_winner":     680,
    "level_test_winner":       680,
}
CLASS_FONT_SIZE = 52
CLASS_COLOR     = (13, 27, 62)
CLASS_FONT      = "Montserrat-Bold.ttf"

# ── 학생 이름: 구분선 기준 하단 정렬 ─────────────────────────
# NAME_Y 대신 generator가 구분선 위치를 자동 감지 후 bbox 하단 정렬
# → 대소문자 조합, 이름 길이 상관없이 항상 선 바로 위에 위치
NAME_LINE_GAP  = 5             # 텍스트 하단 ~ 구분선 간격 (px)
NAME_FONT_SIZE = {             # award_type별 최대 폰트 크기
    "perfect_score":           160,
    "honor_roll":              110,      # 2줄 타이틀로 공간 좁음
    "best_writer":             160,
    "best_sr":                 150,
    # 정발 캠퍼스
    "achievement_certificate": 140,
    "monthly_test_winner":     140,
    "level_test_winner":       140,
}
NAME_FONT_SIZE_MIN = 70
NAME_MAX_WIDTH     = 1600
NAME_COLOR         = (13, 27, 62)
NAME_FONT          = "DancingScript-Bold.ttf"

# 자동 감지 실패 시 폴백 값
DIVIDER_LINE_Y_FALLBACK = {
    "perfect_score":           870,
    "honor_roll":              870,
    "best_writer":             870,
    "best_sr":                 870,
    # 정발 캠퍼스 (실제 선 y=904)
    "achievement_certificate": 904,
    "monthly_test_winner":     904,
    "level_test_winner":       904,
}

# ── 유성 전용 폰트 파일 ─────────────────────────────────────
# templates/유성/에서 추출해 fonts/ 폴더에 저장
YUSEONG_CORSIVA_FONT     = "MonotypeCorsiva.ttf"     # perfect_score 본문/이름
YUSEONG_TREBUCHET_FONT   = "TrebuchetMS-Bold.ttf"    # honor_roll 본문/이름
YUSEONG_BASKERVILLE_FONT = "BaskOldFace.ttf"         # best_sr 본문/이름

YUSEONG_AWARD_TYPES = {"perfect_score", "honor_roll", "best_sr"}

# ── 정발 전용: 가상 자리표시자 기반 텍스트 배치 ──────────────
# _scan_jungbal_placeholders() 가 PDF에서 자동으로 찾으며,
# 이 상수들은 감지 실패 시 폴백으로만 사용됨
JUNGBAL_AWARD_TYPES = {
    "achievement_certificate",
    "monthly_test_winner",
    "level_test_winner",
}
# 날짜 자리표시자 폴백 bbox (x0,y0,x1,y1 @200dpi)
JUNGBAL_DATE_BBOX_FALLBACK = (1190, 1087, 1468, 1198)
# 반/레벨 이름 자리표시자 폴백 bbox (monthly/level winner 전용)
JUNGBAL_EXTRA_BBOX_FALLBACK = (1439, 959, 1773, 1070)
# 정발 전용 폰트: PalaceScriptMT와 가장 유사한 무료 스크립트체 (이름·반·날짜 통일)
JUNGBAL_SCRIPT_FONT = "PinyonScript-Regular.ttf"
# 자리표시자용 폰트 크기 — 템플릿 원본 40pt × (200/72) ≈ 111px, 여유를 두고 80
JUNGBAL_PLACEHOLDER_FONT_SIZE = 80

# ── Date: Date 밑줄 기준 하단 정렬 ───────────────────────────
# DATE_Y 대신 generator가 밑줄 위치를 자동 감지 후 bbox 하단 정렬
# → January~December 어떤 월이 와도 항상 선 바로 위에 위치
DATE_LINE_GAP  = 5             # 텍스트 하단 ~ Date 밑줄 간격 (px)
DATE_CENTER_X  = 706           # Date 밑줄 중심 X (2340px 기준)
DATE_FONT_SIZE = 52
DATE_COLOR     = (0, 0, 0)
DATE_FONT      = "PlayfairDisplay-Regular.ttf"

# 자동 감지 실패 시 폴백
DATE_LINE_Y_FALLBACK = 1295
