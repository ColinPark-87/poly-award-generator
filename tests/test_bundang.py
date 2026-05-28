import os
import fitz
import generator

ABC = "abcdefghijklmnopqrstuvwxyz ABCDEFGHIJKLMNOPQRSTUVWXYZ"
MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]
TPL = {
    "grammar_certification": "templates/분당엠폴리/grammar_certification.pdf",
    "certificate_of_achievement": "templates/분당엠폴리/certificate_of_achievement.pdf",
}

os.makedirs("test_output", exist_ok=True)


def _render(at, name, cls, month, out):
    generator.build_certificate(
        at, name, cls, f"{month} 2026", out,
        template_override=TPL[at], campus="분당엠폴리",
    )
    assert os.path.exists(out)


def test_name_alphabet_fits():
    for at in TPL:
        _render(at, ABC, "5HO1_1", "April", f"test_output/stress_{at}_abc.pdf")


def test_all_months():
    for m in MONTHS:
        _render("grammar_certification", "오민준 (Minjun Oh)", "5HO1_1", m,
                f"test_output/month_grammar_{m}.pdf")
        _render("certificate_of_achievement", "Grace Jo", "5HO2_2", m,
                f"test_output/month_level_{m}.pdf")
