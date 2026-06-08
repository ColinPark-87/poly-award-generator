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

def set_campus_director(campus: str, name: str) -> None:
    """캠퍼스 원장 사인 이름을 campus_config.json 에 저장(영구).
    파일에 캠퍼스가 없으면 기본 설정으로 만들어 director 만 갱신."""
    data = load_campus_config()
    if campus not in data:
        data[campus] = json.loads(json.dumps(_DEFAULT_CAMPUS_CFG))
    data[campus]["director"] = name.strip()
    with open(_CAMPUS_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ── 캠퍼스 표기 라벨 (정발/일산 양식: 상장에 박힌 "POLY <campus>") ──
# 정발 템플릿에는 "Jeongbal", 일산 전용 템플릿에는 기본 "Ilsan"이 새겨져 있다.
# 일산 캠퍼스 표기는 'Ilsan' 고정(전용 템플릿에 새김). campus_config.json의
# "campus_label" 값이 기본("Ilsan")과 다르면 렌더 시 치환(안전망, 일반적으로 미사용).
CAMPUS_LABEL_DEFAULT = "Ilsan"

# ── 정발/일산 양식 원장 서명 (상장 우하단 손글씨 서명 이미지) ──────
# 정발/일산 템플릿 우하단에는 'Charlotte Lee' 손글씨 서명이 이미지로 박혀 있다.
# campus_config.json의 캠퍼스별 "director" 값이 기본("Charlotte Lee")과 다르면,
# 렌더 시 그 이미지를 제거하고 새 원장 이름을 손글씨체(SIGNATURE_FONT)로 다시 그린다.
# (중계의 'Colin Park' 텍스트 사인 교체와 같은 개념. 단 여기선 서명이 이미지)
JUNGBAL_DIRECTOR_DEFAULT = "Charlotte Lee"

def set_campus_label(campus: str, label: str) -> None:
    """캠퍼스 표기 이름(상장의 'POLY <campus>')을 campus_config.json 에 저장(영구).
    파일에 캠퍼스가 없으면 기본 설정으로 만들어 campus_label 만 갱신."""
    data = load_campus_config()
    if campus not in data:
        data[campus] = json.loads(json.dumps(_DEFAULT_CAMPUS_CFG))
    data[campus]["campus_label"] = label.strip()
    with open(_CAMPUS_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_template_path(campus: str, award_type: str) -> str:
    """캠퍼스별 템플릿 경로. 없으면 기본 templates/ 폴더 사용."""
    campus_path = os.path.join(TEMPLATE_DIR, campus, f"{award_type}.pdf")
    if os.path.exists(campus_path):
        return campus_path
    return TEMPLATES[award_type]

# PDF → PNG 변환 해상도 (200 DPI → 2340×1655 px)
DPI = 200

# ── 원장 사인 (기본 템플릿 캠퍼스: 중계 등) ──────────────────
# 템플릿에 벡터 텍스트로 박힌 원장 이름(기본 "Colin Park").
# campus_config.json의 캠퍼스별 "director" 값이 이와 다르면, 렌더 시
# 해당 텍스트를 배경색으로 덮고 새 이름을 손글씨체로 다시 그린다.
# 기본값과 같으면(=Colin Park) 원본 템플릿(HolidayRegular)을 그대로 사용.
SIGNATURE_DEFAULT_NAME = "Colin Park"
SIGNATURE_FONT         = "DancingScript-Bold.ttf"   # HolidayRegular와 가장 유사한 보유 손글씨체

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
# 기본 템플릿 본문 이탤릭(중계 'Monthly/Level Test' 문구 치환용 — 템플릿 내장체와 동일 계열)
BODY_ITALIC_FONT = "PlayfairDisplay-Italic.ttf"

# 자동 감지 실패 시 폴백
DATE_LINE_Y_FALLBACK = 1295

# ── 분당엠폴리 전용 ──────────────────────────────────────────
BUNDANG_AWARD_TYPES = {"grammar_certification", "certificate_of_achievement",
                       "best_book_reflection", "voca_king"}
BUNDANG_KR_FONT      = "NanumGothic-Regular.ttf"   # 반코드·월·본문
BUNDANG_KR_FONT_BOLD = "NanumGothic-Bold.ttf"      # 학생이름·제목 월

# ── Voca King 전용 ───────────────────────────────────────────
# 템플릿(templates/분당엠폴리/voca_king.pdf)은 미작성본2(854×642px)를 그대로 깐 래스터로,
# "VOCA KING"·이름선·서명·디자인이 이미 박혀 있다. 변수(월·이름)만 벡터로 올린다.
# 좌표는 템플릿 픽셀 = PDF 포인트 1:1 (page 854×642).
BUNDANG_VOCA_TITLE_FONT = "Algerian.ttf"           # 상단 월 제목(=VOCA KING과 동일 서체)
VOCA_PAGE_W = 854
VOCA_PAGE_H = 642
# 월(예: APRIL): 작성본 측정 밴드 y85~139 중앙. baseline=캡 하단, 중앙 정렬.
VOCA_MONTH_BASELINE = 138.0
VOCA_MONTH_SIZE     = 82.0        # 캘리브레이션: 캡높이 ≈ 55px (작성본 APRIL y85~139와 일치)
# 템플릿에 박힌 기본 월("April")을 덮는 흰 사각형 (타이틀 배경=흰색, VOCA KING은 y178+이라 안전)
VOCA_MONTH_COVER    = (286.0, 78.0, 568.0, 150.0)
VOCA_MONTH_MAX_W    = 560.0       # VOCA KING 폭(218~632≈414)보다 약간 넓게 허용
# 이름(예: 5HO1_1 이소윤 (Alice Lee)): 이름선 y≈402 바로 위. baseline=선 위 ~12px.
VOCA_NAME_BASELINE  = 382.0
VOCA_NAME_SIZE      = 36.0
VOCA_NAME_MIN       = 18.0
VOCA_NAME_MAX_W     = 430.0       # 이름선 폭(209~644≈435)에 맞춰 넘치면 자동 축소
VOCA_TEXT_COLOR     = (0, 0, 0)   # 작성본의 월·이름은 검정
