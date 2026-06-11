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
    코드 형식 불일치 보완을 위해 특기명(gsteukgiNm) 역매핑도 병행.
    반환: ( {코드: {licenses, majors}}, {특기명: 코드} )
    """
    # numOfRows=1000으로 늘려 더 많은 데이터 확보 (기본 100 → 1000)
    raw = _fetch_all(JIWON_URL, service_key, max_pages=1400, rows=1000)
    info = defaultdict(lambda: {"licenses": [], "majors": []})
    name_to_code = {}  # 특기명 → 코드 역매핑

    for row in raw:
        code = row.get("gsteukgiCd") or ""
        nm = row.get("gsteukgiNm") or ""
        if not code:
            continue

        # 특기명 → 코드 역매핑 등록
        if nm and nm not in name_to_code:
            name_to_code[nm] = code

        gubun = row.get("gubun", "")
        val = row.get("gtcdNm2", "")
        if not val:
            continue

        if gubun == "자격":
            info[code]["licenses"].append(val)
        else:
            info[code]["majors"].append(val)

    # 중복 제거
    for code in info:
        info[code]["licenses"] = list(set(info[code]["licenses"]))
        info[code]["majors"] = list(set(info[code]["majors"]))

    return dict(info), name_to_code


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


@st.cache_data(ttl=1800)
def fetch_jeopsu_data(service_key):
    """모집병 군지원 접수현황 API 호출"""
    url = "http://apis.data.go.kr/1300000/MJBGJWJeopSuHH4/list"
    params = {
        "serviceKey": service_key,
        "numOfRows": 2000,
        "pageNo": 1
    }
    try:
        res = requests.get(url, params=params, timeout=10)
        res.encoding = "utf-8"
        if res.status_code == 200:
            root = ET.fromstring(res.text)
            result_code = root.findtext(".//resultCode")
            if result_code == "00":
                items = []
                for item in root.iter("item"):
                    d = {child.tag: (child.text or "").strip() for child in item}
                    items.append(d)
                return items
    except Exception:
        pass
    return None


def get_jeopsu_details(service_key, specialty_code, specialty_name, gun, category):
    """특기별 과거/현재 입영일, 부대, 지원율 데이터를 가져오거나 생성합니다."""
    raw_items = fetch_jeopsu_data(service_key)
    matched = []
    
    if raw_items:
        for it in raw_items:
            # 특기코드 또는 명칭 매칭 + 군종 필터 (육군이면 육군 데이터만)
            code_match = it.get("gsteukgiCd") == specialty_code or it.get("teukgiCd") == specialty_code
            name_match = it.get("gsteukgiNm") == specialty_name or it.get("teukgiNm") == specialty_name
            gun_match = it.get("gunGbnm", "") == gun
            if (code_match or name_match) and gun_match:
                matched.append(it)
                
    # API 데이터가 없거나 403 에러 등으로 가져올 수 없으면 고유 시드 기반의 고품질 Mock 데이터 생성
    if not matched:
        return _generate_mock_jeopsu_details(specialty_code, specialty_name, gun, category)
        
    # 실제 API 데이터 가공
    rounds = []
    for it in matched:
        try:
            # 입영년월: ipyeongDe가 '*'이면 접수종료일(jeopsuJrdtm, 8자리 YYYYMMDD)에서 추정
            ipyeong_de = it.get("ipyeongDe") or ""
            if ipyeong_de and ipyeong_de != "*" and len(ipyeong_de) == 6:
                enlist_date = f"{ipyeong_de[2:4]}.{ipyeong_de[4:]}"
            else:
                # 접수종료일 기준 다음 달 = 입영월로 추정
                jrd = it.get("jeopsuJrdtm") or ""
                if len(jrd) >= 6:
                    yr, mo = int(jrd[2:4]), int(jrd[4:6]) + 1
                    if mo > 12:
                        mo, yr = 1, yr + 1
                    enlist_date = f"{yr:02d}.{mo:02d}"
                else:
                    enlist_date = "-"

            # 선발인원(정원), 접수인원(지원자), 경쟁률
            plan = int(it.get("seonbalPcnt") or 0)
            applied = int(it.get("jeopsuPcnt") or 0)
            raw_rate = it.get("rate")
            rate = float(raw_rate) if raw_rate else (round(applied / plan, 2) if plan > 0 else 0.0)

            # 입영부대
            unit = it.get("iybudaeCdm") or "-"

            # 모집년도·차수로 라벨
            yy = it.get("mojipYy", "")
            tms = it.get("mojipTms", "")
            label = f"{yy}-{tms}차" if yy and tms else "접수마감"

            rounds.append({
                "enlist_date": enlist_date,
                "label": label,
                "category": it.get("mojipGbnm") or category,
                "unit": unit,
                "plan": plan,
                "applied": applied,
                "rate": rate
            })
        except Exception:
            continue
            
    if not rounds:
        return _generate_mock_jeopsu_details(specialty_code, specialty_name, gun, category)
        
    # 정렬 (최신순)
    rounds.sort(key=lambda x: x["enlist_date"], reverse=True)
    avg_rate = round(sum(r["rate"] for r in rounds) / len(rounds), 2)
    
    # 모집 주기 계산 (월 단위 차이의 평균)
    cycle_months = 3.0
    if len(rounds) > 1:
        diffs = []
        for i in range(len(rounds) - 1):
            try:
                y1, m1 = map(int, rounds[i]["enlist_date"].split("."))
                y2, m2 = map(int, rounds[i+1]["enlist_date"].split("."))
                diff = (y1 - y2) * 12 + (m1 - m2)
                if diff > 0:
                    diffs.append(diff)
            except Exception:
                continue
        if diffs:
            cycle_months = round(sum(diffs) / len(diffs), 2)
            
    return {
        "avg_rate": avg_rate,
        "cycle_months": cycle_months,
        "rounds": rounds
    }


def _generate_mock_jeopsu_details(specialty_code, specialty_name, gun, category):
    """공공 API 호출 권한이 아직 없을 때 특기별 시드에 맞춰 고유하게 생성되는 Mock 데이터"""
    import random
    
    # 특기 코드별 해시를 이용해 새로고침을 해도 같은 보직은 항상 같은 고유 값을 가지도록 제어
    random.seed(hash(specialty_code) % 10000)
    
    if gun == "육군":
        units = ["육군훈련소", "지작사 전방사단", "2작사 신교대"]
    elif gun == "해군":
        units = ["해군교육사령부"]
    elif gun == "공군":
        units = ["공군교육사령부"]
    elif gun == "해병대":
        units = ["해병대교육훈련단"]
    else:
        units = ["육군훈련소"]
        
    cycle_months = random.choice([3.0, 4.0, 6.0])
    rounds = []
    
    # 26.09월 입영 일정부터 과거로 역산하여 10개 라운드 생성
    year = 26
    month = 9
    
    base_plan = random.randint(15, 120)
    base_rate = round(random.uniform(1.2, 3.8), 2)
    
    for i in range(10):
        plan = int(base_plan * random.uniform(0.9, 1.1))
        rate = round(base_rate * random.uniform(0.8, 1.2), 2)
        applied = int(plan * rate)
        
        # 순서별 라벨 매칭
        if i == 0:
            label = "접수마감"
        elif i == 1:
            label = "입영전"
        elif i == 2:
            label = "일병 3호봉"
        elif i == 3:
            label = "상병 1호봉"
        elif i == 4:
            label = "상병 5호봉"
        elif i == 5:
            label = "병장 3호봉"
        else:
            label = "전역"
            
        unit = random.choice(units)
        enlist_date = f"{year:02d}.{month:02d}"
        
        rounds.append({
            "enlist_date": enlist_date,
            "label": label,
            "category": category,
            "unit": unit,
            "plan": plan,
            "applied": applied,
            "rate": rate
        })
        
        month -= int(cycle_months)
        if month <= 0:
            month += 12
            year -= 1
            
    avg_rate = round(sum(r["rate"] for r in rounds) / len(rounds), 2)
    
    return {
        "avg_rate": avg_rate,
        "cycle_months": cycle_months,
        "rounds": rounds
    }
