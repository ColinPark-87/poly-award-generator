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


def select_winners(rows: list[dict[str, Any]]) -> dict[str, list[dict]]:
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

        if avg == 100.0:
            perfect_score.append(student)
        elif avg >= 95.0:
            honor_roll.append(student)

        # Best Writer: 학급별 LC 최고점, 동점시 Average 높은 1명
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
