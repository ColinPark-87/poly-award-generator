import os
import io
import zipfile
import tempfile
import requests
import streamlit as st
from matcher import load_rows_from_excel, extract_month_from_filename, select_winners
from generator import build_certificate

# ── 폰트 자동 다운로드 (클라우드 환경에서도 동작) ──────────────
def _ensure_fonts():
    font_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
    os.makedirs(font_dir, exist_ok=True)
    fonts = {
        "DancingScript-Bold.ttf": "https://github.com/google/fonts/raw/main/ofl/dancingscript/static/DancingScript-Bold.ttf",
        "Montserrat-Bold.ttf":    "https://github.com/google/fonts/raw/main/ofl/montserrat/static/Montserrat-Bold.ttf",
    }
    for name, url in fonts.items():
        path = os.path.join(font_dir, name)
        if not os.path.exists(path):
            r = requests.get(url, timeout=30)
            if r.ok:
                open(path, "wb").write(r.content)

_ensure_fonts()

st.set_page_config(page_title="Poly 상장 생성기", layout="centered")
st.title("Poly 상장 생성기")
st.caption("성적 엑셀 파일을 업로드하면 상장 PDF를 자동 생성합니다.")

uploaded = st.file_uploader("성적 엑셀 파일 업로드 (.xlsx)", type=["xlsx"])

if uploaded:
    month = extract_month_from_filename(uploaded.name)
    if month:
        st.success(f"감지된 월: **{month}**")
    else:
        month = st.text_input("월을 직접 입력하세요 (예: April 2026)", value="")

    if month and st.button("상장 생성하기", type="primary"):
        # 엑셀 임시 저장 후 파싱
        with st.spinner("수상자 선정 중..."):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                tmp.write(uploaded.read())
                tmp_path = tmp.name
            rows    = load_rows_from_excel(tmp_path)
            winners = select_winners(rows)
            os.unlink(tmp_path)

        # 결과 요약
        col1, col2, col3 = st.columns(3)
        col1.metric("Perfect Score", f"{len(winners['perfect_score'])}명")
        col2.metric("Honor Roll",    f"{len(winners['honor_roll'])}명")
        col3.metric("Best Writer",   f"{len(winners['best_writer'])}명")

        with st.expander("Perfect Score 수상자 목록"):
            for s in winners["perfect_score"]:
                st.write(f"- **{s['english_name']}** ({s['class']})")

        with st.expander("Honor Roll 수상자 목록"):
            for s in winners["honor_roll"]:
                st.write(f"- **{s['english_name']}** ({s['class']}) — avg {s['average']}")

        with st.expander("Best Writer 수상자 목록"):
            for s in winners["best_writer"]:
                st.write(f"- **{s['english_name']}** ({s['class']}) — LC {s['lc']}점")

        # PDF 생성 (메모리에 저장)
        with st.spinner("상장 PDF 생성 중..."):
            generated = []   # (award_type, folder, filename, pdf_bytes, student)
            errors    = []
            with tempfile.TemporaryDirectory() as tmpdir:
                for award_type, folder, student_list in [
                    ("perfect_score", "Perfect_Score", winners["perfect_score"]),
                    ("honor_roll",    "Honor_Roll",    winners["honor_roll"]),
                    ("best_writer",   "Best_Writer",   winners["best_writer"]),
                ]:
                    for s in student_list:
                        safe_name  = s["english_name"].replace(" ", "_")
                        safe_class = s["class"].replace(" ", "_").replace("/", "-")
                        filename   = f"{safe_name}_{safe_class}.pdf"
                        out_path   = os.path.join(tmpdir, filename)
                        try:
                            build_certificate(
                                award_type=award_type,
                                english_name=s["english_name"],
                                student_class=s["class"],
                                month=month,
                                output_path=out_path,
                            )
                            with open(out_path, "rb") as f:
                                pdf_bytes = f.read()
                            generated.append((award_type, folder, filename, pdf_bytes, s))
                        except Exception as e:
                            errors.append(f"{s['english_name']}: {e}")

        if errors:
            st.warning("일부 상장 생성 실패:\n" + "\n".join(errors))

        total = len(generated)
        st.success(f"총 {total}개 상장 생성 완료!")

        # ── ZIP 다운로드 ──────────────────────────────────
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for _, folder, filename, pdf_bytes, _ in generated:
                zf.writestr(f"{folder}/{filename}", pdf_bytes)

        zip_name = f"{month.replace(' ', '_')}_상장.zip"
        st.download_button(
            label=f"전체 ZIP 다운로드 ({total}개)",
            data=zip_buffer.getvalue(),
            file_name=zip_name,
            mime="application/zip",
        )

        # ── 개별 다운로드 ─────────────────────────────────
        st.markdown("---")
        st.subheader("개별 다운로드")

        for award_label, award_type in [
            ("Perfect Score", "perfect_score"),
            ("Honor Roll",    "honor_roll"),
            ("Best Writer",   "best_writer"),
        ]:
            group = [(fn, pb, s) for (at, _, fn, pb, s) in generated if at == award_type]
            if not group:
                continue
            with st.expander(f"{award_label} — {len(group)}명"):
                for filename, pdf_bytes, s in group:
                    col_name, col_btn = st.columns([3, 1])
                    col_name.write(f"**{s['english_name']}** ({s['class']})")
                    col_btn.download_button(
                        label="PDF",
                        data=pdf_bytes,
                        file_name=filename,
                        mime="application/pdf",
                        key=filename,
                    )
