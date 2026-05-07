import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from matcher import parse_student_name, extract_month_from_filename, select_winners


def test_parse_english_name():
    k, e = parse_student_name("최윤아 (Elena Choi)")
    assert k == "최윤아"
    assert e == "Elena Choi"


def test_parse_no_english():
    k, e = parse_student_name("홍길동")
    assert k == "홍길동"
    assert e == "홍길동"


def test_extract_month():
    assert extract_month_from_filename("April 2026 Monthly Test (ELE)_종합 성적.xlsx") == "April 2026"
    assert extract_month_from_filename("March 2026 Monthly Test.xlsx") == "March 2026"


def test_extract_month_unknown():
    assert extract_month_from_filename("성적.xlsx") == ""


def test_perfect_score():
    rows = [
        {"class": "GT1", "name": "김지안 (Jay Kim)",   "lc": 22, "average": 100.0},
        {"class": "GT1", "name": "최윤아 (Elena Choi)", "lc": 26, "average": 95.56},
        {"class": "GT1", "name": "이지율 (Mia Lee)",    "lc": 15, "average": 64.44},
    ]
    w = select_winners(rows)
    assert len(w["perfect_score"]) == 1
    assert w["perfect_score"][0]["english_name"] == "Jay Kim"


def test_honor_roll_excludes_perfect_score():
    rows = [
        {"class": "GT1", "name": "김지안 (Jay Kim)",   "lc": 22, "average": 100.0},
        {"class": "GT1", "name": "최윤아 (Elena Choi)", "lc": 26, "average": 95.56},
        {"class": "GT1", "name": "이지율 (Mia Lee)",    "lc": 15, "average": 64.44},
    ]
    w = select_winners(rows)
    assert len(w["honor_roll"]) == 1
    assert w["honor_roll"][0]["english_name"] == "Elena Choi"


def test_best_writer_per_class():
    rows = [
        {"class": "GT1", "name": "진은우 (Jace Jin)",  "lc": 27, "average": 97.78},
        {"class": "GT1", "name": "최윤아 (Elena Choi)","lc": 26, "average": 95.56},
        {"class": "GT2", "name": "최세영 (Joy Choi)",  "lc": 27, "average": 93.33},
    ]
    w = select_winners(rows)
    classes = [s["class"] for s in w["best_writer"]]
    assert "GT1" in classes
    assert "GT2" in classes


def test_best_writer_tiebreak():
    rows = [
        {"class": "MAG2", "name": "김태율 (Ethan Kim)", "lc": 27, "average": 100.0},
        {"class": "MAG2", "name": "최하음 (Evie Choi)", "lc": 27, "average": 95.56},
    ]
    w = select_winners(rows)
    assert len(w["best_writer"]) == 1
    assert w["best_writer"][0]["english_name"] == "Ethan Kim"
