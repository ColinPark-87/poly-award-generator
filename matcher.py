import csv
import re
import openpyxl
from typing import Any

MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]

COL_CLASS         = 1
COL_LEVEL         = 2
COL_NAME          = 4
COL_LC            = 9   # Lang. Composition
COL_AVERAGE       = 12
COL_CLASS_RANKING = 13
COL_LEVEL_RANKING = 14


def clean_class_name(cls: str) -> str:
    """클래스명에서 요일/시간 표기 제거.
    예: 'GT3 (MWF)3:10'   → 'GT3'
        'MGT2(t/th)'       → 'MGT2'
        'S1 (M/W/F) 4:20'  → 'S1'
        'GT2 4:40'         → 'GT2'
    """
    cleaned = re.sub(r'\s*\([^)]*\)', '', cls)   # 괄호 그룹 제거
    cleaned = re.sub(r'\s*\d+:\d+', '', cleaned) # 시간 표기(4:40 등) 제거
    return cleaned.strip() if cleaned.strip() else cls


def parse_student_name(full_name: str) -> tuple[str, str]:
    """'최윤아 (Elena Choi)' → ('최윤아', 'Elena Choi')"""
    match = re.search(r'\(([^)]+)\)', str(full_name))
    if match:
        korean = str(full_name)[:match.start()].strip()
        english = match.group(1).strip()
        return korean, english
    return str(full_name).strip(), str(full_name).strip()


def extract_month_from_filename(filename: str) -> str:
    """파일명에서 'April 2026' 형태 추출"""
    pattern = r'(' + '|'.join(MONTHS) + r')\s+(\d{4})'
    match = re.search(pattern, filename)
    if match:
        return f"{match.group(1)} {match.group(2)}"
    return ""


def load_rows_from_excel(file_path: str) -> list[dict[str, Any]]:
    wb = openpyxl.load_workbook(file_path, data_only=True)
    ws = wb.active
    rows = []
    for row in ws.iter_rows(min_row=3, values_only=True):
        name_raw  = row[COL_NAME]
        lc_raw    = row[COL_LC]
        avg_raw   = row[COL_AVERAGE]
        cls_raw   = row[COL_CLASS]
        level_raw = row[COL_LEVEL] if len(row) > COL_LEVEL else None
        cls_rank  = row[COL_CLASS_RANKING] if len(row) > COL_CLASS_RANKING else None
        lvl_rank  = row[COL_LEVEL_RANKING] if len(row) > COL_LEVEL_RANKING else None
        if not name_raw or avg_raw is None:
            continue
        try:
            lc  = int(lc_raw) if lc_raw is not None else 0
            avg = float(avg_raw)
        except (TypeError, ValueError):
            continue
        rows.append({
            "class":         clean_class_name(str(cls_raw).strip()) if cls_raw else "",
            "level":         str(level_raw).strip() if level_raw else "",
            "name":          str(name_raw).strip(),
            "lc":            lc,
            "average":       avg,
            "class_ranking": str(cls_rank).strip() if cls_rank else "",
            "level_ranking": str(lvl_rank).strip() if lvl_rank else "",
        })
    return rows


def _parse_ge(ge_str) -> float | None:
    """GE 값 파싱. '-' 또는 비어있으면 None, '>12.9' 형태도 처리."""
    s = str(ge_str).strip() if ge_str else ""
    if s in ("-", ""):
        return None
    s = s.lstrip(">")
    try:
        return float(s)
    except ValueError:
        return None


def load_sr_from_csv(file_path: str) -> list[dict[str, Any]]:
    """
    Star Summary Report CSV 파싱.
    - Student 컬럼: '학번, 이름' → 이름만 추출
    - GE '-' 또는 test 반은 제외
    """
    rows = []
    with open(file_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cls        = row.get("Class/Group", "").strip()
            student_raw = row.get("Student", "").strip()
            ge_raw     = row.get("GE", "-")

            if not cls or not student_raw:
                continue
            if cls.lower().startswith("test"):
                continue

            ge = _parse_ge(ge_raw)
            if ge is None:          # 점수 없는 학생·반 제외
                continue

            # '학번, 이름' → 이름만
            parts = student_raw.split(",", 1)
            name  = parts[1].strip() if len(parts) == 2 else student_raw

            rows.append({
                "class":        cls,
                "english_name": name,
                "ge":           ge,
            })
    return rows


def select_sr_winners(rows: list[dict[str, Any]]) -> list[dict]:
    """Class/Group별 GE 최고점 학생 1명 선정. 점수 없는 반은 자동 제외."""
    winner_map: dict[str, dict] = {}
    for row in rows:
        cls = row["class"]
        if cls not in winner_map or row["ge"] > winner_map[cls]["ge"]:
            winner_map[cls] = row
    return list(winner_map.values())


def _get_level(cls: str) -> str:
    """클래스명에서 레벨 접두어 추출. 예: 'GT3' → 'GT', 'MGT2' → 'MGT'"""
    m = re.match(r"^(GT|MGT|MAG|S)", cls)
    return m.group(1) if m else ""


def select_winners(
    rows: list[dict[str, Any]],
    perfect_score_min: float = 100.0,
    honor_roll_min:    float = 95.0,
    best_writer_min_lc = 0,
) -> dict[str, list[dict]]:
    """
    수상자 선정.
    perfect_score_min  : 이 값 이상이면 Perfect Score (기본 100)
    honor_roll_min     : 이 값 이상 ~ perfect_score_min 미만이면 Honor Roll (기본 95)
    best_writer_min_lc : Best Writer 자격 최소 LC 점수.
                         int → 전 레벨 공통 기준
                         dict → {'GT': 27, 'MGT': 25, 'S': 20, 'MAG': 20} 형태로 레벨별 기준
    """
    perfect_score = []
    honor_roll    = []
    best_writer_map: dict[str, dict] = {}

    for row in rows:
        avg = row["average"]
        lc  = row["lc"]
        cls = row["class"]
        korean, english = parse_student_name(row["name"])
        student = {
            "korean_name":  korean,
            "english_name": english,
            "class":        cls,
            "average":      avg,
            "lc":           lc,
        }

        if avg >= perfect_score_min:
            perfect_score.append(student)
        elif avg >= honor_roll_min:
            honor_roll.append(student)

        # Best Writer: 학급별 LC 최고점, 동점시 Average 높은 1명
        if isinstance(best_writer_min_lc, dict):
            level  = _get_level(cls)
            min_lc = best_writer_min_lc.get(level, 0)
        else:
            min_lc = best_writer_min_lc

        if lc >= min_lc:
            if cls not in best_writer_map:
                best_writer_map[cls] = student
            else:
                cur = best_writer_map[cls]
                if lc > cur["lc"] or (lc == cur["lc"] and avg > cur["average"]):
                    best_writer_map[cls] = student

    return {
        "perfect_score": perfect_score,
        "honor_roll":    honor_roll,
        "best_writer":   list(best_writer_map.values()),
    }


def select_jungbal_winners(rows: list[dict[str, Any]]) -> dict[str, list[dict]]:
    """
    정발 캠퍼스 수상자 선정.

    로직:
    1) Class Ranking "1/N" 학생 = 반 1등 목록 수집
    2) 반 1등을 level(Col 2)별로 그룹화
    3) 레벨 내 반 1등 중 평균 최고(동점 시 LC 높은 순) → Achievement Certificate
       나머지 반 1등 → Monthly Test Winner
    (Note: Excel Level Ranking 열은 전체 캠퍼스 통합 순위라 사용하지 않음)
    """
    # ── Step 1: 반 1등 수집 ──────────────────────────────
    class_1st: dict[str, dict] = {}   # class → row
    for row in rows:
        if str(row["class_ranking"]).startswith("1/"):
            class_1st[row["class"]] = row

    # ── Step 2: 레벨별 그룹화 ────────────────────────────
    from collections import defaultdict
    by_level: dict[str, list[dict]] = defaultdict(list)
    for row in class_1st.values():
        by_level[row["level"]].append(row)

    # ── Step 3: 레벨 내 최고 학생 → Achievement, 나머지 → Monthly ──
    achievement: list[dict] = []
    monthly_winner: list[dict] = []

    def _make_student(row: dict) -> dict:
        korean, english = parse_student_name(row["name"])
        return {
            "korean_name":   korean,
            "english_name":  english,
            "class":         row["class"],
            "level":         row["level"],
            "average":       row["average"],
            "lc":            row["lc"],
            "class_ranking": row["class_ranking"],
            "level_ranking": row["level_ranking"],
        }

    for level_rows in by_level.values():
        # 평균 내림차순 → LC 내림차순으로 최고 학생 선정
        best = max(level_rows, key=lambda r: (r["average"] + r["lc"], r["lc"]))
        for row in level_rows:
            s = _make_student(row)
            if row["class"] == best["class"]:
                achievement.append(s)
            else:
                monthly_winner.append(s)

    return {
        "achievement_certificate": achievement,
        "monthly_test_winner":     monthly_winner,
    }
