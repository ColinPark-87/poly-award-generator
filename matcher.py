import csv
import re
import openpyxl
from typing import Any

MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]

COL_CLASS   = 1
COL_NAME    = 4
COL_LC      = 9   # Lang. Composition
COL_AVERAGE = 12


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
        name_raw = row[COL_NAME]
        lc_raw   = row[COL_LC]
        avg_raw  = row[COL_AVERAGE]
        cls_raw  = row[COL_CLASS]
        if not name_raw or avg_raw is None:
            continue
        try:
            lc  = int(lc_raw) if lc_raw is not None else 0
            avg = float(avg_raw)
        except (TypeError, ValueError):
            continue
        rows.append({
            "class":   str(cls_raw).strip() if cls_raw else "",
            "name":    str(name_raw).strip(),
            "lc":      lc,
            "average": avg,
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


def select_winners(
    rows: list[dict[str, Any]],
    perfect_score_min: float = 100.0,
    honor_roll_min:    float = 95.0,
    best_writer_min_lc: int  = 0,
) -> dict[str, list[dict]]:
    """
    수상자 선정.
    perfect_score_min  : 이 값 이상이면 Perfect Score (기본 100)
    honor_roll_min     : 이 값 이상 ~ perfect_score_min 미만이면 Honor Roll (기본 95)
    best_writer_min_lc : Best Writer 자격 최소 LC 점수 (기본 0 = 제한 없음)
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
        # best_writer_min_lc 미만이면 후보 제외
        if lc >= best_writer_min_lc:
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
