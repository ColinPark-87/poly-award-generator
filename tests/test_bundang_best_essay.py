# -*- coding: utf-8 -*-
"""분당엠폴리 Best Essay (Certificate of Excellence) 상장 + 명단 로더 테스트."""
import os
import fitz
import generator
import matcher

TPL = "templates/분당엠폴리/best_essay.pdf"
ROSTER = r"C:/Users/user/Desktop/Colin 작업폴더/Raw/0618/★Best Essay 1.xlsx"

os.makedirs("test_output", exist_ok=True)


def _render(name, cls, title, out):
    generator.build_certificate(
        "best_essay", name, cls, title, out,
        template_override=TPL, campus="분당엠폴리",
    )
    assert os.path.exists(out) and os.path.getsize(out) > 1000


def test_template_exists():
    assert os.path.exists(TPL), "best_essay 템플릿 누락 (build_bestessay_template.py 실행 필요)"


def test_default_title_keeps_baked():
    """기본 제목이면 베이킹된 제목을 유지(재기입 안 함) — 생성만 검증."""
    _render("정선우 (Daniel Jung)", "5HO1_1",
            "2026 Spring Semester|Best Essay 1", "test_output/be_default.pdf")


def test_edited_title_and_long_name():
    """제목 편집 + 긴 이름 자동 축소 — 오버플로우/에러 없이 생성."""
    _render("아주긴이름홍길동 (Verylongname Hong)", "7LE3_M-1",
            "2026 Fall Semester|Best Essay 2", "test_output/be_edited.pdf")


def test_roster_loader_all_35():
    """'List' 시트 전원(35명) 로드 + 반코드·이름 파싱."""
    if not os.path.exists(ROSTER):
        return  # 원본 명단 없는 환경(클라우드 등)에선 스킵
    rows = matcher.load_bundang_best_essay(ROSTER)
    assert len(rows) == 35, f"기대 35명, 실제 {len(rows)}명"
    assert rows[0]["class"] == "5HO1_1"
    assert "(" in rows[0]["full_name"]
    assert all(r["class"] and r["full_name"] for r in rows)


def test_blue_M_baked_in_template():
    """템플릿에 'MPOLY'의 M 이 파란색(#004EA2)으로 베이킹돼 있는지 검증."""
    doc = fitz.open(TPL)
    page = doc[0]
    blue_M = False
    for b in page.get_text("dict")["blocks"]:
        if b["type"] != 0:
            continue
        for l in b["lines"]:
            for s in l["spans"]:
                if s["text"].strip() == "M":
                    c = s["color"]
                    r, g, bl = (c >> 16) & 255, (c >> 8) & 255, c & 255
                    if bl > 120 and r < 80:   # 파란 계열
                        blue_M = True
    doc.close()
    assert blue_M, "MPOLY의 파란 M 미검출"
