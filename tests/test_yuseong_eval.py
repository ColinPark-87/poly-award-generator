"""
유성 캠퍼스 상장 생성기 Eval
평가 기준: 중계 캠퍼스 수준 = 100% 기준
  Perfect Score : 평균 ≥ 100.0%
  Honor Roll    : 95.0% ≤ 평균 < 100.0%
  Best Writer   : LC ≥ 27 (GT/MGT/S/MAG 전 레벨 동일)
  Best SR       : 반별 GE 최고점 학생 1명
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import unicodedata
import pytest
from matcher import (
    clean_class_name,
    parse_student_name,
    select_winners,
    select_sr_winners,
)

# ── 중계 기준 (100% 벤치마크) ─────────────────────────────────
PS_MIN = 100.0
HR_MIN = 95.0
BW_LC  = {"GT": 27, "MGT": 27, "S": 27, "MAG": 27}


# ══════════════════════════════════════════════════════════════
# 1. 데이터 정제 (NFKC 정규화 / 전각 문자 처리)
# ══════════════════════════════════════════════════════════════

class TestDataCleaning:
    """엑셀 원본 데이터의 이상 문자 정제 검증"""

    def test_fullwidth_parentheses_in_class(self):
        """전각 괄호 '（）' → ASCII '()' 변환 후 스케줄 제거"""
        raw = "GT1-Pine（화목）"
        result = clean_class_name(raw)
        assert result == "GT1-Pine", f"got: {result!r}"

    def test_fullwidth_letters_in_class(self):
        """전각 알파벳 포함 반명 정규화"""
        raw = "ＧＴ１-Pine"
        result = clean_class_name(raw)
        assert result == "GT1-Pine", f"got: {result!r}"

    def test_korean_chars_stripped_from_class(self):
        """반명에 한국어 포함 시 제거"""
        raw = "GT1-보스턴"
        result = clean_class_name(raw)
        # 한국어 제거 후 'GT1-' 만 남거나 유사 ASCII 형태
        assert "보스턴" not in result, f"Korean not stripped: {result!r}"

    def test_schedule_removal(self):
        """'GT3 (MWF)3:10' → 'GT3'"""
        assert clean_class_name("GT3 (MWF)3:10") == "GT3"
        assert clean_class_name("MGT2(t/th)") == "MGT2"
        assert clean_class_name("S1 (M/W/F) 4:20") == "S1"

    def test_plant_class_unchanged(self):
        """유성 식물명 반명 — 정제 후 그대로 유지"""
        for cls in ["GT1-Pine", "MGT2-Oak", "S3-Iris", "MAG4-Holly", "LXE-Birch"]:
            assert clean_class_name(cls) == cls, f"changed: {cls!r}"

    def test_parse_name_fullwidth(self):
        """영문 이름 안 전각 문자 정규화"""
        k, e = parse_student_name("김마크 (Mark Ｋim)")
        assert e == "Mark Kim", f"got: {e!r}"

    def test_parse_name_normal(self):
        """정상 이름 파싱"""
        k, e = parse_student_name("박수아 (Sua Park)")
        assert k == "박수아"
        assert e == "Sua Park"

    def test_name_text_is_ascii_renderable(self):
        """생성될 name_text가 모두 렌더링 가능한 ASCII/Latin 범위인지 확인"""
        test_cases = [
            ("Sua Park", "GT1-Pine"),
            ("Mark Kim", "MGT2-Oak"),
            ("Brian Lee", "MGT1-Willow"),
        ]
        for name, cls in test_cases:
            name_text = f"{name} ({clean_class_name(cls)})"
            for ch in name_text:
                assert ord(ch) < 0x300 or unicodedata.category(ch).startswith('L'), \
                    f"Non-renderable char U+{ord(ch):04X} ({ch!r}) in {name_text!r}"


# ══════════════════════════════════════════════════════════════
# 2. Perfect Score 수상자 선정 (기준: 평균 ≥ 100%)
# ══════════════════════════════════════════════════════════════

class TestPerfectScore:
    """중계 기준 100% — Perfect Score 선정 검증"""

    BASE_ROWS = [
        {"class": "GT1-Pine",    "name": "이채원 (Chaewon Lee)",  "lc": 28, "average": 100.0},
        {"class": "GT1-Pine",    "name": "김서준 (Seojun Kim)",   "lc": 25, "average": 98.5},
        {"class": "MGT2-Oak",    "name": "박지유 (Jiyu Park)",    "lc": 27, "average": 100.0},
        {"class": "MGT2-Oak",    "name": "최하은 (Haeun Choi)",   "lc": 22, "average": 94.4},
        {"class": "S1-Jasmine",  "name": "정민준 (Minjun Jung)",  "lc": 27, "average": 96.7},
        {"class": "MAG3-Fir",    "name": "한지아 (Jia Han)",      "lc": 20, "average": 87.0},
    ]

    def test_exact_100_qualifies(self):
        """평균 정확히 100.0이면 PS 수상"""
        w = select_winners(self.BASE_ROWS, perfect_score_min=PS_MIN, honor_roll_min=HR_MIN,
                           best_writer_min_lc=BW_LC)
        ps_names = {s["english_name"] for s in w["perfect_score"]}
        assert "Chaewon Lee" in ps_names
        assert "Jiyu Park" in ps_names

    def test_below_100_not_ps(self):
        """평균 99.9 → PS 탈락"""
        rows = [{"class": "GT1-Pine", "name": "테스트 (Test Student)", "lc": 28, "average": 99.9}]
        w = select_winners(rows, perfect_score_min=PS_MIN, honor_roll_min=HR_MIN,
                           best_writer_min_lc=BW_LC)
        assert len(w["perfect_score"]) == 0

    def test_ps_not_in_honor_roll(self):
        """PS 수상자는 HR에 포함되지 않음"""
        w = select_winners(self.BASE_ROWS, perfect_score_min=PS_MIN, honor_roll_min=HR_MIN,
                           best_writer_min_lc=BW_LC)
        ps_names = {s["english_name"] for s in w["perfect_score"]}
        hr_names = {s["english_name"] for s in w["honor_roll"]}
        assert ps_names & hr_names == set()


# ══════════════════════════════════════════════════════════════
# 3. Honor Roll 수상자 선정 (기준: 95% ≤ 평균 < 100%)
# ══════════════════════════════════════════════════════════════

class TestHonorRoll:
    """중계 기준 100% — Honor Roll 선정 검증"""

    BASE_ROWS = [
        {"class": "GT2-Iris",   "name": "윤소율 (Soyul Yoon)",  "lc": 26, "average": 100.0},
        {"class": "GT2-Iris",   "name": "장다온 (Daon Jang)",   "lc": 27, "average": 97.8},
        {"class": "GT2-Iris",   "name": "김나은 (Naeun Kim)",   "lc": 22, "average": 95.0},
        {"class": "GT2-Iris",   "name": "이재원 (Jaewon Lee)",  "lc": 15, "average": 88.9},
        {"class": "MGT3-Holly", "name": "박서연 (Seoyeon Park)","lc": 27, "average": 95.6},
    ]

    def test_exact_95_qualifies(self):
        """평균 정확히 95.0이면 HR 수상"""
        w = select_winners(self.BASE_ROWS, perfect_score_min=PS_MIN, honor_roll_min=HR_MIN,
                           best_writer_min_lc=BW_LC)
        hr_names = {s["english_name"] for s in w["honor_roll"]}
        assert "Naeun Kim" in hr_names

    def test_below_95_not_hr(self):
        """평균 94.9 → HR 탈락"""
        rows = [{"class": "GT2-Iris", "name": "테스트 (Test B)", "lc": 27, "average": 94.9}]
        w = select_winners(rows, perfect_score_min=PS_MIN, honor_roll_min=HR_MIN,
                           best_writer_min_lc=BW_LC)
        assert len(w["honor_roll"]) == 0

    def test_average_stored_correctly(self):
        """HR 수상자 average 값이 반올림 없이 그대로 보존"""
        w = select_winners(self.BASE_ROWS, perfect_score_min=PS_MIN, honor_roll_min=HR_MIN,
                           best_writer_min_lc=BW_LC)
        hr = {s["english_name"]: s["average"] for s in w["honor_roll"]}
        assert hr["Naeun Kim"] == 95.0
        assert hr["Seoyeon Park"] == 95.6


# ══════════════════════════════════════════════════════════════
# 4. Best Writer 수상자 선정 (기준: LC ≥ 27, 반별 최고 LC)
# ══════════════════════════════════════════════════════════════

class TestBestWriter:
    """중계 기준 100% — Best Writer 선정 검증 (LC ≥ 27 전 레벨 동일)"""

    BASE_ROWS = [
        # GT1-Pine 반: LC 27 vs 26 → 27이 선정
        {"class": "GT1-Pine",   "name": "이윤서 (Yunseo Lee)",   "lc": 27, "average": 98.0},
        {"class": "GT1-Pine",   "name": "김도윤 (Doyun Kim)",    "lc": 26, "average": 99.0},
        # MGT2-Oak 반: LC 26 → 기준 미달 → 없음
        {"class": "MGT2-Oak",   "name": "최예린 (Yerin Choi)",   "lc": 26, "average": 97.0},
        # S1-Iris 반: LC 27 동점 → average 높은 쪽
        {"class": "S1-Iris",    "name": "장현준 (Hyunjun Jang)", "lc": 27, "average": 100.0},
        {"class": "S1-Iris",    "name": "박민서 (Minseo Park)",  "lc": 27, "average": 97.0},
        # MAG4-Holly: LC 30 → 선정
        {"class": "MAG4-Holly", "name": "한지우 (Jiwoo Han)",    "lc": 30, "average": 95.0},
    ]

    def test_lc_27_qualifies(self):
        """LC 정확히 27이면 BW 자격"""
        w = select_winners(self.BASE_ROWS, perfect_score_min=PS_MIN, honor_roll_min=HR_MIN,
                           best_writer_min_lc=BW_LC)
        bw_names = {s["english_name"] for s in w["best_writer"]}
        assert "Yunseo Lee" in bw_names

    def test_lc_26_not_qualified(self):
        """LC 26 → BW 탈락 (기준 27)"""
        w = select_winners(self.BASE_ROWS, perfect_score_min=PS_MIN, honor_roll_min=HR_MIN,
                           best_writer_min_lc=BW_LC)
        bw_names = {s["english_name"] for s in w["best_writer"]}
        assert "Yerin Choi" not in bw_names
        assert "Doyun Kim" not in bw_names

    def test_per_class_one_winner(self):
        """반별 1명만 수상"""
        w = select_winners(self.BASE_ROWS, perfect_score_min=PS_MIN, honor_roll_min=HR_MIN,
                           best_writer_min_lc=BW_LC)
        bw_classes = [s["class"] for s in w["best_writer"]]
        assert len(bw_classes) == len(set(bw_classes)), "반별 중복 수상자 발생"

    def test_tiebreak_by_average(self):
        """LC 동점 → average 높은 학생"""
        w = select_winners(self.BASE_ROWS, perfect_score_min=PS_MIN, honor_roll_min=HR_MIN,
                           best_writer_min_lc=BW_LC)
        s1_winner = next(s for s in w["best_writer"] if s["class"] == "S1-Iris")
        assert s1_winner["english_name"] == "Hyunjun Jang"

    def test_per_level_threshold_applied(self):
        """레벨별 LC 기준 dict 전달 시 정확히 적용"""
        custom_lc = {"GT": 27, "MGT": 26, "S": 27, "MAG": 27}
        w = select_winners(self.BASE_ROWS, perfect_score_min=PS_MIN, honor_roll_min=HR_MIN,
                           best_writer_min_lc=custom_lc)
        bw_names = {s["english_name"] for s in w["best_writer"]}
        # MGT2 기준 26으로 낮아졌으므로 Yerin Choi(LC 26) 수상
        assert "Yerin Choi" in bw_names


# ══════════════════════════════════════════════════════════════
# 5. Best SR 수상자 선정 (반별 GE 최고점 1명)
# ══════════════════════════════════════════════════════════════

class TestBestSR:
    """유성 캠퍼스 SR 수상자 선정 검증"""

    BASE_ROWS = [
        {"class": "GT1-Pine",   "english_name": "Sua Park",    "ge": 3.5},
        {"class": "GT1-Pine",   "english_name": "Tony Moon",   "ge": 4.2},
        {"class": "MGT2-Oak",   "english_name": "James Kim",   "ge": 5.1},
        {"class": "MGT2-Oak",   "english_name": "Stella Byun", "ge": 4.9},
        {"class": "S1-Jasmine", "english_name": "Alex Park",   "ge": 6.0},
    ]

    def test_highest_ge_per_class(self):
        """반별 GE 최고점 학생 선정"""
        winners = select_sr_winners(self.BASE_ROWS)
        by_class = {s["class"]: s["english_name"] for s in winners}
        assert by_class["GT1-Pine"] == "Tony Moon"      # 4.2 > 3.5
        assert by_class["MGT2-Oak"] == "James Kim"      # 5.1 > 4.9
        assert by_class["S1-Jasmine"] == "Alex Park"    # 단독

    def test_one_winner_per_class(self):
        """반별 수상자 1명"""
        winners = select_sr_winners(self.BASE_ROWS)
        classes = [s["class"] for s in winners]
        assert len(classes) == len(set(classes))

    def test_total_count(self):
        """수상자 수 = 반 수"""
        winners = select_sr_winners(self.BASE_ROWS)
        assert len(winners) == 3


# ══════════════════════════════════════════════════════════════
# 6. 종합 시나리오 — 유성 캠퍼스 실제 반명 사용
# ══════════════════════════════════════════════════════════════

class TestYuseongCampusScenario:
    """유성 식물명 반명으로 전체 파이프라인 검증"""

    YUSEONG_ROWS = [
        # GT 레벨
        {"class": "GT1-Pine",     "name": "남주원 (Juwon Nam)",    "lc": 28, "average": 100.0},
        {"class": "GT2-Iris",     "name": "오서아 (Seoa Oh)",      "lc": 27, "average": 96.3},
        {"class": "GT3-Oak",      "name": "임하랑 (Harang Im)",    "lc": 26, "average": 95.0},
        {"class": "GT4-Willow",   "name": "신예찬 (Yechan Shin)",  "lc": 20, "average": 82.0},
        # MGT 레벨
        {"class": "MGT1-Oak",     "name": "강지수 (Jisu Kang)",    "lc": 27, "average": 100.0},
        {"class": "MGT2-Birch",   "name": "백서진 (Seojin Baek)",  "lc": 27, "average": 97.8},
        {"class": "MGT3-Holly",   "name": "조민아 (Mina Jo)",      "lc": 24, "average": 89.0},
        # S 레벨
        {"class": "S1-Geranium",  "name": "문지호 (Jiho Moon)",    "lc": 27, "average": 98.2},
        {"class": "S2-Dahlia",    "name": "류채은 (Chaeeun Ryu)",  "lc": 19, "average": 91.0},
        # MAG 레벨
        {"class": "MAG1-Fir",     "name": "서주안 (Juan Seo)",     "lc": 30, "average": 100.0},
        {"class": "MAG2-Geranium","name": "전다인 (Dain Jeon)",    "lc": 27, "average": 95.5},
        # LXE (특수 반 — 수상 제외 대상 아님, 정상 처리)
        {"class": "LXE-Birch",    "name": "홍지원 (Jiwon Hong)",  "lc": 25, "average": 93.0},
    ]

    def test_ps_winners(self):
        """100% 기준 PS 수상자 — 중계 동일 기준"""
        w = select_winners(self.YUSEONG_ROWS, perfect_score_min=PS_MIN,
                           honor_roll_min=HR_MIN, best_writer_min_lc=BW_LC)
        ps_names = {s["english_name"] for s in w["perfect_score"]}
        assert ps_names == {"Juwon Nam", "Jisu Kang", "Juan Seo"}

    def test_hr_winners(self):
        """HR 수상자 검증"""
        w = select_winners(self.YUSEONG_ROWS, perfect_score_min=PS_MIN,
                           honor_roll_min=HR_MIN, best_writer_min_lc=BW_LC)
        hr_names = {s["english_name"] for s in w["honor_roll"]}
        assert "Seoa Oh" in hr_names      # 96.3
        assert "Harang Im" in hr_names    # 95.0
        assert "Seojin Baek" in hr_names  # 97.8
        assert "Jiho Moon" in hr_names    # 98.2
        assert "Dain Jeon" in hr_names    # 95.5

    def test_bw_lc27_filter(self):
        """LC 27 미만은 BW 탈락"""
        w = select_winners(self.YUSEONG_ROWS, perfect_score_min=PS_MIN,
                           honor_roll_min=HR_MIN, best_writer_min_lc=BW_LC)
        bw_names = {s["english_name"] for s in w["best_writer"]}
        assert "Yechan Shin" not in bw_names  # LC 20
        assert "Mina Jo" not in bw_names      # LC 24
        assert "Chaeeun Ryu" not in bw_names  # LC 19

    def test_class_names_ascii_clean(self):
        """유성 반명 정제 후 모두 ASCII"""
        for row in self.YUSEONG_ROWS:
            cleaned = clean_class_name(row["class"])
            for ch in cleaned:
                assert ord(ch) < 0x300, \
                    f"Non-ASCII in cleaned class: U+{ord(ch):04X} from {row['class']!r}"

    def test_no_cross_contamination(self):
        """PS/HR/BW 간 중복 없음"""
        w = select_winners(self.YUSEONG_ROWS, perfect_score_min=PS_MIN,
                           honor_roll_min=HR_MIN, best_writer_min_lc=BW_LC)
        ps = {s["english_name"] for s in w["perfect_score"]}
        hr = {s["english_name"] for s in w["honor_roll"]}
        assert ps & hr == set(), "PS와 HR 중복 발생"
