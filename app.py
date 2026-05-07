import os
import io
import re
import zipfile
import tempfile
import requests
import pandas as pd
import streamlit as st
from matcher import load_rows_from_excel, extract_month_from_filename, select_winners
from generator import build_certificate, pdf_to_preview_png

# ── 학년 → 레벨 정렬 키 ──────────────────────────────────────
_LEVEL_ORDER = {"GT": 1, "MGT": 2, "S": 3, "MAG": 4}

def _sort_key(s: dict) -> tuple:
    """학년 우선, 같은 학년이면 레벨(GT→MGT→S→MAG) 순 정렬."""
    m = re.match(r"^(GT|MGT|MAG|S)(\d+)", s["class"])
    if m:
        return (int(m.group(2)), _LEVEL_ORDER.get(m.group(1), 99))
    return (99, 99)

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

st.set_page_config(page_title="Poly 상장 생성기", layout="wide")
st.title("Poly 상장 생성기")
st.caption("성적 엑셀 파일을 업로드하면 상장 PDF를 자동 생성합니다.")


uploaded = st.file_uploader("성적 엑셀 파일 업로드 (.xlsx)", type=["xlsx"])

if uploaded:
    month = extract_month_from_filename(uploaded.name)
    if month:
        st.success(f"감지된 월: **{month}**")
    else:
        month = st.text_input("월을 직접 입력하세요 (예: April 2026)", value="")

    # ── 템플릿 페이지 선택 (선택사항) ──────────────────────
    with st.expander("템플릿 페이지 설정 (선택사항, 기본: 0·1·2)", expanded=False):
        st.caption("업로드된 PDF에 디자인 변형이 여러 페이지로 있을 경우 아래에서 선택하세요.")
        c1, c2, c3 = st.columns(3)
        page_ps = c1.number_input("Perfect Score 페이지", 0, 4, 0, key="page_ps")
        page_hr = c2.number_input("Honor Roll 페이지",    0, 4, 1, key="page_hr")
        page_bw = c3.number_input("Best Writer 페이지",   0, 4, 2, key="page_bw")
    _template_pages = {
        "perfect_score": int(page_ps),
        "honor_roll":    int(page_hr),
        "best_writer":   int(page_bw),
    }

    # ── 수상 기준 설정 (생성 전에 설정 → 버튼 클릭 → 해당 기준으로 검색) ──
    with st.expander("수상 기준 설정 (선택사항)", expanded=False):
        st.caption("기준을 바꾸면 그 점수에 해당하는 아이들이 수상자로 검색됩니다. 엑셀의 점수는 변경되지 않습니다.")
        cr1, cr2, cr3 = st.columns(3)
        ps_min = cr1.number_input(
            "Perfect Score 기준 평균 (%)", 0.0, 100.0, 100.0, step=0.5,
            help="이 평균 이상이면 Perfect Score",
        )
        hr_min = cr2.number_input(
            "Honor Roll 기준 평균 (%)", 0.0, 100.0, 95.0, step=0.5,
            help="이 평균 이상 ~ Perfect Score 미만이면 Honor Roll",
        )
        bw_min_lc = cr3.number_input(
            "Best Writer 최소 LC 점수", 0, 30, 0, step=1,
            help="반에서 1위여도 이 점수 미만이면 Best Writer 미수여 (0 = 제한 없음)",
        )

    if month and st.button("상장 생성하기", type="primary"):
        # 엑셀 임시 저장 후 파싱
        with st.spinner("수상자 선정 중..."):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                tmp.write(uploaded.read())
                tmp_path = tmp.name
            rows    = load_rows_from_excel(tmp_path)
            winners = select_winners(
                rows,
                perfect_score_min=float(ps_min),
                honor_roll_min=float(hr_min),
                best_writer_min_lc=int(bw_min_lc),
            )
            os.unlink(tmp_path)

        ps = sorted(winners["perfect_score"], key=_sort_key)
        hr = sorted(winners["honor_roll"],    key=_sort_key)
        bw = sorted(winners["best_writer"],   key=_sort_key)

        # PDF 생성
        with st.spinner("상장 PDF 생성 중..."):
            generated = []
            errors    = []
            with tempfile.TemporaryDirectory() as tmpdir:
                for award_type, folder, student_list in [
                    ("perfect_score", "Perfect_Score", ps),
                    ("honor_roll",    "Honor_Roll",    hr),
                    ("best_writer",   "Best_Writer",   bw),
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
                                page_index=_template_pages[award_type],
                            )
                            with open(out_path, "rb") as f:
                                pdf_bytes = f.read()
                            generated.append((award_type, folder, filename, pdf_bytes, s))
                        except Exception as e:
                            errors.append(f"{s['english_name']}: {e}")

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for _, folder, filename, pdf_bytes, _ in generated:
                zf.writestr(f"{folder}/{filename}", pdf_bytes)

        # 결과를 session_state에 저장 → 탭/드롭다운 조작해도 사라지지 않음
        st.session_state["result"] = {
            "ps": ps, "hr": hr, "bw": bw,
            "generated": generated,
            "errors": errors,
            "month": month,
            "zip_bytes": zip_buffer.getvalue(),
            "zip_name": f"{month.replace(' ', '_')}_상장.zip",
        }

    # ── 결과 표시 (session_state 기반, 버튼 재클릭과 무관하게 유지) ──
    if "result" in st.session_state:
        r  = st.session_state["result"]
        ps = r["ps"];  hr = r["hr"];  bw = r["bw"]
        generated = r["generated"]

        if r["errors"]:
            st.warning("일부 상장 생성 실패:\n" + "\n".join(r["errors"]))

        st.success(f"총 {len(generated)}개 상장 생성 완료!")

        # ── 수상자 명단 병렬 3컬럼 ──────────────────────────
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"#### 🏆 Perfect Score — {len(ps)}명")
            if ps:
                st.dataframe(
                    pd.DataFrame([{"이름": s["english_name"], "반": s["class"]}
                                  for s in ps]),
                    hide_index=True, use_container_width=True,
                )
        with col2:
            st.markdown(f"#### 🎖 Honor Roll — {len(hr)}명")
            if hr:
                st.dataframe(
                    pd.DataFrame([{"이름": s["english_name"], "반": s["class"],
                                   "평균": s["average"]} for s in hr]),
                    hide_index=True, use_container_width=True,
                )
        with col3:
            st.markdown(f"#### ✍️ Best Writer — {len(bw)}명")
            if bw:
                st.dataframe(
                    pd.DataFrame([{"이름": s["english_name"], "반": s["class"],
                                   "LC점수": s["lc"]} for s in bw]),
                    hide_index=True, use_container_width=True,
                )

        # ── ZIP 전체 다운로드 ────────────────────────────────
        st.markdown("---")
        st.download_button(
            label=f"전체 ZIP 다운로드 ({len(generated)}개)",
            data=r["zip_bytes"],
            file_name=r["zip_name"],
            mime="application/zip",
        )

        # ── 개별 다운로드 (탭 + 셀렉트박스) ──────────────────
        st.subheader("개별 다운로드")

        _groups = {
            "perfect_score": [(fn, pb, s) for (at, _, fn, pb, s) in generated if at == "perfect_score"],
            "honor_roll":    [(fn, pb, s) for (at, _, fn, pb, s) in generated if at == "honor_roll"],
            "best_writer":   [(fn, pb, s) for (at, _, fn, pb, s) in generated if at == "best_writer"],
        }

        tab_ps, tab_hr, tab_bw = st.tabs([
            f"🏆 Perfect Score ({len(_groups['perfect_score'])}명)",
            f"🎖 Honor Roll ({len(_groups['honor_roll'])}명)",
            f"✍️ Best Writer ({len(_groups['best_writer'])}명)",
        ])

        for tab, award_type in zip(
            [tab_ps, tab_hr, tab_bw],
            ["perfect_score", "honor_roll", "best_writer"],
        ):
            group = _groups[award_type]
            with tab:
                if not group:
                    st.info("해당 수상자 없음")
                    continue
                options = [f"{s['english_name']}  ({s['class']})" for _, _, s in group]
                sel     = st.selectbox("수상자 선택", options, key=f"sel_{award_type}")
                sel_idx = options.index(sel)
                filename, pdf_bytes, s = group[sel_idx]

                col_img, col_info = st.columns([2, 1])
                with col_img:
                    st.image(pdf_to_preview_png(pdf_bytes), use_container_width=True)
                with col_info:
                    st.markdown(f"### {s['english_name']}")
                    st.caption(s["class"])
                    if award_type == "honor_roll":
                        st.metric("평균", f"{s['average']:.2f}%")
                    elif award_type == "best_writer":
                        st.metric("LC 점수", s["lc"])
                    st.download_button(
                        label="PDF 다운로드",
                        data=pdf_bytes,
                        file_name=filename,
                        mime="application/pdf",
                        key=f"dl_{award_type}",
                    )
