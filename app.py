"""
입대 나침반 (EnlistCompass) — 메인 Streamlit 앱
실행: streamlit run app.py
"""
import streamlit as st
from datetime import datetime, timezone, timedelta
import importlib
from api import mma_api, gemini_api
from utils import matching
from utils.hints import get_hint

# Streamlit Cloud 모듈 캐싱 방지용 강제 리로드
importlib.reload(mma_api)
importlib.reload(gemini_api)
importlib.reload(matching)

st.set_page_config(page_title="입대 나침반", page_icon="🧭", layout="wide")

# 전역 버튼 스타일 커스텀: 줄바꿈 금지(nowrap) 및 크기 조정
st.markdown(
    """
    <style>
    div[data-testid="stButton"] button {
        white-space: nowrap !important;
        font-size: 0.82em !important;
        padding: 0.2rem 0.4rem !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)


def get_secret(name):
    """secrets.toml에 키가 있으면 반환, 없으면 빈 문자열"""
    try:
        return st.secrets.get(name, "")
    except Exception:
        return ""


def format_datetime(dt_str):
    """ISO 8601 형식의 날짜 문자열(예: 2026-05-28T14:00:00+09:00)을 'YYYY-MM-DD HH:MM' 형식으로 변환"""
    if not dt_str:
        return ""
    try:
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return dt_str


def get_recruitment_status(tk, now):
    """보직의 모집 상태와 포맷팅된 기간 반환. 이미 지난 접수 일정은 표시하지 않음."""
    start_str = tk.get("apply_start")
    end_str = tk.get("apply_end")
    if not start_str or not end_str:
        return "NO_DATE", ""
    try:
        start_dt = datetime.fromisoformat(start_str)
        end_dt = datetime.fromisoformat(end_str)
        
        if end_dt < now:
            # 접수 종료된 과거 정보
            return "CLOSED", ""
            
        start_fmt = start_dt.strftime("%Y-%m-%d %H:%M")
        end_fmt = end_dt.strftime("%Y-%m-%d %H:%M")
        
        if start_dt <= now <= end_dt:
            return "OPEN", f"🟢 **접수 중**: {start_fmt} ~ {end_fmt}"
        else:
            return "UPCOMING", f"🔵 **접수 예정**: {start_fmt} ~ {end_fmt}"
    except Exception:
        return "ERROR", ""

# ── 세션 상태 초기화 ──
if "page" not in st.session_state:
    st.session_state.page = "intro"
if "user" not in st.session_state:
    st.session_state.user = {}
if "results" not in st.session_state:
    st.session_state.results = None
if "compare" not in st.session_state:
    st.session_state.compare = []
if "active_summary" not in st.session_state:
    st.session_state.active_summary = None
if "active_details" not in st.session_state:
    st.session_state.active_details = None

# ── 로컬 데이터 확인 ──
local_data = mma_api.load_local_data()

# secrets.toml에 키가 있으면 자동 사용, 없으면 입력창 표시
_mma = get_secret("MMA_API_KEY")
_gemini = get_secret("GEMINI_API_KEY")

# API 키 설정 초기화
mma_key = _mma
gemini_key = _gemini

# ── 인트로 (설문조사) 페이지 분기 ──
if st.session_state.page == "intro":
    st.title("🧭 입대 나침반")
    st.caption("내 조건으로 지원 가능한 군 보직을 한눈에 찾아보세요.")
    st.warning("⚠️ 본 서비스의 정보는 참고용이며, 실제 모집 요건은 반드시 병무청 공고를 확인하세요.")
    
    st.divider()
    
    st.subheader("혹시 카투사(KATUSA)를 지원해 보셨나요?")
    st.caption("카투사는 평생 단 1회만 지원 가능한 인기 보직으로, 지원 이력에 따라 최적의 경로를 안내합니다.")
    
    option = st.radio(
        "아래 항목 중 본인에게 해당하는 항목을 선택하세요:",
        [
            "1️⃣ 네, 지원해 봤는데 떨어졌어요 (또는 탈락했어요)",
            "2️⃣ 아니요, 아직 안 해봤어요 (지원 예정 / 관심 있음)",
            "3️⃣ 카투사는 생각 없어요"
        ],
        index=None,
        key="katusa_survey_radio"
    )
    
    # 사이드바 구성 (일관성 유지)
    with st.sidebar:
        st.markdown("### 🧭 입대 나침반")
        st.caption("내 조건으로 군 보직 찾기")
        st.info("카투사 설문을 마친 후 메인 서비스로 진입할 수 있습니다.")
    
    if option:
        if option.startswith("1️⃣"):
            st.session_state.page = "main"
            st.rerun()
        else:
            if option.startswith("3️⃣"):
                st.info("💡 카투사는 미군과 함께 복무하며 우수한 생활 시설과 영어 학습 기회를 얻을 수 있어 선호도가 매우 높은 보직입니다. 생각해보지 않으셨더라도 아래 모집 조건과 혜택을 한 번 검토해 보시는 것을 적극 추천해 드립니다!")
            
            st.divider()
            st.markdown("### 🇺🇸 모집 안내: 카투사 (KATUSA)")
            st.write("카투사(Korean Augmentation To the United States Army)는 미8군에 배속된 한국군 육군 요원으로, 한미 연합 방위태세 강화를 위한 임무를 수행합니다.")
            
            # 카드 레이아웃을 위한 2단 배치
            col_info1, col_info2 = st.columns(2)
            
            with col_info1:
                with st.container(border=True):
                    st.markdown("#### 📋 기본 지원 자격")
                    st.markdown("""
                    * **연령**: 지원서 접수년도 기준 **18세 이상 28세 이하**
                      * *(2026년 모집 기준: 1998. 1. 1. ~ 2008. 12. 31. 출생자)*
                    * **신체등급**: 병역판정검사 결과 **1급 ~ 4급** 현역병입영대상자
                      * *아직 검사를 받지 않은 사람도 현역병 지원 신체검사 결과 1~4급이면 가능합니다.*
                    * **제한 사항**: 현역병(징집병) 입영기일이 결정된 사람은 그 입영기일 30일 전까지 지원 완료해야 함
                    """)
            
            with col_info2:
                with st.container(border=True):
                    st.markdown("#### 🚫 선발 제외 대상")
                    st.markdown("""
                    * 범죄경력 조회결과(경찰청) **징역 또는 금고의 실형(집행유예 포함)**을 선고받은 사람 (기소유예는 무관)
                    * 현재 수사 또는 재판 중에 있는 사람
                    * 대체역 편입원을 제출한 사람
                    * ※ 최종 합격했더라도 입영 시점에 범죄경력 등이 확인되면 선발이 즉시 취소됩니다.
                    """)
            
            st.markdown("#### 🔠 영어 어학성적 기준 (2026년 기준)")
            st.markdown("접수일 기준 **5년 이내**에 응시하고 성적이 발표된 **정기시험** 성적만 인정됩니다.")
            
            st.markdown("""
            | 시험 종류 | 기준 점수 | 응시 구분 | 비고 |
            | :--- | :---: | :---: | :--- |
            | **TOEIC** | **780점** 이상 | 국내·외 | 정기시험 성적만 인정 |
            | **TEPS** | **299점** 이상 | 국내 | |
            | **TOEFL iBT** | **73점** 이상 | 국내·외 | 2026. 1. 20. 이전 응시자는 **83점** 이상 적용 |
            | **G-TELP (Level 2)** | **73점** 이상 | 국내 | |
            | **FLEX** | **690점** 이상 | 국내 | |
            | **OPIc** | **IM2** 이상 | 국내 | |
            | **TOEIC Speaking** | **140점** 이상 | 국내·외 | |
            | **TEPS Speaking** | **83점** 이상 | 국내 | 개편 전 응시자는 **61점** 이상 적용 |
            """)
            st.caption("※ 어학시험은 특별(수시)시험은 지원 불가합니다. 국외 응시 토익(일본 제외) 등은 사전등록이 불가하여 성적표 원본 제출이 필요합니다.")
            
            col_info3, col_info4 = st.columns(2)
            with col_info3:
                with st.container(border=True):
                    st.markdown("#### 📂 구비 서류 및 발급 절차")
                    st.markdown("""
                    * **제출 서류**: 어학성적사전등록확인서 (정부24 발급)
                    * **발급 및 확인 절차**:
                      1. [국가공무원채용시스템](https://gongmuwon.gosi.kr) 접속 → '어학성적 사전등록' 신청 및 등록
                      2. [정부24](https://www.gov.kr) 접속 → '어학성적 사전등록 확인서 교부' 검색 → 신청 및 출력
                    """)
            
            with col_info4:
                with st.container(border=True):
                    st.markdown("#### 📅 2026년 모집 및 선발 일정")
                    st.markdown("""
                    * **지원 횟수**: **평생 단 1회만 지원 가능** (접수 취소 또는 신검 불합격자는 재지원 가능)
                    * **접수 기간**: **2026. 7. 9. (목) ~ 7. 15. (수)**
                    * **접수 방법**: 병무청 누리집 → 병무민원포털 → 군지원 → 통합지원서 작성
                    * **선발 일자 및 방식**: **2026. 9. 1. (화)** / 입영희망월 및 어학성적대별 비율을 적용하여 **전산 무작위 추첨**
                    """)
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🧭 내 조건으로 지원 가능한 군 보직 찾으러 가기", type="primary", use_container_width=True):
                st.session_state.page = "main"
                st.rerun()
                
    st.stop()

# ── 메인 화면 ──
with st.sidebar:
    st.markdown("### 🧭 입대 나침반")
    st.caption("내 조건으로 군 보직 찾기")
    st.divider()
    if st.button("↩️ 처음으로 (설문 화면)", use_container_width=True):
        st.session_state.page = "intro"
        st.rerun()

st.title("🧭 입대 나침반")
st.caption("내 조건으로 지원 가능한 군 보직을 한눈에 찾아보세요.")

# 만약 API 키가 누락되었을 때만 expander 형태로 표시
if not _mma or not _gemini:
    with st.expander("🔑 API 키 설정 (키가 누락된 경우에만 입력하세요)", expanded=True):
        if not _mma:
            mma_key = st.text_input("병무청 API 키", type="password",
                                    help="공공데이터포털에서 발급한 키")
        if not _gemini:
            gemini_key = st.text_input("Google Gemini 키 (선택)", type="password",
                                       help="학과/자격증 자동 매칭에 사용 (Google AI Studio에서 발급)")

st.warning("⚠️ 본 서비스의 정보는 참고용이며, 실제 모집 요건은 반드시 병무청 공고를 확인하세요.")

# 로컬 데이터가 없는 경우 자동 동기화 실행
if not local_data and mma_key:
    with st.spinner("최초 실행: 병무청 데이터를 로컬로 안전하게 수집하고 있습니다 (약 1분 소요)..."):
        try:
            import os
            from scripts import download_data
            current_dir = os.path.dirname(os.path.abspath(__file__))
            output_path = os.path.join(current_dir, "data", "military_specialties.json")
            success = download_data.download_and_save(mma_key, output_path)
            if success:
                st.rerun()
        except Exception as e:
            st.error(f"자동 데이터 수집 오류: {e}")

# ── 메인 ──
st.header("내 조건 입력")
st.caption("점수나 합격 예측이 아니라, **지금 내가 지원할 수 있는 보직**을 찾아드려요.")

col1, col2, col3 = st.columns(3)

with col1:
    gun = st.selectbox("희망 군종", ["전체", "육군", "해군", "공군", "해병대"])

    st.markdown("**신체등급** (병역판정검사 결과)")
    body_grade = st.radio("신체등급", [1, 2, 3, 4],
                          format_func=lambda x: f"{x}급",
                          horizontal=True, label_visibility="collapsed")

with col2:
    st.markdown("**시력**")
    vision_naked = st.number_input("나안시력 (교정 전, 더 나쁜 쪽 눈 기준)",
                                   min_value=0.0, max_value=2.0,
                                   value=1.0, step=0.1)
    no_correction = st.checkbox("시력 교정 안 함 (안경/렌즈 미착용)")
    if no_correction:
        vision_corrected = vision_naked
        st.caption(f"교정시력 = 나안시력({vision_naked})으로 자동 적용")
    else:
        vision_corrected = st.number_input("교정시력 (안경/렌즈 착용 시)",
                                           min_value=0.0, max_value=2.0,
                                           value=1.0, step=0.1)
    had_surgery = st.checkbox("라식/라섹 등 시력교정 수술 받음")

with col3:
    st.markdown("**신장(키)**")
    height = st.number_input("신장 (cm)",
                             min_value=100.0, max_value=250.0,
                             value=173.0, step=1.0,
                             help="군사경찰, JSA경비병 등의 보직은 신장 기준을 검사합니다.")

st.divider()

# ── 학과 / 자격증 입력 ──
# 세션 상태로 자격증 입력 칸 개수 관리
if "license_count" not in st.session_state:
    st.session_state.license_count = 1

c3, c4 = st.columns([5.8, 4.2])
with c3:
    st.markdown("**전공 학과** (고등학교 졸업생은 입력 생략 가능)")
    major_input = st.text_input("주전공 학과 (선택)", placeholder="예: 컴퓨터공학과, 기계공학과...")
    double_major_input = st.text_input("이중전공/복수전공 학과 (선택)", placeholder="예: 전자공학과, 드론학과...")

with c4:
    st.markdown("**보유 자격증/면허**")
    license_inputs = []
    for i in range(st.session_state.license_count):
        lic = st.text_input(f"자격증/면허 #{i+1}", key=f"license_input_{i}", placeholder="예: 정보처리기사, 1종 보통 등")
        if lic:
            license_inputs.append(lic.strip())

    # 자격증 칸 추가/삭제 버튼
    col_add, col_del = st.columns(2)
    with col_add:
        if st.button("➕ 자격증 추가", use_container_width=True):
            st.session_state.license_count += 1
            st.rerun()
    with col_del:
        if st.session_state.license_count > 1 and st.button("➖ 자격증 삭제", use_container_width=True):
            st.session_state.license_count -= 1
            st.rerun()

# ── 검색 버튼 ──
if st.button("🔍 지원 가능한 보직 찾기", type="primary", use_container_width=True):
    if not local_data:
        st.error("로컬에 데이터가 없습니다. 먼저 사이드바에서 '병무청 최신 데이터 업데이트'를 진행해 주세요.")
    else:
        teukgi_master = local_data

        # Solar LLM을 이용한 학과/자격증 일괄 정규화
        normalized_major = ""
        normalized_double_major = ""
        normalized_licenses = []

        if gemini_key:
            all_majors = set()
            all_licenses = set()
            for code, tk in teukgi_master.items():
                if tk.get("category") in ("취업맞춤특기병", "임기제부사관"):
                    continue
                all_majors.update(tk.get("majors", []))
                all_licenses.update(tk.get("licenses", []))

            # 주전공 정규화
            sorted_majors = tuple(sorted(all_majors))  # 캐시 키 고정을 위해 정렬된 tuple 사용
            sorted_licenses = tuple(sorted(all_licenses))
            if major_input:
                with st.spinner("Gemini AI로 주전공 학과명을 표준화하는 중..."):
                    normalized_major = gemini_api.normalize_major(gemini_key, major_input, sorted_majors)
            # 이중전공 정규화
            if double_major_input:
                with st.spinner("Gemini AI로 이중전공 학과명을 표준화하는 중..."):
                    normalized_double_major = gemini_api.normalize_major(gemini_key, double_major_input, sorted_majors)
            # 다중 자격증 정규화
            if license_inputs:
                with st.spinner("Gemini AI로 자격증 명칭들을 표준화하는 중..."):
                    for lic in license_inputs:
                        norm_lic = gemini_api.normalize_license(gemini_key, lic, sorted_licenses)
                        if norm_lic:
                            normalized_licenses.append(norm_lic)

        user = {
            "gun": gun,
            "vision_naked": vision_naked,
            "vision_corrected": vision_corrected,
            "had_surgery": had_surgery,
            "body_grade": body_grade,
            "height": height,
            
            "major_input": major_input,
            "double_major_input": double_major_input,
            "normalized_major": normalized_major,
            "normalized_double_major": normalized_double_major,
            
            "license_inputs": license_inputs,
            "normalized_licenses": normalized_licenses,
        }
        st.session_state.user = user
        st.session_state.results = matching.filter_eligible_teukgi(
            teukgi_master, user)
        st.session_state.teukgi_master = teukgi_master

# ── 결과 표시 ──
if st.session_state.results is not None:
    st.divider()
    results = st.session_state.results
    eligible = [r for r in results if r[1]["eligible"]]

    # 현재 KST 기준 시간 구하기
    now = datetime.now(timezone(timedelta(hours=9)))

    # 모집 일정 상태 매핑 및 가공
    eligible_with_status = []
    for tk, elig in eligible:
        status, period_str = get_recruitment_status(tk, now)
        eligible_with_status.append((tk, elig, status, period_str))

    st.subheader(f"지원 가능한 보직 {len(eligible)}개를 찾았어요")

    if not eligible:
        st.info("조건을 만족하는 보직이 없거나 필터 조건에 맞는 모집 일정이 없습니다. 조건을 조정해 보세요.")

    # 표 헤더 (Table Header)
    st.markdown("---")
    header_cols = st.columns([1, 1.8, 4.2, 3.0])
    header_cols[0].markdown("**군**")
    header_cols[1].markdown("**분류**")
    header_cols[2].markdown("**특기명 (코드)**")
    header_cols[3].markdown("**작업**")
    st.markdown("<hr style='margin: 0.5em 0px; border-color: rgba(49, 51, 63, 0.2);'>", unsafe_allow_html=True)

    # 표 데이터 행 (Table Rows)
    prev_priority = None
    for i, (tk, elig) in enumerate(eligible):
        cur_priority = elig.get("priority", 0)

        # 우선순위 그룹이 바뀔 때 섹션 헤더 삽입
        if cur_priority != prev_priority:
            if cur_priority == 2:
                st.markdown(
                    "<div style='margin: 0.6em 0 0.2em; padding: 6px 12px; "
                    "background: linear-gradient(90deg,#1B5E2022,transparent); "
                    "border-left: 4px solid #2E7D32; border-radius: 4px; "
                    "font-weight: 700; font-size: 0.95em; color: #1B5E20;'>"
                    "🎯 내 조건에 직접 매칭된 보직</div>",
                    unsafe_allow_html=True,
                )
            elif cur_priority == 0 and prev_priority is not None:
                st.markdown(
                    "<div style='margin: 1em 0 0.2em; padding: 6px 12px; "
                    "background: linear-gradient(90deg,#37474F15,transparent); "
                    "border-left: 4px solid #78909C; border-radius: 4px; "
                    "font-weight: 600; font-size: 0.9em; color: #546E7A;'>"
                    "📋 기타 지원 가능 보직 (전공·자격 제한 없음)</div>",
                    unsafe_allow_html=True,
                )
            prev_priority = cur_priority

        row_cols = st.columns([1, 1.8, 4.2, 3.0])
        
        # 1. 군 (Badge)
        gun = tk['gun']
        if gun == "육군":
            gun_color = "#2E7D32"
        elif gun == "해군":
            gun_color = "#1565C0"
        elif gun == "공군":
            gun_color = "#EF6C00"
        elif gun == "해병대":
            gun_color = "#C62828"
        else:
            gun_color = "#37474F"
        row_cols[0].markdown(f"<span style='background-color: {gun_color}1a; color: {gun_color}; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 0.85em;'>{gun}</span>", unsafe_allow_html=True)
        
        # 2. 분류
        category = tk.get('category', '')
        row_cols[1].markdown(f"<span style='font-size: 0.9em; font-weight: 500;'>{category}</span>", unsafe_allow_html=True)
        
        # 3. 특기명 (코드) + 힌트
        hint = get_hint(tk['code'], tk['name'])
        name_md = f"**{tk['name']}** <code style='font-size: 0.8em; color: #78909C; background-color: #ECEFF1; padding: 2px 5px; border-radius: 3px;'>{tk['code']}</code>"
        if hint:
            name_md += f"<br><span style='font-size: 0.8em; color: #E65100;'>{hint}</span>"
        row_cols[2].markdown(name_md, unsafe_allow_html=True)

        
        # 4. 작업 (자세히, 요약, 담기)
        with row_cols[3]:
            btn_col1, btn_col2, btn_col3 = st.columns(3)
            with btn_col1:
                # 자세히 토글 버튼
                is_det_active = st.session_state.active_details == tk['code']
                if st.button("자세히", key=f"det_{tk['code']}", type="secondary" if not is_det_active else "primary", use_container_width=True):
                    if is_det_active:
                        st.session_state.active_details = None
                    else:
                        st.session_state.active_details = tk['code']
                        st.session_state.active_summary = None
                    st.rerun()
            with btn_col2:
                # 요약 토글 버튼
                is_sum_active = st.session_state.active_summary == tk['code']
                if st.button("요약", key=f"sum_{tk['code']}", type="secondary" if not is_sum_active else "primary", use_container_width=True):
                    if is_sum_active:
                        st.session_state.active_summary = None
                    else:
                        st.session_state.active_summary = tk['code']
                        st.session_state.active_details = None
                    st.rerun()
            with btn_col3:
                # 담기 버튼
                if st.button("담기", key=f"cmp_{tk['code']}", use_container_width=True):
                    if tk not in st.session_state.compare:
                        st.session_state.compare.append(tk)
                        st.toast(f"'{tk['name']}' 보직을 비교함에 담았습니다! 🧭")

        # ── [요약] 화면 표시 ──
        if st.session_state.active_summary == tk['code']:
            with st.container(border=True):
                st.markdown(f"##### 🧭 **{tk['name']} ({tk['code']}) 요약 정보**")
                st.markdown("**🔍 지원 자격 판정 결과:**")
                for r in elig["reasons"]:
                    st.markdown(f"- {r}")
                
                if gemini_key:
                    with st.spinner("Gemini AI로 업무 요약 중..."):
                        desc = gemini_api.summarize_duty(gemini_key, tk["name"])
                    if desc:
                        st.info(desc)
                else:
                    st.caption("ℹ️ Google Gemini 키를 설정하시면 AI가 요약해주는 상세 업무 정보를 볼 수 있습니다.")

        # ── [자세히] 화면 표시 (지원자격 + 과거 입영일, 평균 지원율, 모집 주기 등 통계 노출) ──
        if st.session_state.active_details == tk['code']:
            with st.container(border=True):
                st.markdown(f"##### 📊 **{tk['name']} ({tk['code']}) 과거 모집 및 지원 통계**")

                # 가산점 힌트
                hint = get_hint(tk['code'], tk['name'])
                if hint:
                    st.info(hint)
                    st.markdown("<br>", unsafe_allow_html=True)


                # 접수현황 API/Mock 정보 가져오기
                with st.spinner("통계 데이터를 가져오는 중..."):
                    stats = mma_api.get_jeopsu_details(mma_key, tk['code'], tk['name'], tk['gun'], tk['category'])

                
                # 통계 요약 박스 (평균 지원율 & 모집 주기)
                col_stat1, col_stat2 = st.columns(2)
                with col_stat1:
                    st.markdown(
                        f"""
                        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 5px solid #1565C0; margin-bottom: 10px;">
                            <p style="margin: 0; font-size: 0.85em; color: #546E7A; font-weight: bold;">평균 지원률</p>
                            <h2 style="margin: 5px 0 0 0; color: #1565C0; font-size: 1.8em;">📊 {stats['avg_rate']:.2f}</h2>
                            <span style="font-size: 0.75em; color: #78909C;">전체 모집의 평균 경쟁률</span>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                with col_stat2:
                    st.markdown(
                        f"""
                        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 8px; border-left: 5px solid #9C27B0; margin-bottom: 10px;">
                            <p style="margin: 0; font-size: 0.85em; color: #546E7A; font-weight: bold;">모집 주기</p>
                            <h2 style="margin: 5px 0 0 0; color: #9C27B0; font-size: 1.8em;">📅 {stats['cycle_months']:.2f}개월</h2>
                            <span style="font-size: 0.75em; color: #78909C;">평균 입영일 간격</span>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                
                st.markdown("<p style='font-size:0.8em; color:gray; text-align:center;'>* 위 통계는 과거 데이터를 기반으로 계산한 대략적인 분석 결과입니다.</p>", unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                
                # 상세 입영일/지원현황 표 렌더링
                det_hdr = st.columns([1.8, 1.8, 2.5, 3.5])
                det_hdr[0].markdown("**입영일**")
                det_hdr[1].markdown("**분류**")
                det_hdr[2].markdown("**입영부대**")
                det_hdr[3].markdown("**지원률**")
                st.markdown("<hr style='margin: 0.2em 0px; border-color: rgba(49, 51, 63, 0.15);'>", unsafe_allow_html=True)
                
                for r in stats["rounds"]:
                    r_cols = st.columns([1.8, 1.8, 2.5, 3.5])
                    
                    # 입영년월 + 라벨 배치
                    lbl_color = "#ECEFF1" if r['label'] == "전역" else "#FCE4EC" if r['label'] == "접수마감" else "#E8F5E9"
                    lbl_text_color = "#455A64" if r['label'] == "전역" else "#C2185B" if r['label'] == "접수마감" else "#2E7D32"
                    r_cols[0].markdown(f"**{r['enlist_date']}** <span style='background-color: {lbl_color}; color: {lbl_text_color}; padding: 2px 6px; border-radius: 3px; font-size: 0.75em; font-weight:bold;'>{r['label']}</span>", unsafe_allow_html=True)
                    
                    r_cols[1].markdown(f"<span style='font-size:0.9em;'>{r['category']}</span>", unsafe_allow_html=True)
                    r_cols[2].markdown(f"<span style='font-size:0.9em;'>{r['unit']}</span>", unsafe_allow_html=True)
                    r_cols[3].markdown(f"<span style='font-size:0.9em;'>정원: **{r['plan']}**명 | 지원: **{r['applied']}**명 (**{r['rate']:.2f}**)</span>", unsafe_allow_html=True)
                    st.markdown("<hr style='margin: 0.1em 0px; border-color: rgba(0, 0, 0, 0.04);'>", unsafe_allow_html=True)

        st.markdown("<hr style='margin: 0.3em 0px; border-color: rgba(49, 51, 63, 0.08);'>", unsafe_allow_html=True)

# ── 비교 영역 ──
if st.session_state.compare:
    st.divider()
    st.subheader(f"보직 비교 ({len(st.session_state.compare)}개)")
    ccols = st.columns(len(st.session_state.compare))
    for col, tk in zip(ccols, st.session_state.compare):
        with col:
            with st.container(border=True):
                st.markdown(f"**{tk['name']} ({tk['code']})**")
                category_str = f" · {tk['category']}" if tk.get("category") else ""
                st.caption(f"{tk['gun']}{category_str}")
                for hangmok, (low, high) in tk.get("conditions", {}).items():
                    st.text(f"{hangmok}: {low}~{high}")
    if st.button("비교 초기화"):
        st.session_state.compare = []
        st.rerun()
