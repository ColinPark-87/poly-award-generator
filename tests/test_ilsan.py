# -*- coding: utf-8 -*-
"""일산(Ilsan) 캠퍼스: 정발과 동일 양식 + 캠퍼스 표기 'Ilsan' + 표기 변경 옵션 회귀 테스트."""
import os
import sys
import json
import tempfile

import fitz
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as cfg
import generator

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ILSAN_DIR = os.path.join(cfg.TEMPLATE_DIR, "일산")
JUNGBAL_DIR = os.path.join(cfg.TEMPLATE_DIR, "정발")
TYPES = ["achievement_certificate", "monthly_test_winner", "level_test_winner"]


# ── 1) 설정: 일산 = 정발 양식(3종) + campus_label Ilsan ──────────────────
def test_ilsan_config_is_jungbal_style():
    c = cfg.get_campus_cfg("일산")
    assert c.get("campus_label") == "Ilsan"
    assert "score_weights" in c
    assert set(c["award_labels"]) == set(TYPES)


def test_ilsan_default_label_constant():
    assert cfg.CAMPUS_LABEL_DEFAULT == "Ilsan"


# ── 2) 전용 템플릿 존재 + Jeongbal→Ilsan 베이킹 확인 ──────────────────────
@pytest.mark.parametrize("t", TYPES)
def test_ilsan_templates_say_ilsan_not_jeongbal(t):
    p = os.path.join(ILSAN_DIR, f"{t}.pdf")
    assert os.path.exists(p), f"일산 템플릿 없음: {p}"
    txt = fitz.open(p)[0].get_text("text")
    assert "Ilsan" in txt and "Jeongbal" not in txt


@pytest.mark.parametrize("t", TYPES)
def test_jungbal_templates_unchanged(t):
    """정발 템플릿은 그대로 'Jeongbal' 유지(회귀 방지)."""
    txt = fitz.open(os.path.join(JUNGBAL_DIR, f"{t}.pdf"))[0].get_text("text")
    assert "Jeongbal" in txt and "Ilsan" not in txt


# ── 3) 생성: 일산 상장 PDF가 정상 생성되고 짤림/오류 없음 ────────────────
@pytest.mark.parametrize("t,extra", [
    ("achievement_certificate", None),
    ("monthly_test_winner", "MGT2"),
    ("level_test_winner", "S1"),
])
def test_ilsan_build_certificate(t, extra):
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "c.pdf")
        generator.build_certificate(
            award_type=t, english_name="Charlotte Lee", student_class="GT3",
            month="May 2026", output_path=out,
            template_override=cfg.get_template_path("일산", t),
            extra_text=extra, campus="일산",
        )
        assert os.path.exists(out) and os.path.getsize(out) > 5000


# ── 4) 표기 변경(override): 길어도 짤리지 않고 치환됨 ─────────────────────
def test_apply_campus_label_override_long():
    doc = fitz.open(os.path.join(ILSAN_DIR, "achievement_certificate.pdf"))
    ok = generator._apply_campus_label(doc, cfg.CAMPUS_LABEL_DEFAULT, "Ilsan Magnet")
    assert ok is True
    # 치환 후 텍스트층 검증
    txt = doc[0].get_text("text")
    assert "Ilsan Magnet" in txt
    # 페이지 폭 안에 들어가는지(짤림 방지): 모든 텍스트 span이 페이지 우측 경계 내
    pw = doc[0].rect.width
    for b in doc[0].get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                assert s["bbox"][2] <= pw + 1, f"우측 짤림: {s['text']!r}"
    doc.close()


def test_apply_campus_label_returns_false_when_token_absent():
    """토큰 없는 문서에는 변경 없이 False 반환(안전)."""
    doc = fitz.open(os.path.join(JUNGBAL_DIR, "achievement_certificate.pdf"))
    assert generator._apply_campus_label(doc, "ZZZNoSuchToken", "X") is False
    doc.close()


# ── 5) 원장 사인 변경 (중계처럼 원장 이름 변경 — 정발/일산 우하단 서명) ──────
def test_ilsan_director_default():
    """일산 기본 원장 사인은 'Charlotte Lee'(원본 유지)."""
    assert cfg.JUNGBAL_DIRECTOR_DEFAULT == "Charlotte Lee"
    assert cfg.get_campus_cfg("일산").get("director") == "Charlotte Lee"


@pytest.mark.parametrize("t", TYPES)
def test_apply_director_signature_replaces_and_fits(t):
    """원장 서명 이미지를 제거하고 새 이름을 그리며, 페이지 밖으로 짤리지 않는다."""
    doc = fitz.open(os.path.join(ILSAN_DIR, f"{t}.pdf"))
    assert generator._apply_jungbal_director_signature(doc, "Jiyoung Kim") is True
    page = doc[0]
    pw = page.rect.width
    found = False
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                if "Jiyoung Kim" in s["text"]:
                    found = True
                assert s["bbox"][2] <= pw + 1, f"우측 짤림: {s['text']!r}"
    assert found, "새 원장 이름이 그려지지 않음"
    doc.close()


def test_apply_director_signature_long_name_no_overflow():
    """긴 원장 이름도 자동 축소되어 페이지를 벗어나지 않는다."""
    doc = fitz.open(os.path.join(ILSAN_DIR, "achievement_certificate.pdf"))
    assert generator._apply_jungbal_director_signature(doc, "Alexandria Montgomery") is True
    pw = doc[0].rect.width
    for b in doc[0].get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                assert 0 <= s["bbox"][0] and s["bbox"][2] <= pw + 1
    doc.close()


def test_apply_director_signature_false_without_image():
    """서명 이미지가 없는 문서에는 변경 없이 False(안전)."""
    doc = fitz.open()
    doc.new_page(width=842, height=595)
    assert generator._apply_jungbal_director_signature(doc, "X") is False
    doc.close()


def test_ilsan_build_with_director_override():
    """원장 이름을 바꾼 일산 상장이 정상 생성된다."""
    import json
    orig = generator.config.get_campus_cfg
    generator.config.get_campus_cfg = (
        lambda c: {**orig(c), "director": "Jiyoung Kim"} if c == "일산" else orig(c)
    )
    try:
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "c.pdf")
            generator.build_certificate(
                "achievement_certificate", "Charlotte Lee", "GT3", "May 2026", out,
                template_override=cfg.get_template_path("일산", "achievement_certificate"),
                campus="일산",
            )
            assert os.path.getsize(out) > 5000
    finally:
        generator.config.get_campus_cfg = orig
