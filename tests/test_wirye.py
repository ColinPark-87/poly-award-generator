# -*- coding: utf-8 -*-
"""위례 캠퍼스(중계 방식 공유) + 원장서명 교체 잔재(밑줄/점) 회귀 테스트."""
import os
import sys

import fitz
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import generator


def test_wirye_campus_config_matches_junggye():
    data = config.load_campus_config()
    assert "위례" in data
    jg, wr = data["중계"], data["위례"]
    assert wr["perfect_score_min"] == jg["perfect_score_min"]
    assert wr["honor_roll_min"] == jg["honor_roll_min"]
    assert wr["bw_min_lc"] == jg["bw_min_lc"]
    assert wr["award_labels"] == jg["award_labels"]
    # 기본 원장 = Colin Park → 서명 교체 없이 원본 템플릿 유지
    assert wr["director"] == config.SIGNATURE_DEFAULT_NAME


@pytest.mark.parametrize("award_type", sorted(config.TEMPLATES))
@pytest.mark.parametrize("name", ["Colin", "Grace Kim", "Alexandra Richardson"])
def test_director_swap_leaves_no_residue_and_keeps_line(award_type, name):
    """교체 후 baseline 아래~서명선 사이 띠에 원본 손글씨 잔재(밑줄/점)가 없어야 하고,
    서명선 자체는 살아 있어야 한다. 4종 기본 템플릿의 서명 블록 좌표는 동일
    (span 'Colin Park' bbox 538.2~656.7, baseline 481.1, 서명선 y≈495.4)."""
    doc = fitz.open(config.TEMPLATES[award_type])
    assert generator._apply_director_signature(doc, name) is True

    def dark_count(clip):
        pix = doc[0].get_pixmap(clip=clip, dpi=300)
        n, data = pix.n, pix.samples
        return sum(1 for i in range(0, len(data), n)
                   if data[i] + data[i + 1] + data[i + 2] < 380)

    # 잔재 띠: baseline+4pt ~ 서명선-1pt (원본 'Colin Park' 스워시가 남던 구간)
    residue = dark_count(fitz.Rect(538.2 - 14, 481.1 + 4, 656.7 + 14, 495.4 - 1))
    assert residue == 0, f"서명 교체 잔재 픽셀 {residue}개 (이름 앞 밑줄 버그)"
    # 서명선 보존
    line = dark_count(fitz.Rect(504.3, 494.8, 676.0, 496.2))
    assert line > 500, "서명선이 지워짐"
    doc.close()


def test_wirye_build_certificate(tmp_path):
    out = str(tmp_path / "wirye_ps.pdf")
    generator.build_certificate(
        award_type="perfect_score", english_name="Ethan Lee",
        student_class="GT3", month="July 2026", output_path=out, campus="위례",
    )
    assert os.path.getsize(out) > 10_000
