"""
자격 게이트 필터링 로직
점수 계산 없이 "지원 가능 여부(통과/탈락)"만 판정한다.
"""


def _to_float(v):
    try:
        return float(str(v).replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def find_vision_condition(conditions):
    """conditions dict에서 시력 관련 항목을 찾아 최저기준값 반환.
    gjhangmokNm에 '시력'이 포함된 항목을 탐색.
    ※ 실제 항목명은 explore_api.py 결과로 확인 후 키워드 보정."""
    for name, (low, high) in conditions.items():
        if "시력" in name:
            return _to_float(low), name
    return None, None


def find_grade_condition(conditions):
    """신체등급 관련 항목 탐색 (최저신체등급)"""
    for name, (low, high) in conditions.items():
        if "신체등급" in name or "신체 등급" in name or "등급" in name:
            return _to_float(low), name
    return None, None


def check_eligibility(teukgi, user):
    """
    하나의 특기(teukgi)에 대해 사용자(user)가 지원 가능한지 판정.
    반환: {
        "eligible": bool,        # 모든 필수 조건 통과 여부
        "reasons": [str, ...],   # 통과/탈락 사유 목록
        "blockers": [str, ...],  # 탈락 사유만
    }

    user 예시:
    {
        "gun": "육군",            # 희망 군종 ("전체"면 무시)
        "vision_naked": 0.8,      # 나안시력
        "body_grade": 2,          # 신체등급 (1/2/3/4)
        "major_input": "컴퓨터공학과",
        "license_input": "정보처리기사",
        "normalized_major": "컴퓨터공학과",
        "normalized_license": "정보처리기사"
    }
    """
    conditions = teukgi.get("conditions", {})
    reasons, blockers = [], []
    eligible = True

    # ① 군종 필터
    want_gun = user.get("gun", "전체")
    if want_gun != "전체" and teukgi.get("gun"):
        if want_gun != teukgi["gun"]:
            return {"eligible": False, "reasons": [f"군종 불일치 ({teukgi['gun']})"],
                    "blockers": [f"군종 불일치 ({teukgi['gun']})"]}

    # ② 시력 필터 (나안 기준)
    vmin, vname = find_vision_condition(conditions)
    if vmin is not None:
        uv = user.get("vision_naked")
        if uv is not None:
            if uv >= vmin:
                reasons.append(f"✅ 시력 충족 (요구 {vmin} / 내 나안 {uv})")
            else:
                msg = f"❌ 시력 미달 (요구 {vmin} / 내 나안 {uv})"
                reasons.append(msg)
                blockers.append(msg)
                eligible = False
        else:
            reasons.append(f"⚠️ 시력 요구 {vmin} (내 시력 미입력)")

    # ③ 신체등급 필터
    gmin, gmin_name = find_grade_condition(conditions)
    if gmin is not None:
        ug = user.get("body_grade")
        if ug is not None:
            # 등급은 숫자가 낮을수록 좋음(1급>2급). 최저기준 이하면 통과
            if ug <= gmin:
                reasons.append(f"✅ 신체등급 충족 (요구 {gmin}급 이내 / 내 {ug}급)")
            else:
                msg = f"❌ 신체등급 미달 (요구 {gmin}급 이내 / 내 {ug}급)"
                reasons.append(msg)
                blockers.append(msg)
                eligible = False
        else:
            reasons.append(f"⚠️ 신체등급 요구 {gmin}급 (미입력)")

    # ④ 학과 및 자격증 필터
    req_majors = teukgi.get("majors", [])
    req_licenses = teukgi.get("licenses", [])

    # 만약 해당 보직에 아무런 전공/자격 제한이 없으면 무조건 통과
    if not req_majors and not req_licenses:
        reasons.append("✅ 전공/자격 제한 없음")
    else:
        user_major = user.get("normalized_major") or user.get("major_input") or ""
        user_double_major = user.get("normalized_double_major") or user.get("double_major_input") or ""
        
        # 다중 자격증 지원을 위해 리스트 타입 지원
        user_licenses = user.get("normalized_licenses") or user.get("license_inputs") or []
        if not user_licenses and user.get("license_input"):
            user_licenses = [user.get("license_input")]

        has_major_match = False
        has_license_match = False

        # 1. 학과 매칭 체크 (주전공 및 이중전공 모두 검사)
        majors_to_check = [m for m in [user_major, user_double_major] if m]
        if req_majors and majors_to_check:
            for user_m in majors_to_check:
                user_m_clean = user_m.replace(" ", "").lower()
                for m in req_majors:
                    m_clean = m.replace(" ", "").lower()
                    if user_m_clean in m_clean or m_clean in user_m_clean:
                        has_major_match = True
                        reasons.append(f"✅ 전공 충족 (요구: {m} / 내 전공: {user_m})")
                        break
                if has_major_match:
                    break

        # 2. 자격증 매칭 체크 (여러 자격증 중 하나라도 일치하면 충족)
        if req_licenses and user_licenses:
            for user_l in user_licenses:
                if not user_l:
                    continue
                user_l_clean = user_l.replace(" ", "").lower()
                for l in req_licenses:
                    l_clean = l.replace(" ", "").lower()
                    if user_l_clean in l_clean or l_clean in user_l_clean:
                        has_license_match = True
                        reasons.append(f"✅ 자격증 충족 (요구: {l} / 내 자격증: {user_l})")
                        break
                if has_license_match:
                    break

        # 매칭되는 것이 전혀 없다면 조건 탈락
        if not has_major_match and not has_license_match:
            msg = "❌ 전공/자격증 조건 미달 (관련 전공 또는 자격증 필요)"
            reasons.append(msg)
            blockers.append(msg)
            eligible = False

    # 매칭 우선순위 계산:
    #   2 = 학과 또는 자격증이 구체적으로 매칭됨
    #   1 = 시력/신체 조건만 있거나 일부 매칭
    #   0 = 전공/자격 제한 없음 (무조건 통과)
    if not req_majors and not req_licenses:
        priority = 0
    elif has_major_match or has_license_match:
        priority = 2
    else:
        priority = 1

    return {"eligible": eligible, "reasons": reasons, "blockers": blockers, "priority": priority}


def filter_eligible_teukgi(teukgi_master, user, include_unknown=True):
    """
    전체 특기 중 사용자가 지원 가능한 것만 필터링.
    우선순위: 2(직접 매칭) > 1(부분 매칭) > 0(제한 없음)
    반환: [(teukgi, eligibility), ...]
    """
    results = []
    for code, tk in teukgi_master.items():
        # 취업맞춤특기병 및 임기제부사관 제외 (병사 대상 서비스)
        category = tk.get("category")
        if category in ("취업맞춤특기병", "임기제부사관") or tk.get("name", "").startswith("(맞춤)"):
            continue
        elig = check_eligibility(tk, user)
        if elig["eligible"]:
            results.append((tk, elig))
        elif include_unknown and not tk.get("conditions"):
            # 조건 데이터 자체가 없으면 '확인 필요'로 포함
            elig["reasons"].append("⚠️ 신체조건 데이터 없음 - 직접 확인 필요")
            results.append((tk, elig))

    # 정렬: 블로커 없는 것 우선, 그 안에서 priority 높은 것 우선, 동순위는 이름순
    results.sort(key=lambda x: (
        len(x[1]["blockers"]),          # 블로커 없는 것 우선 (오름차순)
        -x[1].get("priority", 0),       # priority 높은 것 우선 (내림차순)
        x[0]["name"],                   # 이름 가나다순
    ))
    return results
