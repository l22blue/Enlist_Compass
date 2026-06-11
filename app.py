"""
입대 나침반 (EnlistCompass) — 메인 Streamlit 앱
실행: streamlit run app.py
"""
import streamlit as st
from datetime import datetime, timezone, timedelta
from api import mma_api, solar_api
from utils import matching

st.set_page_config(page_title="입대 나침반", page_icon="🧭", layout="wide")


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
if "user" not in st.session_state:
    st.session_state.user = {}
if "results" not in st.session_state:
    st.session_state.results = None
if "compare" not in st.session_state:
    st.session_state.compare = []

# ── 로컬 데이터 확인 ──
local_data = mma_api.load_local_data()

# secrets.toml에 키가 있으면 자동 사용, 없으면 입력창 표시
_mma = get_secret("MMA_API_KEY")
_solar = get_secret("SOLAR_API_KEY")

# ── 사이드바: 키 입력 ──
with st.sidebar:
    st.title("🧭 입대 나침반")
    st.caption("내 조건으로 지원 가능한 군 보직 찾기")
    st.divider()

    if _mma:
        mma_key = _mma
    else:
        st.subheader("🔑 API 키 설정")
        mma_key = st.text_input("병무청 API 키", type="password",
                                help="공공데이터포털에서 발급한 키")

    if _solar:
        solar_key = _solar
    else:
        solar_key = st.text_input("Upstage Solar 키 (선택)", type="password",
                                  help="학과/자격증 자동 매칭에 사용")

    st.divider()
    st.info("⚠️ 본 서비스의 정보는 참고용이며, "
            "실제 모집 요건은 병무청 공고를 확인하세요.")

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

col1, col2 = st.columns(2)

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

st.divider()

# ── 학과 / 자격증 입력 ──
# 세션 상태로 자격증 입력 칸 개수 관리
if "license_count" not in st.session_state:
    st.session_state.license_count = 1

c3, c4 = st.columns(2)
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

        if solar_key:
            all_majors = set()
            all_licenses = set()
            for code, tk in teukgi_master.items():
                if tk.get("category") in ("취업맞춤특기병", "임기제부사관"):
                    continue
                all_majors.update(tk.get("majors", []))
                all_licenses.update(tk.get("licenses", []))

            # 주전공 정규화
            if major_input:
                with st.spinner("Solar LLM으로 주전공 학과명을 표준화하는 중..."):
                    normalized_major = solar_api.normalize_major(solar_key, major_input, list(all_majors))
            # 이중전공 정규화
            if double_major_input:
                with st.spinner("Solar LLM으로 이중전공 학과명을 표준화하는 중..."):
                    normalized_double_major = solar_api.normalize_major(solar_key, double_major_input, list(all_majors))
            # 다중 자격증 정규화
            if license_inputs:
                with st.spinner("Solar LLM으로 자격증 명칭들을 표준화하는 중..."):
                    for lic in license_inputs:
                        norm_lic = solar_api.normalize_license(solar_key, lic, list(all_licenses))
                        if norm_lic:
                            normalized_licenses.append(norm_lic)

        user = {
            "gun": gun,
            "vision_naked": vision_naked,
            "vision_corrected": vision_corrected,
            "had_surgery": had_surgery,
            "body_grade": body_grade,
            
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

    # 필터 옵션 UI
    show_only_active = st.checkbox("🟢 현재 접수 중 또는 🔵 접수 예정인 보직만 보기", value=False)

    if show_only_active:
        eligible_with_status = [item for item in eligible_with_status if item[2] in ("OPEN", "UPCOMING")]

    st.subheader(f"지원 가능한 보직 {len(eligible_with_status)}개를 찾았어요")

    if not eligible_with_status:
        st.info("조건을 만족하는 보직이 없거나 필터 조건에 맞는 모집 일정이 없습니다. "
                "조건을 조정하거나 필터 체크박스를 해제해 보세요.")

    # 카드 3열 그리드
    cols = st.columns(3)
    for i, (tk, elig, status, period_str) in enumerate(eligible_with_status):
        with cols[i % 3]:
            with st.container(border=True):
                st.markdown(f"**{tk['name']} ({tk['code']})**")
                category_str = f" · {tk['category']}" if tk.get("category") else ""
                st.caption(f"{tk['gun']}{category_str} · {tk.get('field', '')}")

                # 모집 일정 (접수 종료된 과거 정보 등은 period_str이 빈 값으로 오며 미표출됨)
                if period_str:
                    st.caption(period_str)

                # 통과 사유
                for r in elig["reasons"]:
                    st.caption(r)

                # Solar 요약 (키 있을 때만)
                if solar_key:
                    if st.button("💡 하는 업무 요약", key=f"sum_{tk['code']}"):
                        with st.spinner("요약 중..."):
                            desc = solar_api.summarize_duty(solar_key, tk["name"])
                        st.info(desc)

                # 비교 담기
                if st.button("➕ 비교 담기", key=f"cmp_{tk['code']}"):
                    if tk not in st.session_state.compare:
                        st.session_state.compare.append(tk)

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
