"""
Google Gemini LLM 연동 모듈 (Upstage Solar 대체)
- 사용자가 자유 입력한 학과/자격증을 병무청 코드 목록과 매칭 (연결고리)
- 보직 설명을 쉬운 말로 요약
"""
import json
import urllib.request
import urllib.error
import streamlit as st

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


def _call_gemini(api_key, system, user, temperature=0.1):
    """Gemini REST API 직접 호출 (requests 미사용)"""
    url = f"{GEMINI_URL}?key={api_key}"
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"parts": [{"text": user}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": 256,
        },
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["candidates"][0]["content"]["parts"][0]["text"].strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        st.warning(f"Gemini 호출 실패: {e.code} {e.reason} — {body[:200]}")
        return ""
    except Exception as e:
        st.warning(f"Gemini 호출 실패: {e}")
        return ""


@st.cache_data(ttl=86400)
def normalize_major(api_key, user_input, candidate_list):
    """
    사용자 입력 학과명을 후보 목록 중 가장 유사한 항목으로 매칭.
    candidate_list: 병무청 데이터에서 추출한 인정 학과/계열 목록
    반환: 매칭된 학과명 (없으면 빈 문자열)
    """
    if not user_input or not candidate_list:
        return ""

    system = (
        "너는 한국 군 모집 시스템의 학과 매칭 도우미야. "
        "사용자가 입력한 학과명을 주어진 후보 목록 중 의미가 가장 가까운 "
        "하나로만 매칭해. 반드시 후보 목록에 있는 정확한 텍스트로만 답하고, "
        "적절한 매칭이 없으면 '없음'이라고만 답해. 다른 설명은 절대 붙이지 마."
    )
    user = (
        f"사용자 입력: {user_input}\n\n"
        f"후보 목록: {', '.join(candidate_list)}\n\n"
        f"가장 유사한 항목 하나만 출력:"
    )
    result = _call_gemini(api_key, system, user)
    return "" if result == "없음" else result


@st.cache_data(ttl=86400)
def normalize_license(api_key, user_input, candidate_list):
    """사용자 입력 자격증명을 인정 자격증 목록과 매칭"""
    if not user_input or not candidate_list:
        return ""

    system = (
        "너는 한국 군 모집 시스템의 자격증 매칭 도우미야. "
        "사용자가 입력한 자격증/면허명을 주어진 후보 목록 중 "
        "가장 가까운 하나로만 매칭해. 후보 목록의 정확한 텍스트로만 답하고, "
        "매칭이 없으면 '없음'이라고만 답해. 다른 설명 금지."
    )
    user = (
        f"사용자 입력: {user_input}\n\n"
        f"후보 목록: {', '.join(candidate_list)}\n\n"
        f"가장 유사한 항목 하나만 출력:"
    )
    result = _call_gemini(api_key, system, user)
    return "" if result == "없음" else result


@st.cache_data(ttl=86400)
def summarize_duty(api_key, teukgi_name, raw_desc=""):
    """보직명(+설명)을 받아 '무슨 일을 하는지' 2~3문장으로 쉽게 요약"""
    system = (
        "너는 군 보직을 쉽게 설명해주는 도우미야. "
        "고등학생도 이해할 수 있게, 이 보직이 실제로 무슨 일을 하는지 "
        "2~3문장으로 친근하게 설명해. 군사 전문용어는 풀어서 써."
    )
    user = f"보직명: {teukgi_name}\n참고 설명: {raw_desc or '(없음)'}\n\n쉬운 설명:"
    return _call_gemini(api_key, system, user, temperature=0.5)
