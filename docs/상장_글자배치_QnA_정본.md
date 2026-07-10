# 상장 글자배치 로직 QnA 정본

> 상장생성기(`generator.py`)에서 **원장이름·학생이름·월** 3개 변수가 어떻게 위치잡히고 바뀌는지 정본. 로직 손볼 때 먼저 여기서 찾을 것.
> 최종 갱신: 2026-07-10

핵심 원칙 하나: **박힌 글자는 지운 뒤 새로 그린다.** 지우는 방식(배경덮기 vs redaction vs delete_image), 배치 기준(고정Y vs 선검출 vs placeholder검출)만 캠퍼스·변수별로 갈린다.

---

## §0. 캠퍼스별 분기 (build_certificate, generator.py:1154)

| 캠퍼스 | 판정 | 이름·월 배치 방식 | 원장 서명 |
|---|---|---|---|
| 중계 등 기본 | else 브랜치 | 선(divider)기준 상대배치, 고정Y | 텍스트 서명 교체 |
| 정발 | `award_type ∈ JUNGBAL_AWARD_TYPES` | `___` placeholder 검출 벡터주입 | (정발은 미변경) |
| 일산 | 정발 + `campus_config.director` 설정 | 정발과 동일 | 이미지 서명 교체 |
| 유성 | campus에 "유성" + `YUSEONG_AWARD_TYPES` | placeholder(`_____`)+굵은선 검출 | 자체템플릿 |
| 분당엠폴리 | campus에 "분당" + `BUNDANG_AWARD_TYPES` | placeholder 검출 벡터주입 | — |

정발/분당은 **벡터 텍스트 직접주입**(선명·용량작음, 래스터화 없음). 나머지는 PIL 래스터.

---

## §1. 원장이름 바뀌는 부분

Q. 원장 이름은 어떻게 바뀌나?
A. 캠퍼스별 3방식. 공통 = **원본 서명 지움 → 손글씨체(config.SIGNATURE_FONT)로 같은 자리에 재기입**. 이름 길면 폭 자동축소(짤림방지).

### 1-1. 중계 등 기본 — 텍스트 서명 (`_apply_director_signature`, :~940)
- 트리거: `campus_config.director` ≠ 기본값 `SIGNATURE_DEFAULT_NAME`("Colin Park")
- 박힌 서명이 **텍스트 span** → span 폰트·크기·색·baseline·bbox 추출
- 지우기: 테두리없는 채움사각형(`draw_rect`)으로 배경색 덮음. **하단 경계 = baseline+3** (바로 아래 서명선 보존, 이름엔 디센더 없음 전제)
- 배경색: 텍스트 **위쪽 30px 띠** 평균 샘플링(크림/흰색 자동대응)
- 재기입: 같은 baseline, bbox 중앙정렬, `max_w = bbox.width*1.25`, 폰트 `size*1.1`(손글씨 자간보정)

### 1-2. 정발/일산 — 이미지 서명 (`_apply_jungbal_director_signature`, :1115)
- 트리거: 정발계열 + `campus_config.director` ≠ `JUNGBAL_DIRECTOR_DEFAULT`("Charlotte Lee")
- 박힌 서명이 **이미지(XObject)** → 텍스트 아님. `get_image_info`로 **우하단 작은 이미지** 탐지(x0>폭50%, y0>높이50%, 작은크기 = 전체배경 워터마크 제외)
- 지우기: `page.delete_image(xref)` — 서명 이미지만 제거, 배경워터마크 보존
- 재기입: 이미지 bbox 중앙, `ty = bbox.y1 - height*0.28`(원본 baseline 근처), `fs = height*1.1`, 페이지 양끝 8pt 여백 안 넘게 max_w 산출
- 정발 자체는 director 미설정 → None → **변경 없음(정발 양식 그대로 보존)**

### 1-3. 이미지 vs 텍스트 왜 다르나?
정발/일산 템플릿은 서명이 손글씨 **그림**이라 텍스트 검색 안 됨 → delete_image. 중계는 서명이 폰트텍스트 → draw_rect 덮기. **서명 못 찾으면 False 반환(변경없음=안전).**

---

## §2. 학생이름 배치 (위로 올라오는 부분)

Q. 학생이름이 밑줄/선 바로 위에 딱 붙어 올라오는 원리?
A. **선(divider)을 먼저 검출 → 이름을 그 위로 밀어올린다.** 고정 좌표 아님. 이름 높이만큼 위로.

### 2-1. 중계/기본·정발 — 선기준 상대배치 (:1258, :1240)
```
lines     = _scan_template_lines(template, dpi)   # PDF 가로선 전부 검출
divider_y = _find_divider_y(lines, fallback)      # 이름 밑줄 Y
name_font = _load_font_fit(...)                    # 폭 초과시 폰트 자동축소
name_bbox = textbbox(english_name)
name_y    = divider_y − name_bbox[3] − NAME_LINE_GAP   # ★ 선 위로 밀어올림
_draw_centered(name, name_y)                       # 페이지 가로 중앙
```
- **위로 올라오는 핵심** = `name_y = divider_y − 글자높이 − gap`. 글자가 클수록(=`name_bbox[3]`↑) 더 위에서 시작 → 항상 선 위 같은 간격.
- 폭 자동축소(`_load_font_fit`): 긴 이름은 `NAME_MAX_WIDTH` 넘으면 폰트 줄임 → 선 밖으로 안 삐짐
- 반코드(student_class): 이름과 달리 **고정 Y** `config.CLASS_Y[award_type]`(기본 520)
- 정발만 이름폰트 = `JUNGBAL_SCRIPT_FONT`(Pinyon Script), 기본은 `config.NAME_FONT`

### 2-2. 유성·분당 — placeholder 검출 배치 (:658 _render_yuseong, doc: _render_bundang)
- 밑줄이 텍스트 `_____`(언더스코어 span) → `_scan_*_placeholders`로 그 자리 좌표 검출
- placeholder를 **배경색으로 덮어 지움**("가상의 선") → 그 위 텍스트
- 분당 grammar: 이름(크게)+반코드(위 작게) 2줄, 한글포함 → NanumGothic 필수
- 분당 leveltop: "반코드 영문이름" 1줄, 굵은가로선 위 중앙
- baseline = 언더스코어 하단 기준, 폭초과시 `_fit`로 자동축소

### 2-3. 왜 고정좌표 안 쓰나?
템플릿마다 밑줄 Y가 달라서. 선을 런타임 검출해 상대배치하면 award_type 6종·캠퍼스별 템플릿 다 대응. fallback Y(`DIVIDER_LINE_Y_FALLBACK`)는 선 검출 실패시 안전망.

---

## §3. 월(Month) 바뀌는 부분

Q. 월은 어디에 어떻게 들어가나?
A. 입력 `month`="April 2026" 형식. 캠퍼스별로 위치 다름. placeholder/선 검출 후 그 자리.

### 3-1. 중계 등 기본캠퍼스 — 선기준 (:1276)
```
date_line_y = _find_date_line_y(lines, DATE_LINE_Y_FALLBACK)  # 날짜 밑줄
date_y      = date_line_y − 글자높이 − DATE_LINE_GAP           # 선 위로
date_x      = DATE_CENTER_X − 글자폭/2                          # 고정 중앙X
draw.text(month)  # "April 2026" 통째로(연도 포함)
```
- **중계 월위치는 MT/LT 구분 없음.** 시험 종류는 §3-4 문구치환(Monthly Test→Level Test)으로만 갈리고, 월 배치 좌표는 동일.
- 이름·월 모두 선(divider/date-line) 런타임 검출 상대배치라 PS/HR/BW/achievement 템플릿 다 대응.

### 3-2. 정발 — `___` placeholder 검출 (`_inject_jungbal_text_pdf`, :185)
- 페이지에서 `___` 포함 span 검색. **y > 페이지높이 65% = 날짜줄**, 그 위 = extra_text(반이름)
- prefix 폭 계산(PalaceScriptMT)으로 blank **시작 x** 정확히 산출
- `___` 자리 배경색으로 덮음 → GreatVibes로 재기입(PalaceScript 최근접 무료폰트)
- date는 그대로, extra_text만 우측여백(x=678pt) 초과시 폰트축소

### 3-3. 유성 — placeholder, 월만 추출
- `month.rsplit(" ",1)[0]` → "April 2026"에서 **"April"만** 사용(연도 제거)
- 검출한 언더스코어/월 placeholder bbox 덮어지우고 중앙 재기입, 폭맞춤

### 3-3b. 분당엠폴리(엠폴리) — award_type 5종마다 월배치 다름 (`_inject_bundang_text_pdf`, :426)
공통 전처리: `month_name = month.rsplit(" ",1)[0]`("April"), `year = 뒤쪽`("2026"). 흰사각형 `_cover`로 원본 덮고 NanumGothic 벡터 재기입.

| award_type | 월 위치 | 방식 |
|---|---|---|
| **grammar_certification** | "During the month of `___` {year}" 본문줄 | 줄 **전체 재작성** `f"During the month of {month_name} {year}"`, span폭 중앙정렬. + "on the {year} POLY Grammar..." 연도줄도 재작성 (:633) |
| **certificate_of_achievement**(레벨탑) | 제목 "POLY `___`" 인라인 | `_us_hit`로 언더스코어 찾아 덮고 그 자리 `month_name`만 Bold 재기입 (:574) |
| **best_book_reflection** | 제목 "{year} {month} Best Book Reflection" | "Best Book Reflection" span 통째 덮고 `f"{year} {month_name} Best Book Reflection"` PlayfairDisplay 금색 중앙 재작성 (:591) |
| **voca_king** | 상단 중앙 타이틀 | 월 점선 없음. 베이킹된 기본 "April"을 `VOCA_MONTH_COVER`로 흰색덮기 → `month.capitalize()` Algerian(VOCA KING 동일서체) 재기입. 고정좌표 `VOCA_MONTH_BASELINE` (:475) |
| **best_essay** | **월 변수 없음** | `month` 인자를 "L1\|L2" 제목 두 줄로 전용(월 아님). `\|` 있으면 제목 재작성, 없으면 기본제목 유지 (:506) |

- 엠폴리는 유성과 달리 **월만 바꾸는 게 아니라 문장/제목 줄 전체를 재작성**하는 경우가 많음(자간 깨짐·잔상 방지). grammar는 본문·연도줄 2곳.
- voca_king은 placeholder(점선)가 아예 없어 **고정좌표+기본월 흰색덮기**로 처리(다른 월 넣어도 "April" 잔상 없음).
- best_essay의 `month` 파라미터는 이름만 month일 뿐 **제목 편집용**(주의).

### 3-4. Monthly Test → Level Test 문구치환 (`_apply_test_label`, :993)
- **월 자체 아님.** 중계 등 PS/HR/BW 상장의 "on the Monthly Test" 문구를 LT시험이면 "Level Test"로 바꾸는 것
- 트리거: `test_label=="Level"` + award_type ∈ (perfect_score/honor_roll/best_writer)
- **redaction**으로 'Monthly Test' 글리프 완전제거(텍스트층까지) → 원본폰트(PlayfairDisplay-Italic 14pt)·색 맞춰 재기입
- 배경색 = 문구 **오른쪽** 빈칸 가장밝은픽셀(위쪽은 어센더 잉크오염이라 회피)
- 못 찾으면 False(변경없음)

### 3-5. 캠퍼스명 치환 (`_apply_campus_label`, :1049) — 참고
- 월/이름 아니지만 같은 계열. 정발→일산 등 "Jeongbal"→"Ilsan"
- 제목(스크립트체 size>30)+서명란(Calibri size<30) 두 곳, **줄 전체 재기입**(자간깨짐 방지)
- redaction `fill=False` + `IMAGE_NONE`/`LINE_ART_NONE` → 워터마크·라인아트 보존

---

## §4. 3대 지우기 방식 요약 (제일 헷갈리는 곳)

| 방식 | 언제 | 특징 |
|---|---|---|
| `draw_rect` 배경덮기 | 중계 서명, 유성/분당 placeholder | 배경색 샘플링해 사각형 덮음. 벡터층엔 잔존(이미지化하니 무관) |
| `add_redact_annot`+`apply_redactions` | Monthly Test·캠퍼스명 문구치환 | **텍스트층까지 완전제거**. 벡터PDF도 잔존없음. `fill=False`+IMAGE/LINE_ART_NONE로 배경보존 |
| `delete_image(xref)` | 정발/일산 원장 서명 | 이미지 XObject만 제거, 배경워터마크 보존 |

배경색은 **항상 근처 깨끗한 픽셀 샘플링**(크림·흰색 자동대응). 잉크(어센더) 오염 피하려 위쪽 대신 옆/위쪽 띠 골라 씀.

---

## §5. 안전장치 (전 함수 공통)
- 대상(서명/문구/placeholder) 못 찾으면 **False 반환 = 변경없음** → 원본 안 깨짐
- 폭 초과 = 폰트 자동축소 루프(min size까지) → 짤림·삐짐 원천차단
- 기본값과 같으면 치환 스킵(정발 director/label 미설정 → 양식 보존)
