import os
import io
import re
import zipfile
import tempfile
import requests
import pandas as pd
import streamlit as st
from matcher import (load_rows_from_excel, extract_month_from_filename,
                     select_winners, load_sr_from_csv, select_sr_winners)
from generator import build_certificate, pdf_to_preview_png
import config as cfg

# ── 학년 → 레벨 정렬 키 ──────────────────────────────────────
_LEVEL_ORDER = {"GT": 1, "MGT": 2, "S": 3, "MAG": 4}

def _sort_key(s: dict) -> tuple:
    m = re.match(r"^(GT|MGT|MAG|S)(\d+)", s["class"])
    if m:
        return (int(m.group(2)), _LEVEL_ORDER.get(m.group(1), 99))
    return (99, 99)

def _sr_sort_key(s: dict) -> str:
    return s["class"]

# ── 폰트 자동 다운로드 ──────────────────────────────────────
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

# ── 캠퍼스 선택 ─────────────────────────────────────────
_CAMPUS_COLORS = {
    "중계":     "#1B3F7A",
    "광명":     "#1E6B4A",
    "일산":     "#6B3A1E",
    "목동":     "#4A1E6B",
    "목동매그넷": "#1E556B",
}
_DEFAULT_COLOR = "#2C2C2C"

if "campus_list" not in st.session_state:
    st.session_state["campus_list"] = ["중계", "광명", "일산", "목동", "목동매그넷"]

_c1, _c2, _c3 = st.columns([1, 1, 2])
campus = _c1.selectbox("캠퍼스 선택", st.session_state["campus_list"], index=0, key="campus")

with _c2:
    st.markdown("<div style='margin-top:28px'>", unsafe_allow_html=True)
    if st.button("＋ 캠퍼스 추가", key="btn_add_campus"):
        st.session_state["show_campus_input"] = True
        st.session_state["show_delete_input"]  = False
    st.markdown("</div>", unsafe_allow_html=True)

with _c3:
    st.markdown("<div style='margin-top:28px'>", unsafe_allow_html=True)
    if st.button("🗑 캠퍼스 삭제", key="btn_del_campus"):
        st.session_state["show_delete_input"] = True
        st.session_state["show_campus_input"] = False
        st.session_state["del_pw_wrong"]      = False
    st.markdown("</div>", unsafe_allow_html=True)

if st.session_state.get("show_campus_input"):
    _in_col, _ok_col = st.columns([2, 1])
    new_campus = _in_col.text_input("새 캠퍼스 이름", key="new_campus_name", label_visibility="collapsed", placeholder="캠퍼스 이름 입력")
    with _ok_col:
        st.markdown("<div style='margin-top:4px'>", unsafe_allow_html=True)
        if st.button("추가", key="btn_confirm_campus"):
            name = new_campus.strip()
            if name and name not in st.session_state["campus_list"]:
                st.session_state["campus_list"].append(name)
            st.session_state["show_campus_input"] = False
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

if st.session_state.get("show_delete_input"):
    _pw_col, _ok_col, _cancel_col = st.columns([2, 1, 1])
    pw = _pw_col.text_input("비밀번호 입력", type="password", key="del_pw",
                             label_visibility="collapsed", placeholder="비밀번호 입력")
    with _ok_col:
        if st.button("삭제 확인", key="btn_confirm_del"):
            if pw == "poly7659!!":
                if campus in st.session_state["campus_list"] and len(st.session_state["campus_list"]) > 1:
                    st.session_state["campus_list"].remove(campus)
                st.session_state["show_delete_input"] = False
                st.session_state["del_pw_wrong"]      = False
                st.rerun()
            else:
                st.session_state["del_pw_wrong"] = True
    with _cancel_col:
        if st.button("취소", key="btn_cancel_del"):
            st.session_state["show_delete_input"] = False
            st.session_state["del_pw_wrong"]      = False
            st.rerun()
    if st.session_state.get("del_pw_wrong"):
        st.error("비밀번호가 틀렸습니다.")

# 캠퍼스 배너
_color = _CAMPUS_COLORS.get(campus, _DEFAULT_COLOR)
st.markdown(f"""
<div style="
    background: linear-gradient(135deg, {_color} 0%, {_color}cc 100%);
    border-radius: 12px;
    padding: 18px 28px;
    margin: 8px 0 16px 0;
    display: flex;
    align-items: center;
    gap: 12px;
">
    <span style="font-size:2rem;">📍</span>
    <div>
        <div style="color:rgba(255,255,255,0.7); font-size:0.8rem; letter-spacing:0.1em; text-transform:uppercase;">POLY LANGUAGE INSTITUTE</div>
        <div style="color:white; font-size:1.6rem; font-weight:700; line-height:1.2;">{campus} 캠퍼스</div>
    </div>
</div>
""", unsafe_allow_html=True)

# 캠퍼스 설정 로드
_campus_cfg = cfg.get_campus_cfg(campus)
_bw_def     = _campus_cfg["bw_min_lc"]

# ══════════════════════════════════════════════════════════
# 상단: 2분할 업로드
# ══════════════════════════════════════════════════════════
up_col1, up_col2 = st.columns(2)

with up_col1:
    st.subheader("📝 Monthly Test")
    uploaded_monthly = st.file_uploader("성적 엑셀 업로드 (.xlsx)", type=["xlsx"], key="monthly_upload")
    if uploaded_monthly:
        month = extract_month_from_filename(uploaded_monthly.name)
        if month:
            st.success(f"감지된 월: **{month}**")
        else:
            month = st.text_input("월을 직접 입력하세요 (예: April 2026)", value="", key="month_input")
    else:
        month = ""

with up_col2:
    st.subheader("⭐ Best SR")
    uploaded_sr = st.file_uploader("Star Summary Report CSV 업로드 (.csv)", type=["csv"], key="sr_upload")
    if uploaded_sr:
        st.success(f"파일 감지: **{uploaded_sr.name}**")
    _MONTHS = ["January","February","March","April","May","June",
               "July","August","September","October","November","December"]
    import datetime
    sr_m_col, sr_y_col = st.columns(2)
    sr_month_name = sr_m_col.selectbox("SR 상장 월", _MONTHS,
                                        index=datetime.date.today().month - 1,
                                        key="sr_month")
    sr_year       = sr_y_col.number_input("연도", 2020, 2100,
                                           datetime.date.today().year,
                                           key="sr_year")
    sr_month = f"{sr_month_name} {int(sr_year)}"

# ══════════════════════════════════════════════════════════
# 수상 기준 설정 + 생성 버튼
# ══════════════════════════════════════════════════════════
_award_labels = _campus_cfg.get("award_labels", {
    "perfect_score": "Perfect Score",
    "honor_roll":    "Honor Roll",
    "best_writer":   "Best Writer",
    "best_sr":       "Best SR",
})

# 캠퍼스 요약 카드 (항상 표시)
st.info(
    f"**{campus} 캠퍼스** | "
    f"Perfect Score ≥ {_campus_cfg['perfect_score_min']:.0f}%　"
    f"Honor Roll ≥ {_campus_cfg['honor_roll_min']:.0f}%　"
    f"Best Writer LC ≥ GT {_bw_def.get('GT',27)} / MGT {_bw_def.get('MGT',27)} / "
    f"S {_bw_def.get('S',27)} / MAG {_bw_def.get('MAG',27)}"
)

with st.expander("수상 기준 수정", expanded=False):
    st.caption("변경하면 해당 점수 기준으로 수상자가 검색됩니다. 엑셀의 점수는 변경되지 않습니다.")
    cr1, cr2 = st.columns(2)
    # 캠퍼스별로 key를 달리해 캠퍼스 변경 시 값이 초기화되도록 함
    ps_min = cr1.number_input("Perfect Score 기준 평균 (%)", 0.0, 100.0,
                               value=float(_campus_cfg["perfect_score_min"]),
                               step=0.5, key=f"ps_min_{campus}")
    hr_min = cr2.number_input("Honor Roll 기준 평균 (%)",    0.0, 100.0,
                               value=float(_campus_cfg["honor_roll_min"]),
                               step=0.5, key=f"hr_min_{campus}")

    st.markdown("**Best Writer 레벨별 최소 LC 점수** (0 = 제한 없음)")
    bw_col1, bw_col2, bw_col3, bw_col4 = st.columns(4)
    bw_gt  = bw_col1.number_input("GT",  0, 30, value=_bw_def.get("GT",  27), step=1, key=f"bw_gt_{campus}")
    bw_mgt = bw_col2.number_input("MGT", 0, 30, value=_bw_def.get("MGT", 27), step=1, key=f"bw_mgt_{campus}")
    bw_s   = bw_col3.number_input("S",   0, 30, value=_bw_def.get("S",   27), step=1, key=f"bw_s_{campus}")
    bw_mag = bw_col4.number_input("MAG", 0, 30, value=_bw_def.get("MAG", 27), step=1, key=f"bw_mag_{campus}")
    bw_min_lc = {"GT": int(bw_gt), "MGT": int(bw_mgt), "S": int(bw_s), "MAG": int(bw_mag)}

can_generate = bool((uploaded_monthly and month) or uploaded_sr)
if st.button("상장 생성하기", type="primary", disabled=not can_generate):

    generated = []   # (award_type, folder, filename, pdf_bytes, student)
    errors    = []

    # ── Monthly Test 처리 ──────────────────────────────
    ps = hr = bw = []
    if uploaded_monthly and month:
        with st.spinner("Monthly Test 수상자 선정 중..."):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                tmp.write(uploaded_monthly.read())
                tmp_path = tmp.name
            rows    = load_rows_from_excel(tmp_path)
            winners = select_winners(
                rows,
                perfect_score_min=float(ps_min),
                honor_roll_min=float(hr_min),
                best_writer_min_lc=bw_min_lc,
            )
            os.unlink(tmp_path)

        ps = sorted(winners["perfect_score"], key=_sort_key)
        hr = sorted(winners["honor_roll"],    key=_sort_key)
        bw = sorted(winners["best_writer"],   key=_sort_key)

        with st.spinner("Monthly Test 상장 PDF 생성 중..."):
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
                                template_override=cfg.get_template_path(campus, award_type),
                            )
                            with open(out_path, "rb") as f:
                                pdf_bytes = f.read()
                            generated.append((award_type, folder, filename, pdf_bytes, s))
                        except Exception as e:
                            errors.append(f"{s['english_name']}: {e}")

    # ── Best SR 처리 ───────────────────────────────────
    sr_list = []
    if uploaded_sr:
        with st.spinner("Best SR 수상자 선정 중..."):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode="wb") as tmp:
                tmp.write(uploaded_sr.read())
                tmp_path = tmp.name
            sr_rows = load_sr_from_csv(tmp_path)
            sr_list = sorted(select_sr_winners(sr_rows), key=_sr_sort_key)
            os.unlink(tmp_path)

        with st.spinner("Best SR 상장 PDF 생성 중..."):
            with tempfile.TemporaryDirectory() as tmpdir:
                for s in sr_list:
                    safe_name  = s["english_name"].replace(" ", "_")
                    safe_class = s["class"].replace(" ", "_").replace("/", "-")
                    filename   = f"{safe_name}_{safe_class}.pdf"
                    out_path   = os.path.join(tmpdir, filename)
                    try:
                        build_certificate(
                            award_type="best_sr",
                            english_name=s["english_name"],
                            student_class=s["class"],
                            month=sr_month,
                            output_path=out_path,
                            template_override=cfg.get_template_path(campus, "best_sr"),
                        )
                        with open(out_path, "rb") as f:
                            pdf_bytes = f.read()
                        generated.append(("best_sr", "Best_SR", filename, pdf_bytes, s))
                    except Exception as e:
                        errors.append(f"{s['english_name']} (SR): {e}")

    # ZIP 생성
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for _, folder, filename, pdf_bytes, _ in generated:
            zf.writestr(f"{folder}/{filename}", pdf_bytes)

    st.session_state["result"] = {
        "ps": ps, "hr": hr, "bw": bw, "sr": sr_list,
        "generated": generated,
        "errors": errors,
        "month": month,
        "zip_bytes": zip_buffer.getvalue(),
        "zip_name": f"{(month or 'SR').replace(' ', '_')}_상장.zip",
    }

# ══════════════════════════════════════════════════════════
# 결과 표시
# ══════════════════════════════════════════════════════════
if "result" in st.session_state:
    r         = st.session_state["result"]
    ps        = r["ps"];  hr = r["hr"];  bw = r["bw"];  sr = r["sr"]
    generated = r["generated"]

    if r["errors"]:
        st.warning("일부 상장 생성 실패:\n" + "\n".join(r["errors"]))

    st.success(f"총 {len(generated)}개 상장 생성 완료!")

    # ── 수상자 명단 4컬럼 병렬 ────────────────────────────
    st.markdown("---")
    st.caption("학생 이름을 클릭하면 아래에 상장 미리보기와 다운로드가 표시됩니다.")
    col1, col2, col3, col4 = st.columns(4)

    ev_ps = ev_hr = ev_bw = ev_sr = None

    with col1:
        st.markdown(f"#### 🏆 {_award_labels['perfect_score']} — {len(ps)}명")
        if ps:
            ev_ps = st.dataframe(
                pd.DataFrame([{"이름": s["english_name"], "반": s["class"]} for s in ps]),
                hide_index=True, use_container_width=True,
                selection_mode="single-row", on_select="rerun", key="sel_ps",
            )

    with col2:
        st.markdown(f"#### 🎖 {_award_labels['honor_roll']} — {len(hr)}명")
        if hr:
            ev_hr = st.dataframe(
                pd.DataFrame([{"이름": s["english_name"], "반": s["class"], "평균": s["average"]} for s in hr]),
                hide_index=True, use_container_width=True,
                selection_mode="single-row", on_select="rerun", key="sel_hr",
            )

    with col3:
        st.markdown(f"#### ✍️ {_award_labels['best_writer']} — {len(bw)}명")
        if bw:
            ev_bw = st.dataframe(
                pd.DataFrame([{"이름": s["english_name"], "반": s["class"], "LC": s["lc"]} for s in bw]),
                hide_index=True, use_container_width=True,
                selection_mode="single-row", on_select="rerun", key="sel_bw",
            )

    with col4:
        st.markdown(f"#### ⭐ {_award_labels['best_sr']} — {len(sr)}명")
        if sr:
            ev_sr = st.dataframe(
                pd.DataFrame([{"이름": s["english_name"], "반": s["class"], "GE": s["ge"]} for s in sr]),
                hide_index=True, use_container_width=True,
                selection_mode="single-row", on_select="rerun", key="sel_sr",
            )

    # ── 클릭된 학생 파악 ──────────────────────────────────
    _sel_student = None
    _sel_award   = None
    if ev_ps and ev_ps.selection.rows:
        _sel_student = ps[ev_ps.selection.rows[0]]
        _sel_award   = "perfect_score"
    elif ev_hr and ev_hr.selection.rows:
        _sel_student = hr[ev_hr.selection.rows[0]]
        _sel_award   = "honor_roll"
    elif ev_bw and ev_bw.selection.rows:
        _sel_student = bw[ev_bw.selection.rows[0]]
        _sel_award   = "best_writer"
    elif ev_sr and ev_sr.selection.rows:
        _sel_student = sr[ev_sr.selection.rows[0]]
        _sel_award   = "best_sr"

    # ── ZIP 전체 다운로드 ──────────────────────────────────
    st.markdown("---")
    st.download_button(
        label=f"전체 ZIP 다운로드 ({len(generated)}개)",
        data=r["zip_bytes"],
        file_name=r["zip_name"],
        mime="application/zip",
        key="zip_dl",
    )

    # ── 개별 미리보기 / 다운로드 ──────────────────────────
    st.markdown("---")
    _AWARD_LABEL = {
        "perfect_score": f"🏆 {_award_labels['perfect_score']}",
        "honor_roll":    f"🎖 {_award_labels['honor_roll']}",
        "best_writer":   f"✍️ {_award_labels['best_writer']}",
        "best_sr":       f"⭐ {_award_labels['best_sr']}",
    }
    if _sel_student is None:
        st.info("위 명단에서 학생을 클릭하면 상장 미리보기와 다운로드가 표시됩니다.")
    else:
        for at, _, fn, pb, s in generated:
            if at == _sel_award \
                    and s["english_name"] == _sel_student["english_name"] \
                    and s["class"] == _sel_student["class"]:
                col_img, col_info = st.columns([2, 1])
                with col_img:
                    st.image(pdf_to_preview_png(pb), use_container_width=True)
                with col_info:
                    st.markdown(f"**{_AWARD_LABEL[at]}**")
                    st.markdown(f"### {s['english_name']}")
                    st.caption(s["class"])
                    if at == "honor_roll":
                        st.metric("평균", f"{s['average']:.2f}%")
                    elif at == "best_writer":
                        st.metric("LC 점수", s["lc"])
                    elif at == "best_sr":
                        st.metric("GE", s["ge"])
                    st.download_button(
                        label="PDF 다운로드",
                        data=pb,
                        file_name=fn,
                        mime="application/pdf",
                        key="dl_selected",
                    )
                break
