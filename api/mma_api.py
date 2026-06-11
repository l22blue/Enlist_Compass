"""
병무청 공공 API 호출 모듈
- 군사특기마스타(gsTgMastr): 특기 목록 + 신체조건(시력/등급) + 모집일정
- 지원가능정보(mjbJiWon): 자격/면허/전공 매칭
"""
import requests
import xml.etree.ElementTree as ET
from collections import defaultdict
import streamlit as st

GSTG_URL = "http://apis.data.go.kr/1300000/gsTgMastr/list/gsTgMastr/list"
JIWON_URL = "http://apis.data.go.kr/1300000/mjbJiWon/list"


def _fetch_all(url, service_key, max_pages=150, rows=100):
    """페이지네이션 돌면서 전체 item 수집"""
    all_items = []
    for page in range(1, max_pages + 1):
        params = {
            "serviceKey": service_key,
            "numOfRows": rows,
            "pageNo": page,
        }
        try:
            res = requests.get(url, params=params, timeout=10)
            res.encoding = "utf-8"
            root = ET.fromstring(res.text)
        except Exception as e:
            st.error(f"API 호출 오류: {e}")
            break

        items = []
        for item in root.iter("item"):
            d = {child.tag: (child.text or "").strip() for child in item}
            items.append(d)

        if not items:
            break
        all_items.extend(items)

        total = root.findtext(".//totalCount")
        if total and len(all_items) >= int(total):
            break

    return all_items


@st.cache_data(ttl=3600)
def get_teukgi_master(service_key):
    """
    군사특기마스타 호출 → 특기코드 기준으로 그룹핑.
    한 특기에 여러 기준항목(시력/신장/등급 등) 행이 있으므로 묶어준다.
    반환: { 특기코드: {기본정보 + conditions: {항목명: (최저, 최고)}} }
    """
    raw = _fetch_all(GSTG_URL, service_key)
    teukgi = {}

    for row in raw:
        code = row.get("gsteukgiCd", "")
        if not code:
            continue

        if code not in teukgi:
            teukgi[code] = {
                "code": code,
                "name": row.get("gsteukgiNm", ""),
                "gun": row.get("gunGbnm", ""),
                "field": row.get("mjbgteukgiNm", ""),       # 모집병과특기명
                "category": row.get("mjgubNm", ""),        # 모집구분명 (기술행정병, 전문특기병 등)
                "apply_start": row.get("jeopsuSjdtm", ""),  # 접수 시작
                "apply_end": row.get("jeopsuJrdtm", ""),    # 접수 종료
                "enlist_start": row.get("iyyjsijakYm", ""), # 입영예정 시작월
                "enlist_end": row.get("iyyjjongryoYm", ""),
                "year": row.get("mojipYy", ""),
                "round": row.get("mojipTms", ""),
                "conditions": {},  # {기준항목명: (최저값, 최고값)}
            }

        # 신체조건/기준 항목 누적
        hangmok = row.get("gjhangmokNm", "")
        if hangmok:
            teukgi[code]["conditions"][hangmok] = (
                row.get("cjgijunVl", ""),  # 최저
                row.get("cggijunVl", ""),  # 최고
            )

    return teukgi


@st.cache_data(ttl=3600)
def get_jiwon_info(service_key):
    """
    지원가능정보 호출 → 특기코드 기준으로 자격/전공 요건 그룹핑.
    반환: { 특기코드: {licenses:[...], majors:[...]} }
    """
    raw = _fetch_all(JIWON_URL, service_key)
    info = defaultdict(lambda: {"licenses": [], "majors": [], "raw": []})

    for row in raw:
        code = row.get("gsteukgiCd") or ""
        if not code:
            continue
        info[code]["raw"].append(row)
        
        gubun = row.get("gubun", "")
        name = row.get("gtcdNm2", "")
        if not name:
            continue
            
        if gubun == "자격":
            info[code]["licenses"].append(name)
        else:
            # '학과', '학력' 등은 전공으로 판단
            info[code]["majors"].append(name)

    # 중복 제거
    for code in info:
        info[code]["licenses"] = list(set(info[code]["licenses"]))
        info[code]["majors"] = list(set(info[code]["majors"]))

    return dict(info)


@st.cache_data
def load_local_data():
    """
    로컬 캐시된 JSON 파일(data/military_specialties.json)을 로드합니다.
    """
    import os
    import json
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    data_path = os.path.join(project_root, "data", "military_specialties.json")
    
    if os.path.exists(data_path):
        try:
            with open(data_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            st.error(f"로컬 보직 데이터 파일을 읽는 중 오류 발생: {e}")
    return None
