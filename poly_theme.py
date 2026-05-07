"""
poly_theme.py — Poly Design System theme module for Streamlit
=============================================================
Drop-in module. Usage in app.py:

    from poly_theme import (
        inject_poly_theme,
        poly_header,
        poly_campus_banner,
        poly_section,
        poly_kpi_row,
        poly_award_card_grid,
        poly_footer,
    )
    inject_poly_theme()

All functions render via st.markdown(..., unsafe_allow_html=True).
No JavaScript. Compatible with Streamlit 1.30+.
"""

from __future__ import annotations
import base64
import html
from pathlib import Path
import streamlit as st

_HERE = Path(__file__).parent
_ASSETS = _HERE / "assets"
_FONTS = _HERE / "poly_fonts"


def _b64(path: Path) -> str:
    if not path.exists():
        return ""
    return base64.b64encode(path.read_bytes()).decode("ascii")


def _logo_uri() -> str:
    b = _b64(_ASSETS / "poly_logo.png")
    return f"data:image/png;base64,{b}" if b else ""


def _emblem_uri() -> str:
    b = _b64(_ASSETS / "poly_emblem_circle.png")
    return f"data:image/png;base64,{b}" if b else ""


def _emblem_diamond_uri() -> str:
    b = _b64(_ASSETS / "poly_emblem_diamond.png")
    return f"data:image/png;base64,{b}" if b else ""


def _font_face_css() -> str:
    """Inline TTF fonts from ./fonts as @font-face. Skips missing files silently."""
    faces = [
        # NanumSquare Neo — display & headings
        ("NanumSquareNeo", 400, "NanumSquareNeo-bRg.ttf"),
        ("NanumSquareNeo", 500, "NanumSquareNeo-cBd.ttf"),
        ("NanumSquareNeo", 700, "NanumSquareNeo-cBd.ttf"),
        ("NanumSquareNeo", 800, "NanumSquareNeo-eHv.ttf"),
        # KoPubWorld Dotum — body / numerals
        ("KoPubWorldDotum", 500, "KoPubWorldDotum-Medium.ttf"),
        ("KoPubWorldDotum", 700, "KoPubWorldDotum-Bold.ttf"),
    ]
    out = []
    for family, weight, fname in faces:
        b = _b64(_FONTS / fname)
        if not b:
            continue
        out.append(
            f"""@font-face {{
  font-family: '{family}';
  font-style: normal;
  font-weight: {weight};
  font-display: swap;
  src: url(data:font/ttf;base64,{b}) format('truetype');
}}"""
        )
    return "\n".join(out)


# ============================================================================
# 1. THEME INJECTION
# ============================================================================

_POLY_CSS = r"""
<style>
/* ---------- Pretendard (web fallback) ---------- */
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable.min.css');

/* ---------- Tokens ---------- */
:root {
  --poly-blue-50:  #ECF3FB;
  --poly-blue-100: #D2E1F4;
  --poly-blue-200: #A6C2E8;
  --poly-blue-300: #6E9CD8;
  --poly-blue-400: #3776C2;
  --poly-blue-500: #004EA2;
  --poly-blue-600: #003F84;
  --poly-blue-700: #002F65;
  --poly-blue-800: #00224A;
  --poly-blue-900: #001530;

  --poly-gold-50:  #FBF6E6;
  --poly-gold-300: #DABF50;
  --poly-gold-500: #A6841A;
  --poly-gold-700: #5F4A0E;

  --ink-0:  #FFFFFF;
  --ink-50: #F7F8FA;
  --ink-100:#EEF1F5;
  --ink-200:#E1E5EC;
  --ink-300:#C5CCD8;
  --ink-400:#97A2B3;
  --ink-500:#6A7588;
  --ink-600:#4A5363;
  --ink-700:#2E3744;
  --ink-800:#1A212E;
  --ink-900:#0B111E;

  --success-50: #E5F6EC; --success-700:#0E6029;
  --warning-50: #FDF4D7; --warning-700:#8A5F02;
  --danger-50:  #FBE9E8; --danger-700: #761816;

  --shadow-1: 0 1px 2px rgba(11,17,30,.05), 0 1px 1px rgba(11,17,30,.04);
  --shadow-2: 0 2px 4px rgba(11,17,30,.05), 0 6px 14px rgba(11,17,30,.06);
  --shadow-3: 0 6px 16px rgba(11,17,30,.07), 0 14px 36px rgba(0,78,162,.10);
  --radius-md: 10px;
  --radius-lg: 16px;
  --ease: cubic-bezier(.2,.7,.2,1);
}

/* ---------- App canvas + container width ---------- */
html, body, [class*="css"], .stApp, .stMarkdown, .stMarkdown p,
.stTextInput, .stNumberInput, .stSelectbox, .stFileUploader, .stButton, .stExpander {
  font-family: 'NanumSquareNeo', 'KoPubWorldDotum', 'Pretendard Variable', Pretendard,
               -apple-system, BlinkMacSystemFont, system-ui, 'Apple SD Gothic Neo',
               'Malgun Gothic', sans-serif !important;
}
.stApp { background: var(--ink-50) !important; color: var(--ink-700); }
.block-container { padding-top: 2.2rem !important; padding-bottom: 4rem !important; max-width: 1200px !important; }

/* ---------- Hide Streamlit chrome (optional, comment out if needed) ---------- */
#MainMenu, footer, [data-testid="stStatusWidget"] { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; }

/* ---------- Headings ---------- */
h1, h2, h3, h4 { color: var(--ink-900) !important; letter-spacing: -.018em; font-family: 'NanumSquareNeo', sans-serif !important; }
h1 { font-weight: 800 !important; }
h2 { font-weight: 700 !important; }
h3 { font-weight: 700 !important; }
.stMarkdown p { color: var(--ink-700); line-height: 1.6; font-family: 'KoPubWorldDotum','NanumSquareNeo',sans-serif !important; }

/* ---------- Buttons ---------- */
div[data-testid="stButton"] > button,
div[data-testid="stDownloadButton"] > button {
  background: #fff !important;
  color: var(--ink-700) !important;
  border: 1px solid var(--ink-200) !important;
  border-radius: 8px !important;
  font-weight: 600 !important;
  font-size: 13.5px !important;
  padding: 9px 18px !important;
  box-shadow: var(--shadow-1) !important;
  transition: all 160ms var(--ease) !important;
  letter-spacing: -.005em;
}
div[data-testid="stButton"] > button:hover,
div[data-testid="stDownloadButton"] > button:hover {
  border-color: var(--poly-blue-300) !important;
  color: var(--poly-blue-700) !important;
  box-shadow: var(--shadow-2) !important;
  transform: translateY(-1px);
}

/* primary button */
div[data-testid="stButton"] > button[kind="primary"],
div[data-testid="stDownloadButton"] > button[kind="primary"] {
  background: var(--poly-blue-500) !important;
  color: #fff !important;
  border: 1px solid var(--poly-blue-500) !important;
  box-shadow: var(--shadow-2) !important;
}
div[data-testid="stButton"] > button[kind="primary"]:hover,
div[data-testid="stDownloadButton"] > button[kind="primary"]:hover {
  background: var(--poly-blue-600) !important;
  border-color: var(--poly-blue-600) !important;
  box-shadow: var(--shadow-3) !important;
}

/* ---------- Inputs ---------- */
input, textarea,
div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div {
  border-radius: 8px !important;
  border-color: var(--ink-200) !important;
  background: #fff !important;
  font-size: 14px !important;
}
div[data-baseweb="select"] > div:hover,
div[data-baseweb="input"] > div:hover { border-color: var(--ink-300) !important; }
div[data-baseweb="select"] > div:focus-within,
div[data-baseweb="input"] > div:focus-within {
  border-color: var(--poly-blue-500) !important;
  box-shadow: 0 0 0 3px rgba(0,78,162,.18) !important;
}
label, .stFileUploader label, .stSelectbox label {
  font-size: 12.5px !important; font-weight: 600 !important;
  color: var(--ink-700) !important; letter-spacing: -.005em;
}

/* ---------- File uploader ---------- */
[data-testid="stFileUploaderDropzone"] {
  background: #fff !important;
  border: 1.5px dashed var(--ink-300) !important;
  border-radius: 12px !important;
  padding: 22px !important;
  transition: all 160ms var(--ease);
}
[data-testid="stFileUploaderDropzone"]:hover {
  border-color: var(--poly-blue-400) !important;
  background: var(--poly-blue-50) !important;
}
[data-testid="stFileUploaderDropzone"] small,
[data-testid="stFileUploaderDropzone"] span { color: var(--ink-500) !important; }

/* ---------- Expander ---------- */
.streamlit-expanderHeader, [data-testid="stExpander"] details > summary {
  background: #fff !important;
  border: 1px solid var(--ink-200) !important;
  border-radius: 10px !important;
  padding: 12px 16px !important;
  font-weight: 600 !important;
  color: var(--ink-800) !important;
  font-size: 13.5px !important;
}
[data-testid="stExpander"] { border: none !important; box-shadow: var(--shadow-1); border-radius: 10px; }
[data-testid="stExpander"] details[open] > summary { border-bottom: 1px solid var(--ink-100) !important; border-radius: 10px 10px 0 0 !important; }
[data-testid="stExpander"] details > div { background: #fff !important; padding: 16px 20px !important; border-radius: 0 0 10px 10px; }

/* ---------- DataFrame ---------- */
[data-testid="stDataFrame"] { border-radius: 10px !important; overflow: hidden; box-shadow: var(--shadow-1); border: 1px solid var(--ink-100); }
[data-testid="stDataFrame"] [role="columnheader"] {
  background: var(--ink-50) !important;
  font-weight: 700 !important;
  font-size: 12px !important;
  letter-spacing: .04em;
  text-transform: uppercase;
  color: var(--ink-600) !important;
}
[data-testid="stDataFrame"] [role="row"] { font-size: 13px; }

/* ---------- Custom Poly classes ---------- */
.poly-eyebrow { font-size:11px; font-weight:700; letter-spacing:.14em; text-transform:uppercase; color:var(--poly-blue-500); }
.poly-h1 { font-size:30px; font-weight:800; letter-spacing:-.018em; color:var(--ink-900); margin:6px 0 6px; }
.poly-sub { font-size:14px; color:var(--ink-500); margin:0 0 18px; }

.poly-banner {
  margin: 10px 0 24px; padding: 22px 26px; border-radius: var(--radius-lg);
  background: linear-gradient(135deg, var(--poly-blue-700) 0%, var(--poly-blue-500) 100%);
  color:#fff; box-shadow: var(--shadow-2);
  display:flex; align-items:center; gap:18px; position:relative; overflow:hidden;
}
.poly-banner::after {
  content:""; position:absolute; right:-30px; top:-40px; width:200px; height:200px;
  border-radius:50%; background:radial-gradient(circle, rgba(255,255,255,.18), transparent 60%);
  pointer-events:none;
}
.poly-banner .mark { width:46px; height:46px; border-radius:50%; background:#fff; color:var(--poly-blue-500); display:grid; place-items:center; font-weight:900; font-size:22px; flex:none; box-shadow: 0 2px 6px rgba(0,0,0,.15); }
.poly-banner .emblem { width:54px; height:54px; flex:none; background:#fff; padding:8px; border-radius:50%; box-shadow: 0 2px 6px rgba(0,0,0,.15); object-fit:contain; }
.poly-banner .body h2 { color:#fff !important; font-size:20px !important; font-weight:700 !important; margin:0 0 2px; letter-spacing:-.01em; }
.poly-banner .body .term { font-size:12.5px; opacity:.78; letter-spacing:.02em; }
.poly-banner .badge { margin-left:auto; padding:6px 12px; border-radius:999px; background:rgba(255,255,255,.18); font-size:11.5px; font-weight:600; letter-spacing:.04em; backdrop-filter: blur(6px); }

.poly-section-head {
  display:flex; align-items:baseline; gap:14px; margin: 26px 0 12px;
  border-top: 1px solid var(--ink-200); padding-top: 22px;
}
.poly-section-head .num { font-family: 'JetBrains Mono', monospace; font-size:11px; letter-spacing:.06em; color:var(--ink-400); font-weight:600; }
.poly-section-head h3 { font-size:18px !important; font-weight:700 !important; margin:0 !important; }
.poly-section-head .desc { font-size:13px; color:var(--ink-500); margin-left:auto; }

.poly-drop {
  display:flex; align-items:baseline; gap:8px; padding: 0 4px 6px;
  font-size:13px; color:var(--ink-700);
}
.poly-drop b { font-size:13.5px; font-weight:700; color:var(--ink-900); }
.poly-drop .hint { font-size:11.5px; color:var(--ink-400); font-family:'JetBrains Mono', monospace; letter-spacing:.02em; }

.poly-kpi-row { display:grid; grid-template-columns:repeat(4, 1fr); gap:12px; margin: 14px 0 22px; }
.poly-kpi {
  background:#fff; border:1px solid var(--ink-100); border-radius:10px; padding: 14px 16px;
  box-shadow: var(--shadow-1);
}
.poly-kpi .lbl { font-size:11px; font-weight:700; letter-spacing:.1em; text-transform:uppercase; color:var(--ink-500); }
.poly-kpi .val { font-size:24px; font-weight:800; color:var(--ink-900); margin: 4px 0 2px; letter-spacing:-.015em; font-variant-numeric: tabular-nums; }
.poly-kpi .sub { font-size:11.5px; color:var(--ink-500); }

.poly-cta-wrap { display:flex; justify-content:flex-end; margin: 14px 0 8px; }

.poly-card {
  background:#fff; border:1px solid var(--ink-100); border-radius: var(--radius-md);
  box-shadow: var(--shadow-1); overflow:hidden; height:100%;
}
.poly-card-head {
  padding: 14px 16px 12px; border-bottom: 1px solid var(--ink-100);
  display:flex; align-items:baseline; justify-content:space-between; gap:8px;
  background: linear-gradient(180deg, #fff 0%, var(--ink-50) 100%);
}
.poly-card-head .ttl { font-size:13.5px; font-weight:700; color:var(--ink-900); letter-spacing:-.01em; }
.poly-card-head .cnt { font-family:'JetBrains Mono', monospace; font-size:11.5px; font-weight:700; color:var(--poly-blue-600); padding:2px 8px; border-radius:999px; background:var(--poly-blue-50); }
.poly-card-head .desc { font-size:11px; color:var(--ink-500); width:100%; margin-top:4px; }

.poly-empty {
  padding: 28px 16px; text-align:center; color:var(--ink-400); font-size:12.5px;
  border-top: 1px dashed var(--ink-200);
}

.poly-footer {
  margin-top: 48px; padding: 18px 0; border-top: 1px solid var(--ink-200);
  display:flex; align-items:center; gap:12px; color:var(--ink-500); font-size:12px;
}
.poly-footer .dot { width:8px; height:8px; border-radius:50%; background:var(--poly-blue-500); }
.poly-footer .right { margin-left:auto; font-family:'JetBrains Mono', monospace; letter-spacing:.04em; }
</style>
"""


def inject_poly_theme():
    """Call once per app run (after st.set_page_config). Injects all styles."""
    st.markdown(f"<style>{_font_face_css()}</style>", unsafe_allow_html=True)
    st.markdown(_POLY_CSS, unsafe_allow_html=True)


# ============================================================================
# 2. SECTION HELPERS
# ============================================================================

def poly_header(title: str, subtitle: str = "", eyebrow: str = "ACADEMY"):
    """Page-level header: Poly wordmark logo + eyebrow → title → subtitle."""
    logo = _logo_uri()
    logo_html = (
        f'<img src="{logo}" alt="Poly" style="height:34px;width:auto;display:block;margin-bottom:14px;" />'
        if logo
        else ""
    )
    st.markdown(
        f"""
        <div style="margin-bottom: 18px;">
          {logo_html}
          <span class="poly-eyebrow">{html.escape(eyebrow)}</span>
          <h1 class="poly-h1">{html.escape(title)}</h1>
          <p class="poly-sub">{html.escape(subtitle)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def poly_campus_banner(campus_name: str, term: str = ""):
    """Royal-blue banner: Poly emblem + campus name + term tag."""
    em = _emblem_uri()
    mark_html = (
        f'<img src="{em}" alt="Poly" class="emblem" />'
        if em
        else '<div class="mark">P</div>'
    )
    st.markdown(
        f"""
        <div class="poly-banner">
          {mark_html}
          <div class="body">
            <h2>{html.escape(campus_name)} 캠퍼스</h2>
            <div class="term">{html.escape(term)}</div>
          </div>
          <div class="badge">CERTIFICATES</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def poly_section(title: str, desc: str = ""):
    """Numbered section divider — call between major workflow steps."""
    # Auto-extract leading "NN ·" pattern for the mono number tag
    num, _, ttl = title.partition(" · ")
    if not ttl:
        num, ttl = "", title
    st.markdown(
        f"""
        <div class="poly-section-head">
          <span class="num">{html.escape(num)}</span>
          <h3>{html.escape(ttl)}</h3>
          <span class="desc">{html.escape(desc)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def poly_kpi_row(items: list[tuple[str, str, str]]):
    """4-up KPI tiles. items = [(label, value, sub), ...]"""
    cells = "".join(
        f"""<div class="poly-kpi">
          <div class="lbl">{html.escape(lbl)}</div>
          <div class="val">{html.escape(str(val))}</div>
          <div class="sub">{html.escape(sub)}</div>
        </div>"""
        for lbl, val, sub in items
    )
    st.markdown(f'<div class="poly-kpi-row">{cells}</div>', unsafe_allow_html=True)


def poly_award_card_grid(awards: list):
    """4-up award card grid. awards = [(title, dataframe, desc), ...]
    Renders Poly card chrome around st.dataframe for each.
    """
    cols = st.columns(len(awards), gap="small")
    for col, (ttl, df, desc) in zip(cols, awards):
        with col:
            count = 0 if df is None else len(df)
            st.markdown(
                f"""
                <div class="poly-card">
                  <div class="poly-card-head">
                    <span class="ttl">{html.escape(ttl)}</span>
                    <span class="cnt">{count}</span>
                    <div class="desc">{html.escape(desc)}</div>
                  </div>
                """,
                unsafe_allow_html=True,
            )
            if df is None or count == 0:
                st.markdown('<div class="poly-empty">해당 학생 없음</div>', unsafe_allow_html=True)
            else:
                st.dataframe(df, hide_index=True, use_container_width=True, height=min(40 + count * 35, 320))
            st.markdown("</div>", unsafe_allow_html=True)


def poly_footer(left: str = "Poly Academy · Internal tool", right: str = ""):
    st.markdown(
        f"""
        <div class="poly-footer">
          <span class="dot"></span>
          <span>{html.escape(left)}</span>
          <span class="right">{html.escape(right)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
