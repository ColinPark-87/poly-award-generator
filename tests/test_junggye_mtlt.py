"""중계 MT/LT 분리 — LT 'Level Test' 문구 치환 검증."""
import os
import sys

import fitz
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import generator

TPL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
PS_TPL  = os.path.join(TPL_DIR, "perfect_score.pdf")
HR_TPL  = os.path.join(TPL_DIR, "honor_roll.pdf")
BW_TPL  = os.path.join(TPL_DIR, "best_writer.pdf")


def test_font_asset_present():
    """치환에 쓰는 PlayfairDisplay-Italic 폰트가 존재해야 함."""
    fp = os.path.join(config.FONT_DIR, config.BODY_ITALIC_FONT)
    assert os.path.exists(fp), f"폰트 없음: {fp}"
    # 대문자 'L' 글리프 포함 여부 (Level)
    f = fitz.Font(fontfile=fp)
    assert f.has_glyph(ord("L")) and f.has_glyph(ord("T"))


@pytest.mark.parametrize("tpl", [PS_TPL, HR_TPL, BW_TPL])
def test_apply_test_label_replaces_monthly_with_level(tpl):
    """벡터 단계에서 'Monthly Test' → 'Level Test' 로 바뀌어야 함."""
    doc = fitz.open(tpl)
    assert "Monthly Test" in doc[0].get_text()
    ok = generator._apply_test_label(doc, "Level")
    assert ok is True
    txt = doc[0].get_text()
    assert "Level Test" in txt
    assert "Monthly Test" not in txt
    doc.close()


def test_apply_test_label_no_match_returns_false():
    """'Monthly Test' 가 없으면 False(변경 없음)."""
    doc = fitz.open()
    doc.new_page()
    assert generator._apply_test_label(doc, "Level") is False
    doc.close()


def _phrase_band_pixels(pdf_path):
    """생성 상장(이미지 PDF)에서 문구 띠 영역 픽셀 바이트 반환."""
    d = fitz.open(pdf_path)
    pg = d[0]
    W, H = pg.rect.width, pg.rect.height
    # 'In recognition ... Test' 문구는 이름 밑줄 바로 아래 (대략 세로 중앙 하단)
    clip = fitz.Rect(W * 0.15, H * 0.52, W * 0.88, H * 0.62)
    pix = pg.get_pixmap(matrix=fitz.Matrix(2, 2), clip=clip)
    data = pix.samples
    d.close()
    return data


def test_build_certificate_level_differs_from_monthly(tmp_path):
    """중계 LT(Level) 상장과 MT(Monthly) 상장의 래스터 출력이 실제로 달라야 함
    (= 문구가 최종 PDF에 반영됨). 동시에 둘 다 정상 생성."""
    mt = str(tmp_path / "ps_monthly.pdf")
    lt = str(tmp_path / "ps_level.pdf")
    common = dict(award_type="perfect_score", english_name="Andy Kim",
                  student_class="GT1", month="April 2026", campus="중계")
    generator.build_certificate(output_path=mt, test_label="Monthly", **common)
    generator.build_certificate(output_path=lt, test_label="Level", **common)

    assert os.path.getsize(mt) > 1000
    assert os.path.getsize(lt) > 1000
    # 문구 띠 영역이 서로 달라야 함 (Monthly vs Level)
    assert _phrase_band_pixels(mt) != _phrase_band_pixels(lt)


def test_build_certificate_default_is_monthly(tmp_path):
    """test_label 미지정 시 기본 Monthly(=원본 유지)와 동일해야 함."""
    default = str(tmp_path / "ps_default.pdf")
    monthly = str(tmp_path / "ps_monthly.pdf")
    common = dict(award_type="perfect_score", english_name="Andy Kim",
                  student_class="GT1", month="April 2026", campus="중계")
    generator.build_certificate(output_path=default, **common)
    generator.build_certificate(output_path=monthly, test_label="Monthly", **common)
    assert _phrase_band_pixels(default) == _phrase_band_pixels(monthly)
