import os
import io
import re
import zipfile
import tempfile
import requests
import pandas as pd
import streamlit as st
from matcher import (load_rows_from_excel, extract_month_from_filename,
                     select_winners, load_sr_from_csv, select_sr_winners,
                     select_jungbal_winners, JUNGBAL_DEFAULT_WEIGHTS,
                     load_sr_from_excel_yuseong,
                     load_bundang_level_top, load_bundang_grammar)
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
        "DancingScript-Bold.ttf":  "https://github.com/google/fonts/raw/main/ofl/dancingscript/static/DancingScript-Bold.ttf",
        "Montserrat-Bold.ttf":     "https://github.com/google/fonts/raw/main/ofl/montserrat/static/Montserrat-Bold.ttf",
        "PinyonScript-Regular.ttf":    "https://github.com/google/fonts/raw/main/ofl/pinyonscript/PinyonScript-Regular.ttf",
        "GreatVibes-Regular.ttf":      "https://github.com/google/fonts/raw/main/ofl/greatvibes/GreatVibes-Regular.ttf",
        "PlayfairDisplay-Regular.ttf": "https://github.com/google/fonts/raw/main/ofl/playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf",
    }
    for name, url in fonts.items():
        path = os.path.join(font_dir, name)
        if not os.path.exists(path):
            r = requests.get(url, timeout=30)
            if r.ok:
                open(path, "wb").write(r.content)

_ensure_fonts()


def _ensure_yuseong_fonts():
    """유성 PDF 템플릿에서 폰트를 추출해 fonts/ 폴더에 저장."""
    import fitz
    font_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
    tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "유성")
    specs = [
        ("perfect_score.pdf", "Corsiva",   "MonotypeCorsiva.ttf"),
        ("honor_roll.pdf",    "Trebuchet", "TrebuchetMS-Bold.ttf"),
        ("best_sr.pdf",       "BaskOld",   "BaskOldFace.ttf"),
    ]
    for tmpl_file, keyword, target_name in specs:
        target_path = os.path.join(font_dir, target_name)
        if os.path.exists(target_path):
            continue
        tmpl_path = os.path.join(tmpl_dir, tmpl_file)
        if not os.path.exists(tmpl_path):
            continue
        try:
            doc = fitz.open(tmpl_path)
            for f in doc.get_page_fonts(0, full=True):
                if keyword.lower() in f[3].lower():
                    fd = doc.extract_font(f[0])
                    if fd and fd[3]:
                        with open(target_path, "wb") as fp:
                            fp.write(fd[3])
                    break
            doc.close()
        except Exception:
            pass

_ensure_yuseong_fonts()

st.set_page_config(page_title="Poly 상장 생성기", page_icon="🏅", layout="wide")

from poly_theme import (inject_poly_theme, poly_header, poly_campus_banner,
                        poly_section, poly_kpi_row, poly_footer)
inject_poly_theme()

poly_header(
    title="상장 생성기",
    subtitle="월간 평가 결과로 4종 상장을 자동 생성합니다.",
    eyebrow="POLY ACADEMY · CERTIFICATES",
)

# ── 캠퍼스 선택 ─────────────────────────────────────────
_JUNGBAL_CAMPUS = "정발"   # 정발 전용 로직을 적용할 캠퍼스 이름
_YUSEONG_CAMPUS = "유성"   # 유성 전용 SR Excel 로직

if "campus_list" not in st.session_state:
    st.session_state["campus_list"] = ["중계", "광명", "일산", "목동", "목동매그넷", "유성", "정발", "분당엠폴리"]

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
            if pw == "01077644950":
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
import datetime as _dt
poly_campus_banner(campus, term=f"{_dt.date.today().year}년 {_dt.date.today().month}월")

# 캠퍼스 설정 로드
_campus_cfg = cfg.get_campus_cfg(campus)
_bw_def     = _campus_cfg["bw_min_lc"]

# ══════════════════════════════════════════════════════════
# 상장 템플릿 확인
# ══════════════════════════════════════════════════════════
poly_section("00 · 상장 템플릿 확인", "현재 캠퍼스에 적용된 템플릿을 미리 확인합니다. 생성과 무관한 미리보기입니다.")

with st.expander("템플릿 미리보기 펼치기", expanded=False):
    _tmpl_labels = _campus_cfg.get("award_labels", {
        "perfect_score": "Perfect Score",
        "honor_roll":    "Honor Roll",
        "best_writer":   "Best Writer",
        "best_sr":       "Best SR",
    })
    _tmpl_types = list(_tmpl_labels.keys())
    _tmpl_cols  = st.columns(len(_tmpl_types))
    for _tcol, _at in zip(_tmpl_cols, _tmpl_types):
        _tmpl_path = cfg.get_template_path(campus, _at)
        _lbl = _tmpl_labels.get(_at, _at)
        with _tcol:
            st.markdown(f"**{_lbl}**")
            if os.path.exists(_tmpl_path):
                with open(_tmpl_path, "rb") as _tf:
                    _tmpl_bytes = _tf.read()
                st.image(pdf_to_preview_png(_tmpl_bytes, preview_width=400),
                         use_container_width=True)
                _campus_tmpl = os.path.join(cfg.TEMPLATE_DIR, campus, f"{_at}.pdf")
                if os.path.exists(_campus_tmpl):
                    st.caption("✅ 캠퍼스 전용 템플릿")
                else:
                    st.caption("📋 기본 템플릿 사용 중")
            else:
                st.warning("템플릿 파일 없음")

# ══════════════════════════════════════════════════════════
# 분당엠폴리 전용 흐름 (Level Top + Grammar)
# ══════════════════════════════════════════════════════════
if campus == "분당엠폴리":
    poly_section(
        "01 · 명단 업로드",
        "분당엠폴리 종합 엑셀 1개를 업로드하세요. "
        "Level Top 상장은 초등TOP·중등TOP 시트의 Level TOP=1 학생, "
        "Grammar 상장은 종합성적관리 시트의 Eng. Mechanics 만점자에게 발급됩니다.",
    )
    _BD_MONTHS = ["January", "February", "March", "April", "May", "June",
                  "July", "August", "September", "October", "November", "December"]
    _bd_today = _dt.date.today()
    _bd_default_month = f"{_BD_MONTHS[_bd_today.month - 1]} {_bd_today.year}"
    _bd_month = st.text_input("월 (예: April 2026)", value=_bd_default_month, key="bd_month")
    _bd_file  = st.file_uploader("엑셀 업로드 (.xlsx)", type=["xlsx"], key="bd_excel")

    if st.button("상장 생성", key="bd_gen", type="primary") and _bd_file:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as _tmp:
            _tmp.write(_bd_file.read())
            _bd_path = _tmp.name
        try:
            lvl_list  = load_bundang_level_top(_bd_path)
            gram_list = load_bundang_grammar(_bd_path)
        finally:
            os.unlink(_bd_path)

        _bd_generated = []   # (award_type, folder, filename, pdf_bytes, student)
        _bd_errors    = []
        with st.spinner(f"상장 생성 중... (Level Top {len(lvl_list)} + Grammar {len(gram_list)})"):
            with tempfile.TemporaryDirectory() as _td:
                _bd_jobs = [
                    ("certificate_of_achievement", "Level_Top", lvl_list, "english_name"),
                    ("grammar_certification",      "Grammar",   gram_list, "full_name"),
                ]
                for _at, _folder, _students, _name_key in _bd_jobs:
                    _tmpl = cfg.get_template_path(campus, _at)
                    for _s in _students:
                        _safe = f"{_s['english_name'].replace(' ', '_')}_{_s['class'].replace('/', '-')}"
                        _fn   = f"{_safe}.pdf"
                        _out  = os.path.join(_td, _fn)
                        try:
                            build_certificate(
                                award_type=_at,
                                english_name=_s[_name_key],
                                student_class=_s["class"],
                                month=_bd_month,
                                output_path=_out,
                                template_override=_tmpl,
                                campus=campus,
                            )
                            with open(_out, "rb") as _f:
                                _bd_generated.append((_at, _folder, _fn, _f.read(), _s))
                        except Exception as _e:
                            _bd_errors.append(f"{_s['full_name']}: {_e}")

        _bd_zip = io.BytesIO()
        with zipfile.ZipFile(_bd_zip, "w", zipfile.ZIP_DEFLATED) as _zf:
            for _, _folder, _fn, _bytes, _ in _bd_generated:
                _zf.writestr(f"{_folder}/{_fn}", _bytes)

        st.session_state["bd_result"] = {
            "lvl": lvl_list, "gram": gram_list,
            "generated": _bd_generated, "errors": _bd_errors,
            "month": _bd_month,
            "zip_bytes": _bd_zip.getvalue(),
            "zip_name": f"분당엠폴리_{_bd_month.replace(' ', '_')}_상장.zip",
        }

    if "bd_result" in st.session_state:
        _r = st.session_state["bd_result"]
        if _r["errors"]:
            st.warning("일부 생성 실패:\n" + "\n".join(_r["errors"]))
        st.success(f"총 {len(_r['generated'])}개 생성 "
                   f"(Level Top {len(_r['lvl'])} · Grammar {len(_r['gram'])})")

        poly_section("02 · 수상자 명단", "학생 이름을 클릭하면 상장 미리보기와 다운로드가 표시됩니다.")

        _bd_lvl_items  = [g for g in _r["generated"] if g[0] == "certificate_of_achievement"]
        _bd_gram_items = [g for g in _r["generated"] if g[0] == "grammar_certification"]
        _ev_lvl = _ev_gram = None
        _bc1, _bc2 = st.columns(2, gap="small")
        with _bc1:
            st.markdown(
                f'<div class="poly-card-head"><span class="ttl">🥇 Level Top 상장</span>'
                f'<span class="cnt">{len(_bd_lvl_items)}</span></div>', unsafe_allow_html=True)
            if _bd_lvl_items:
                _ev_lvl = st.dataframe(
                    pd.DataFrame([{"반": s["class"], "이름": s["full_name"]} for (*_, s) in _bd_lvl_items]),
                    hide_index=True, use_container_width=True,
                    selection_mode="single-row", on_select="rerun", key="bd_sel_lvl",
                )
            else:
                st.markdown('<div class="poly-empty">해당 학생 없음</div>', unsafe_allow_html=True)
        with _bc2:
            st.markdown(
                f'<div class="poly-card-head"><span class="ttl">🏆 Grammar 상장</span>'
                f'<span class="cnt">{len(_bd_gram_items)}</span></div>', unsafe_allow_html=True)
            if _bd_gram_items:
                _ev_gram = st.dataframe(
                    pd.DataFrame([{"반": s["class"], "이름": s["full_name"]} for (*_, s) in _bd_gram_items]),
                    hide_index=True, use_container_width=True,
                    selection_mode="single-row", on_select="rerun", key="bd_sel_gram",
                )
            else:
                st.markdown('<div class="poly-empty">해당 학생 없음</div>', unsafe_allow_html=True)

        _bd_sel = None
        if _ev_lvl and _ev_lvl.selection.rows:
            _bd_sel = _bd_lvl_items[_ev_lvl.selection.rows[0]]
        elif _ev_gram and _ev_gram.selection.rows:
            _bd_sel = _bd_gram_items[_ev_gram.selection.rows[0]]

        poly_section("03 · 다운로드", "전체 ZIP 또는 개별 PDF를 다운로드할 수 있습니다.")
        st.download_button(f"전체 ZIP 다운로드 ({len(_r['generated'])}개)", _r["zip_bytes"],
                           file_name=_r["zip_name"], mime="application/zip",
                           type="primary", key="bd_zip_dl")
        st.markdown("<br>", unsafe_allow_html=True)
        if _bd_sel is None:
            st.info("위 명단에서 학생을 클릭하면 상장 미리보기와 다운로드가 표시됩니다.")
        else:
            _at, _folder, _fn, _bytes, _s = _bd_sel
            _ci, _cf = st.columns([2, 1])
            with _ci:
                st.image(pdf_to_preview_png(_bytes, preview_width=900), use_container_width=True)
            with _cf:
                _tt = "🥇 Level Top 상장" if _at == "certificate_of_achievement" else "🏆 Grammar 상장"
                st.markdown(f"**{_tt}**")
                st.markdown(f"### {_s['full_name']}")
                st.caption(_s["class"])
                st.download_button("PDF 다운로드", _bytes, file_name=_fn,
                                   mime="application/pdf", key="bd_dl_sel")

    poly_footer()
    st.stop()


# ══════════════════════════════════════════════════════════
# 상단: 2분할 업로드
# ══════════════════════════════════════════════════════════
_use_sr = (campus != _JUNGBAL_CAMPUS)   # 정발은 Best SR 미사용
_hint   = "Monthly Test 결과 엑셀(ELE / LX)을 업로드하세요." if not _use_sr else \
          "Monthly Test 결과 엑셀(ELE / LX)과 Best SR CSV를 업로드하세요."
poly_section("01 · 데이터 업로드", _hint)

if _use_sr:
    up_col1, up_col2 = st.columns(2, gap="medium")
else:
    up_col1, up_col2 = st.columns([2, 1], gap="medium")

with up_col1:
    st.markdown('<div class="poly-drop"><b>성적 엑셀</b><span class="hint">&nbsp;·&nbsp;.xlsx&nbsp;·&nbsp;MT/LT 모두 가능, 여러 파일 동시 업로드</span></div>', unsafe_allow_html=True)
    uploaded_excel_files = st.file_uploader(
        "성적 엑셀 업로드 (.xlsx)", type=["xlsx"],
        accept_multiple_files=True, key="excel_upload"
    )

# 하위 호환 — 기존 코드에서 uploaded_ele / uploaded_lx 를 참조하는 부분 대응
uploaded_ele = uploaded_excel_files[0] if uploaded_excel_files else None
uploaded_lx  = uploaded_excel_files[1] if len(uploaded_excel_files) > 1 else None

# 월 감지: 파일명에서 순서대로 시도 → 없으면 직접 입력
month = ""
for _uf in uploaded_excel_files:
    _m = extract_month_from_filename(_uf.name)
    if _m:
        month = _m
        break
if uploaded_excel_files and not month:
    month = st.text_input("월을 직접 입력하세요 (예: April 2026)", value="", key="month_input")
if month:
    st.success(f"감지된 월: **{month}**")

import datetime
if _use_sr:
    with up_col2:
        _is_yuseong_sr = (campus == _YUSEONG_CAMPUS)
        _sr_fmt  = ".xlsx" if _is_yuseong_sr else ".csv UTF-8"
        _sr_type = ["xlsx"] if _is_yuseong_sr else ["csv"]
        _sr_lbl  = f"Star Summary Report {'Excel' if _is_yuseong_sr else 'CSV'} 업로드"
        st.markdown(f'<div class="poly-drop"><b>Best SR</b><span class="hint">&nbsp;·&nbsp;{_sr_fmt}</span></div>', unsafe_allow_html=True)
        uploaded_sr = st.file_uploader(_sr_lbl, type=_sr_type, key="sr_upload")
        if uploaded_sr:
            st.success(f"파일 감지: **{uploaded_sr.name}**")
        _MONTHS = ["January","February","March","April","May","June",
                   "July","August","September","October","November","December"]
        sr_m_col, sr_y_col = st.columns(2)
        sr_month_name = sr_m_col.selectbox("SR 상장 월", _MONTHS,
                                            index=datetime.date.today().month - 1,
                                            key="sr_month")
        sr_year       = sr_y_col.number_input("연도", 2020, 2100,
                                               datetime.date.today().year,
                                               key="sr_year")
        sr_month = f"{sr_month_name} {int(sr_year)}"
else:
    uploaded_sr = None
    sr_month = f"January {datetime.date.today().year}"

# ══════════════════════════════════════════════════════════
# 수상 기준 설정 + 생성 버튼
# ══════════════════════════════════════════════════════════
_award_labels = _campus_cfg.get("award_labels", {
    "perfect_score": "Perfect Score",
    "honor_roll":    "Honor Roll",
    "best_writer":   "Best Writer",
    "best_sr":       "Best SR",
})

if campus == _JUNGBAL_CAMPUS:
    # 정발: 설정된 가중치를 텍스트로 표시 (변경은 campus_config.json에서)
    _saved_w = _campus_cfg.get("score_weights", JUNGBAL_DEFAULT_WEIGHTS)
    jungbal_weights = {k: float(_saved_w.get(k, JUNGBAL_DEFAULT_WEIGHTS[k]))
                       for k in JUNGBAL_DEFAULT_WEIGHTS}

    _SUBJECT_LABEL = {
        "english":     "English",
        "speech":      "Speech",
        "foundations": "Foundations",
        "lc":          "LC",
        "nf":          "NF",
    }

    def _term(key: str, w: float) -> str:
        if w == 1:
            return _SUBJECT_LABEL[key]
        return f"{_SUBJECT_LABEL[key]}×{w:g}"

    # English+Speech+Foundations 모두 1이면 "Total"로 축약
    _eng_keys = ("english", "speech", "foundations")
    _all_eng_one = all(jungbal_weights[k] == 1 for k in _eng_keys)

    _parts: list[str] = []
    if _all_eng_one:
        _parts.append("Total")
    else:
        for k in _eng_keys:
            if jungbal_weights[k] != 0:
                _parts.append(_term(k, jungbal_weights[k]))
    for k in ("lc", "nf"):
        if jungbal_weights[k] != 0:
            _parts.append(_term(k, jungbal_weights[k]))

    _formula = " + ".join(_parts) if _parts else "0"

    poly_section(
        f"02 · {campus} 수상 기준",
        f"{_formula} 점수 합계 → 반 1등 → Achievement Certificate  |  나머지 반 1등 → Monthly Test Winner  (동점 공동 수상)",
    )

    # 정발은 PS/HR/BW 기준 없음 — 기본값만 설정
    ps_min    = _campus_cfg["perfect_score_min"]
    hr_min    = _campus_cfg["honor_roll_min"]
    bw_min_lc = _bw_def
else:
    poly_section(f"02 · {campus} 수상 기준",
                 f"PS ≥ {_campus_cfg['perfect_score_min']:.0f}%  |  "
                 f"HR ≥ {_campus_cfg['honor_roll_min']:.0f}%  |  "
                 f"BW LC ≥ GT {_bw_def.get('GT',27)} / MGT {_bw_def.get('MGT',27)} / "
                 f"S {_bw_def.get('S',27)} / MAG {_bw_def.get('MAG',27)}")

    with st.expander("⚙️ 수상 기준 수정", expanded=False):
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

can_generate = bool(((uploaded_ele or uploaded_lx) and month) or uploaded_sr)
st.markdown('<div class="poly-cta-wrap">', unsafe_allow_html=True)
_btn_generate = st.button("상장 생성하기", type="primary", disabled=not can_generate)
st.markdown('</div>', unsafe_allow_html=True)
if _btn_generate:

    generated = []   # (award_type, folder, filename, pdf_bytes, student)
    errors    = []
    is_jungbal_campus = (campus == _JUNGBAL_CAMPUS)

    # ── Monthly Test 처리 ──────────────────────────────
    ps = hr = bw = []
    jb_ach = jb_mw = []   # 정발 전용
    if (uploaded_ele or uploaded_lx) and month:
        with st.spinner("Monthly Test 수상자 선정 중..."):
            rows = []
            for _uf in [uploaded_ele, uploaded_lx]:
                if _uf is None:
                    continue
                with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                    tmp.write(_uf.read())
                    tmp_path = tmp.name
                rows.extend(load_rows_from_excel(tmp_path))
                os.unlink(tmp_path)

            if is_jungbal_campus:
                jb_winners = select_jungbal_winners(rows, weights=jungbal_weights)
                jb_ach = sorted(jb_winners["achievement_certificate"], key=_sort_key)
                jb_mw  = sorted(jb_winners["monthly_test_winner"],     key=_sort_key)
            else:
                winners = select_winners(
                    rows,
                    perfect_score_min=float(ps_min),
                    honor_roll_min=float(hr_min),
                    best_writer_min_lc=bw_min_lc,
                )
                ps = sorted(winners["perfect_score"], key=_sort_key)
                hr = sorted(winners["honor_roll"],    key=_sort_key)
                bw = sorted(winners["best_writer"],   key=_sort_key)

        with st.spinner("Monthly Test 상장 PDF 생성 중..."):
            with tempfile.TemporaryDirectory() as tmpdir:
                if is_jungbal_campus:
                    for award_type, folder, student_list, needs_extra in [
                        ("achievement_certificate", "Achievement_Certificate", jb_ach, False),
                        ("monthly_test_winner",     "Monthly_Test_Winner",     jb_mw,  True),
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
                                    extra_text=s["class"] if needs_extra else None,
                                )
                                with open(out_path, "rb") as f:
                                    pdf_bytes = f.read()
                                generated.append((award_type, folder, filename, pdf_bytes, s))
                            except Exception as e:
                                errors.append(f"{s['english_name']}: {e}")
                else:
                    for award_type, folder, student_list in [
                        ("perfect_score", "Perfect_Score", ps),
                        ("honor_roll",    "Honor_Roll",    hr),
                        ("best_writer",   "Best_Writer",   bw),
                    ]:
                        if award_type not in _award_labels:
                            continue
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
                                    campus=campus,
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
            _yuseong_sr = (campus == _YUSEONG_CAMPUS)
            _sr_suffix  = ".xlsx" if _yuseong_sr else ".csv"
            with tempfile.NamedTemporaryFile(delete=False, suffix=_sr_suffix, mode="wb") as tmp:
                tmp.write(uploaded_sr.read())
                tmp_path = tmp.name
            if _yuseong_sr:
                sr_rows = load_sr_from_excel_yuseong(tmp_path)
            else:
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
                            campus=campus,
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
        "jb_ach": jb_ach, "jb_mw": jb_mw,
        "generated": generated,
        "errors": errors,
        "month": month,
        "is_jungbal": is_jungbal_campus,
        "jungbal_formula": _formula if is_jungbal_campus else None,
        "zip_bytes": zip_buffer.getvalue(),
        "zip_name": f"{(month or 'SR').replace(' ', '_')}_상장.zip",
    }

# ══════════════════════════════════════════════════════════
# 결과 표시
# ══════════════════════════════════════════════════════════
if "result" in st.session_state:
    r         = st.session_state["result"]
    ps        = r["ps"];  hr = r["hr"];  bw = r["bw"];  sr = r["sr"]
    jb_ach    = r.get("jb_ach", []);  jb_mw = r.get("jb_mw", [])
    generated = r["generated"]
    _is_jb    = r.get("is_jungbal", False)

    if r["errors"]:
        st.warning("일부 상장 생성 실패:\n" + "\n".join(r["errors"]))

    st.success(f"총 {len(generated)}개 상장 생성 완료!")

    poly_section("03 · 수상자 명단", "학생 이름을 클릭하면 상장 미리보기와 다운로드가 표시됩니다.")

    ev_ps = ev_hr = ev_bw = ev_sr = None
    ev_jb_ach = ev_jb_mw = None

    if _is_jb:
        # 가중 합산 점수 컬럼 헤더 — 02 섹션과 동일한 공식 표기 사용
        _score_col = f"{r.get('jungbal_formula') or 'Total + LC'} 점수"

        def _fmt_score(v):
            try:
                f = float(v)
            except (TypeError, ValueError):
                return v
            return int(f) if f == int(f) else round(f, 1)

        # ── 정발 수상자 명단 (2컬럼) ─────────────────────
        col1, col2 = st.columns(2, gap="small")
        with col1:
            st.markdown(
                f'<div class="poly-card-head"><span class="ttl">🏆 Achievement Certificate</span>'
                f'<span class="cnt">{len(jb_ach)}</span></div>', unsafe_allow_html=True)
            if jb_ach:
                ev_jb_ach = st.dataframe(
                    pd.DataFrame([{
                        "이름": s["english_name"],
                        "반": s["class"],
                        _score_col: _fmt_score(s.get("score", s["total"] + s["lc"])),
                    } for s in jb_ach]),
                    hide_index=True, use_container_width=True,
                    selection_mode="single-row", on_select="rerun", key="sel_jb_ach",
                )
            else:
                st.markdown('<div class="poly-empty">해당 학생 없음</div>', unsafe_allow_html=True)
        with col2:
            st.markdown(
                f'<div class="poly-card-head"><span class="ttl">🥇 Monthly Test Winner</span>'
                f'<span class="cnt">{len(jb_mw)}</span></div>', unsafe_allow_html=True)
            if jb_mw:
                ev_jb_mw = st.dataframe(
                    pd.DataFrame([{
                        "이름": s["english_name"],
                        "반": s["class"],
                        _score_col: _fmt_score(s.get("score", s["total"] + s["lc"])),
                    } for s in jb_mw]),
                    hide_index=True, use_container_width=True,
                    selection_mode="single-row", on_select="rerun", key="sel_jb_mw",
                )
            else:
                st.markdown('<div class="poly-empty">해당 학생 없음</div>', unsafe_allow_html=True)
    else:
        # ── 기존 캠퍼스 수상자 명단 (best_writer 없으면 3컬럼, 있으면 4컬럼) ──
        _lbl_ps = _award_labels.get("perfect_score", "Perfect Score")
        _lbl_hr = _award_labels.get("honor_roll",    "Honor Roll")
        _lbl_bw = _award_labels.get("best_writer",   "Best Writer")
        _lbl_sr = _award_labels.get("best_sr",       "Best SR")
        _has_bw = "best_writer" in _award_labels
        _res_cols = st.columns(4 if _has_bw else 3, gap="small")
        with _res_cols[0]:
            st.markdown(
                f'<div class="poly-card-head"><span class="ttl">🏆 {_lbl_ps}</span>'
                f'<span class="cnt">{len(ps)}</span></div>', unsafe_allow_html=True)
            if ps:
                ev_ps = st.dataframe(
                    pd.DataFrame([{"이름": s["english_name"], "반": s["class"]} for s in ps]),
                    hide_index=True, use_container_width=True,
                    selection_mode="single-row", on_select="rerun", key="sel_ps",
                )
            else:
                st.markdown('<div class="poly-empty">해당 학생 없음</div>', unsafe_allow_html=True)
        with _res_cols[1]:
            st.markdown(
                f'<div class="poly-card-head"><span class="ttl">🎖 {_lbl_hr}</span>'
                f'<span class="cnt">{len(hr)}</span></div>', unsafe_allow_html=True)
            if hr:
                ev_hr = st.dataframe(
                    pd.DataFrame([{"이름": s["english_name"], "반": s["class"], "평균": s["average"]} for s in hr]),
                    hide_index=True, use_container_width=True,
                    selection_mode="single-row", on_select="rerun", key="sel_hr",
                )
            else:
                st.markdown('<div class="poly-empty">해당 학생 없음</div>', unsafe_allow_html=True)
        if _has_bw:
            with _res_cols[2]:
                st.markdown(
                    f'<div class="poly-card-head"><span class="ttl">✍️ {_lbl_bw}</span>'
                    f'<span class="cnt">{len(bw)}</span></div>', unsafe_allow_html=True)
                if bw:
                    ev_bw = st.dataframe(
                        pd.DataFrame([{"이름": s["english_name"], "반": s["class"], "LC": s["lc"]} for s in bw]),
                        hide_index=True, use_container_width=True,
                        selection_mode="single-row", on_select="rerun", key="sel_bw",
                    )
                else:
                    st.markdown('<div class="poly-empty">해당 학생 없음</div>', unsafe_allow_html=True)
        with _res_cols[3 if _has_bw else 2]:
            st.markdown(
                f'<div class="poly-card-head"><span class="ttl">⭐ {_lbl_sr}</span>'
                f'<span class="cnt">{len(sr)}</span></div>', unsafe_allow_html=True)
            if sr:
                ev_sr = st.dataframe(
                    pd.DataFrame([{"이름": s["english_name"], "반": s["class"], "GE": s["ge"]} for s in sr]),
                    hide_index=True, use_container_width=True,
                    selection_mode="single-row", on_select="rerun", key="sel_sr",
                )
            else:
                st.markdown('<div class="poly-empty">해당 학생 없음</div>', unsafe_allow_html=True)

    # ── 클릭된 학생 파악 ──────────────────────────────────
    _sel_student = None
    _sel_award   = None
    if ev_jb_ach and ev_jb_ach.selection.rows:
        _sel_student = jb_ach[ev_jb_ach.selection.rows[0]]
        _sel_award   = "achievement_certificate"
    elif ev_jb_mw and ev_jb_mw.selection.rows:
        _sel_student = jb_mw[ev_jb_mw.selection.rows[0]]
        _sel_award   = "monthly_test_winner"
    elif ev_ps and ev_ps.selection.rows:
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
    poly_section("04 · 다운로드", "전체 ZIP 또는 개별 PDF를 다운로드할 수 있습니다.")
    st.download_button(
        label=f"전체 ZIP 다운로드 ({len(generated)}개)",
        data=r["zip_bytes"],
        file_name=r["zip_name"],
        mime="application/zip",
        type="primary",
        key="zip_dl",
    )

    # ── 개별 미리보기 / 다운로드 ──────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    _AWARD_LABEL = {
        "perfect_score":           f"🏆 {_award_labels.get('perfect_score', 'Perfect Score')}",
        "honor_roll":              f"🎖 {_award_labels.get('honor_roll',    'Honor Roll')}",
        "best_writer":             f"✍️ {_award_labels.get('best_writer',   'Best Writer')}",
        "best_sr":                 f"⭐ {_award_labels.get('best_sr',       'Best SR')}",
        "achievement_certificate": f"🏆 {_award_labels.get('achievement_certificate', 'Achievement Certificate')}",
        "monthly_test_winner":     f"🥇 {_award_labels.get('monthly_test_winner',     'Monthly Test Winner')}",
        "level_test_winner":       f"🎖 {_award_labels.get('level_test_winner',       'Level Test Winner')}",
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

# ══════════════════════════════════════════════════════════
# 수동 상장 생성
# ══════════════════════════════════════════════════════════
_AWARD_LABEL_MAP = {
    "perfect_score":           f"🏆 {_award_labels.get('perfect_score', 'Perfect Score')}",
    "honor_roll":              f"🎖 {_award_labels.get('honor_roll',    'Honor Roll')}",
    "best_writer":             f"✍️ {_award_labels.get('best_writer',   'Best Writer')}",
    "best_sr":                 f"⭐ {_award_labels.get('best_sr',       'Best SR')}",
    "achievement_certificate": f"🏆 {_award_labels.get('achievement_certificate', 'Achievement Certificate')}",
    "monthly_test_winner":     f"🥇 {_award_labels.get('monthly_test_winner',     'Monthly Test Winner')}",
    "level_test_winner":       f"🎖 {_award_labels.get('level_test_winner',       'Level Test Winner')}",
}

poly_section("05 · 수동 상장 생성", "업로드 없이 학생 정보를 직접 입력해 개별 상장을 생성합니다.")

_manual_award_keys = list(_award_labels.keys())

mc1, mc2, mc3 = st.columns(3, gap="medium")
with mc1:
    _manual_award = st.selectbox(
        "상장 종류",
        options=_manual_award_keys,
        format_func=lambda k: _award_labels.get(k, k),
        key=f"manual_award_{campus}",
    )
with mc2:
    _manual_name = st.text_input("학생 영문 이름", placeholder="Elena Choi", key="manual_name")
with mc3:
    _manual_class = st.text_input("반 이름", placeholder="GT3", key="manual_class")

mm_col, my_col = st.columns(2)
_MONTHS_LIST = ["January","February","March","April","May","June",
                "July","August","September","October","November","December"]
_manual_month_name = mm_col.selectbox("월", _MONTHS_LIST,
                                       index=datetime.date.today().month - 1,
                                       key="manual_month")
_manual_year = my_col.number_input("연도", 2020, 2100,
                                    datetime.date.today().year, key="manual_year")
_manual_month_str = f"{_manual_month_name} {int(_manual_year)}"

# 정발 monthly/level winner는 extra_text = 반 이름 자동 사용
_manual_extra = (
    _manual_class
    if campus == _JUNGBAL_CAMPUS and _manual_award in {"monthly_test_winner", "level_test_winner"}
    else None
)

_can_manual = bool(_manual_name.strip() and _manual_class.strip())
st.markdown('<div class="poly-cta-wrap">', unsafe_allow_html=True)
_btn_manual = st.button("상장 생성", key="btn_manual", disabled=not _can_manual)
st.markdown('</div>', unsafe_allow_html=True)

if _btn_manual:
    try:
        with tempfile.TemporaryDirectory() as _tmpdir:
            _safe = _manual_name.strip().replace(" ", "_")
            _fn   = f"{_safe}_{_manual_class.strip().replace(' ','_')}.pdf"
            _out  = os.path.join(_tmpdir, _fn)
            build_certificate(
                award_type        = _manual_award,
                english_name      = _manual_name.strip(),
                student_class     = _manual_class.strip(),
                month             = _manual_month_str,
                output_path       = _out,
                template_override = cfg.get_template_path(campus, _manual_award),
                extra_text        = _manual_extra,
                campus            = campus,
            )
            with open(_out, "rb") as _f:
                _manual_pdf = _f.read()
        st.session_state["manual_result"] = {
            "pdf": _manual_pdf, "filename": _fn,
            "award": _manual_award, "name": _manual_name.strip(),
            "class": _manual_class.strip(),
        }
    except Exception as _e:
        st.error(f"상장 생성 실패: {_e}")

if "manual_result" in st.session_state:
    _mr = st.session_state["manual_result"]
    _prev_col, _info_col = st.columns([2, 1])
    with _prev_col:
        st.image(pdf_to_preview_png(_mr["pdf"]), use_container_width=True)
    with _info_col:
        st.markdown(f"**{_AWARD_LABEL_MAP.get(_mr['award'], _mr['award'])}**")
        st.markdown(f"### {_mr['name']}")
        st.caption(_mr["class"])
        st.download_button(
            label="PDF 다운로드",
            data=_mr["pdf"],
            file_name=_mr["filename"],
            mime="application/pdf",
            key="dl_manual",
        )

poly_footer("Poly Academy · 상장 생성기", f"v1.0 · {_dt.date.today().year}")
