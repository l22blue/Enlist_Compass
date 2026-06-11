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

def find_height_condition(conditions):
    """신장(키) 관련 항목 탐색"""
    for name, (low, high) in conditions.items():
        if "신장" in name or "키" in name:
            return _to_float(low), _to_float(high), name
    return None, None, None


def is_major_compatible(user_major, req_major):
    """
    사용자 전공과 모집 요구 전공이 호환되는지 판정 (유연한 휴리스틱 적용).
    """
    if not user_major or not req_major:
        return False
    u = user_major.replace(" ", "").lower()
    r = req_major.replace(" ", "").lower()

    # 1. 신학(Theology) 학과 오매칭 차단 (예: 신학과 vs 정보통신학과)
    # 한쪽이 신학/기독교/종교 계열이고 다른 한쪽이 아닌 경우 매칭 차단 (정보통신학과에 포함된 '신학과' 텍스트로 인한 오매칭 방지)
    def is_theology(s):
        has_theo = "신학" in s or "기독교" in s or "종교" in s or "선교" in s
        if "통신" in s and not ("기독교" in s or "종교" in s or "선교" in s):
            return False
        return has_theo

    if is_theology(u) != is_theology(r):
        return False

    # 2. 디자인/미디어/영상/사진/예술 전공과 순수 기술/공학(전자, 전기, 컴퓨터, IT, 기계 등) 전공의 오매칭 차단
    # 예: 요구 전공이 미디어/디자인/콘텐츠 등을 요구하는데, 사용자 전공은 관련 키워드가 없는 순수 공학인 경우 기각
    media_design_kws = {"디자인", "미디어", "콘텐츠", "사진", "영상", "멀티미디어", "예술", "시각", "애니메이션", "웹"}
    r_has_media = any(kw in r for kw in media_design_kws)
    u_has_media = any(kw in u for kw in media_design_kws)
    if r_has_media and not u_has_media:
        pure_eng_kws = {"전자", "전기", "반도체", "컴퓨터", "소프트웨어", "sw", "전산", "it", "기계", "제어계측", "신소재"}
        if any(kw in u for kw in pure_eng_kws):
            return False

    # 3. 완전 포함 관계 비교 (기본)
    if u in r or r in u:
        return True



    # 2. 전공명 접미사 제거 비교 (학과, 학부, 전공, 과 등)
    # ※ '학'은 제거 시 '신학'이 '신'이 되어 '신소재'에 오매칭되는 등의 문제가 있어 접미사에서 제외.
    def clean_suffix(s):
        suffixes = ["학과", "학부", "전공", "과"]
        changed = True
        while changed:
            changed = False
            for suff in suffixes:
                if s.endswith(suff):
                    s = s[:-len(suff)]
                    changed = True
                    break
        return s

    u_stem = clean_suffix(u)
    r_stem = clean_suffix(r)

    if u_stem and r_stem:
        if u_stem == r_stem:
            return True
        if len(u_stem) >= 2 and len(r_stem) >= 2:
            if u_stem in r_stem or r_stem in u_stem:
                # 경영 vs 경영정보 오매칭 차단
                if ("경영" in u_stem and "경영정보" in r_stem) or ("경영" in r_stem and "경영정보" in u_stem):
                    if not ("경영정보" in u_stem and "경영정보" in r_stem):
                        return False
                # 일반 행정 vs 경찰행정/소방행정 오매칭 차단
                if ("행정" in u_stem and ("경찰" in r_stem or "소방" in r_stem)) or ("행정" in r_stem and ("경찰" in u_stem or "소방" in u_stem)):
                    if not (("경찰" in u_stem or "소방" in u_stem) and ("경찰" in r_stem or "소방" in r_stem)):
                        return False
                return True

    # 3. 핵심 공통 키워드 그룹 비교 (동일 계열 전공 판정)
    groups = [
        # 전산/컴퓨터/SW/개발 계열
        {"컴퓨터", "소프트웨어", "전산", "it", "sw", "개발", "전자계산", "프로그래밍"},
        # 정보보호/보안 계열
        {"보안", "정보보호", "해킹"},
        # 정보통신/네트워크/시스템 계열
        {"정보통신", "통신", "네트워크", "시스템"},
        # 멀티미디어/웹 계열
        {"멀티미디어", "웹"},
        # 전자/전기 계열
        {"전자", "전기", "반도체", "제어계측"},
        # 기계 계열
        {"기계", "메카트로닉스", "자동차", "항공기계", "설계", "로봇"},
        # 화학/생명/신소재 계열
        {"화학", "화공", "생명", "바이오", "신소재", "재료", "금속"},
        # 토목/건축 계열
        {"토목", "건축", "도시"},
    ]
    
    for group in groups:
        has_u = any(kw in u for kw in group)
        has_r = any(kw in r for kw in group)
        if has_u and has_r:
            return True

    return False


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

    # ③-2 신장(키) 필터
    hlow, hhigh, hname = find_height_condition(conditions)
    if hlow is not None or hhigh is not None:
        uh = user.get("height")
        if uh is not None:
            if hlow is not None and uh < hlow:
                msg = f"❌ 신장 미달 (요구 {hlow}cm 이상 / 내 신장 {uh}cm)"
                reasons.append(msg)
                blockers.append(msg)
                eligible = False
            elif hhigh is not None and uh > hhigh:
                msg = f"❌ 신장 초과 (요구 {hhigh}cm 이하 / 내 신장 {uh}cm)"
                reasons.append(msg)
                blockers.append(msg)
                eligible = False
            else:
                h_range_str = f"{hlow}cm 이상" if hhigh is None else f"{hhigh}cm 이하" if hlow is None else f"{hlow} ~ {hhigh}cm"
                reasons.append(f"✅ 신장 충족 (요구 {h_range_str} / 내 신장 {uh}cm)")
        else:
            h_range_str = f"{hlow}cm 이상" if hhigh is None else f"{hhigh}cm 이하" if hlow is None else f"{hlow} ~ {hhigh}cm"
            reasons.append(f"⚠️ 신장 요구 {h_range_str} (미입력)")

    # ③-3 전문특기병 정밀 하드코딩 필터 (최신 공식 기준 적용)
    code = teukgi.get("code", "")
    
    # 훈련소조교병 (111292)
    if code == "111292":
        ug = user.get("body_grade")
        if ug and ug > 2:
            msg = f"❌ 신체등급 제한 (조교병 요구 1~2급 / 내 {ug}급)"
            reasons.append(msg)
            blockers.append(msg)
            eligible = False
        uh = user.get("height")
        if uh and uh < 170:
            msg = f"❌ 신장 미달 (조교병 요구 170cm 이상 / 내 {uh}cm)"
            reasons.append(msg)
            blockers.append(msg)
            eligible = False
        uw = user.get("weight")
        if uw and uw < 56:
            msg = f"❌ 체중 미달 (조교병 요구 56kg 이상 / 내 {uw}kg)"
            reasons.append(msg)
            blockers.append(msg)
            eligible = False
        ucv = user.get("vision_corrected")
        if ucv and ucv < 0.8:
            msg = f"❌ 시력 미달 (조교병 요구 교정시력 0.8 이상 / 내 {ucv})"
            reasons.append(msg)
            blockers.append(msg)
            eligible = False
        if user.get("has_disc_joint"):
            msg = "❌ 지원 불가 (디스크/관절 이상자 지원 불가)"
            reasons.append(msg)
            blockers.append(msg)
            eligible = False
        if user.get("has_tattoo"):
            msg = "❌ 지원 불가 (문신 보유자 지원 불가)"
            reasons.append(msg)
            blockers.append(msg)
            eligible = False
            
    # 의장병 (111284)
    elif code == "111284":
        ug = user.get("body_grade")
        if ug and ug > 3:
            msg = f"❌ 신체등급 제한 (의장병 요구 1~3급 / 내 {ug}급)"
            reasons.append(msg)
            blockers.append(msg)
            eligible = False
        uh = user.get("height")
        if uh and uh < 180:
            msg = f"❌ 신장 미달 (의장병 요구 180cm 이상 / 내 {uh}cm)"
            reasons.append(msg)
            blockers.append(msg)
            eligible = False
        uw = user.get("weight")
        if uw and (uw < 65 or uw > 90):
            msg = f"❌ 체중 제한 (의장병 요구 65~90kg / 내 {uw}kg)"
            reasons.append(msg)
            blockers.append(msg)
            eligible = False
        if user.get("has_disc_joint"):
            msg = "❌ 지원 불가 (디스크/관절 이상자 지원 불가)"
            reasons.append(msg)
            blockers.append(msg)
            eligible = False
        if user.get("has_tattoo"):
            msg = "❌ 지원 불가 (문신 보유자 지원 불가)"
            reasons.append(msg)
            blockers.append(msg)
            eligible = False

    # 특임군사경찰 (321102) / MC군사경찰 (321103)
    elif code in ("321102", "321103"):
        ug = user.get("body_grade")
        if ug and ug > 2:
            msg = f"❌ 신체등급 제한 (군사경찰 요구 1~2급 / 내 {ug}급)"
            reasons.append(msg)
            blockers.append(msg)
            eligible = False
        uh = user.get("height")
        if uh and uh < 168:
            msg = f"❌ 신장 미달 (군사경찰 요구 168cm 이상 / 내 {uh}cm)"
            reasons.append(msg)
            blockers.append(msg)
            eligible = False
        ucv = user.get("vision_corrected")
        if ucv and ucv < 0.8:
            msg = f"❌ 시력 미달 (군사경찰 요구 교정시력 0.8 이상 / 내 {ucv})"
            reasons.append(msg)
            blockers.append(msg)
            eligible = False
        if user.get("has_disc_joint"):
            msg = "❌ 지원 불가 (디스크/관절 이상자 지원 불가)"
            reasons.append(msg)
            blockers.append(msg)
            eligible = False
        if user.get("has_tattoo"):
            msg = "❌ 지원 불가 (문신 보유자 지원 불가)"
            reasons.append(msg)
            blockers.append(msg)
            eligible = False
        if user.get("has_color_blindness"):
            msg = "❌ 지원 불가 (색각 장애 보유자 지원 불가)"
            reasons.append(msg)
            blockers.append(msg)
            eligible = False

    # 특전병 (112100)
    elif code == "112100":
        ug = user.get("body_grade")
        if ug and ug > 2:
            msg = f"❌ 신체등급 제한 (특전병 요구 1~2급 / 내 {ug}급)"
            reasons.append(msg)
            blockers.append(msg)
            eligible = False
        ucv = user.get("vision_corrected")
        if ucv and ucv < 0.8:
            msg = f"❌ 시력 미달 (특전병 요구 교정시력 0.8 이상 / 내 {ucv})"
            reasons.append(msg)
            blockers.append(msg)
            eligible = False
        if user.get("has_disc_joint"):
            msg = "❌ 지원 불가 (디스크/관절 이상자 지원 불가)"
            reasons.append(msg)
            blockers.append(msg)
            eligible = False
        if user.get("has_color_blindness"):
            msg = "❌ 지원 불가 (색각 장애 보유자 지원 불가)"
            reasons.append(msg)
            blockers.append(msg)
            eligible = False

    # 지식재산관리병 (311334)
    elif code == "311334":
        user_lics = user.get("normalized_licenses") or user.get("license_inputs") or []
        has_patent_license = False
        for l in user_lics:
            if "변리사" in l.replace(" ", ""):
                has_patent_license = True
                break
        if not has_patent_license:
            msg = "❌ 지원자격 미달 (변리사 자격증 소지 또는 단독 특허 5건 이상 등록 실적 필수)"
            reasons.append(msg)
            blockers.append(msg)
            eligible = False

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
                for m in req_majors:
                    if is_major_compatible(user_m, m):
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


def get_category_rank(tk):
    """보직 카테고리별 정렬 가중치 (전문특기병(1) -> 어학병(2) -> 기술행정병(3) -> 기타(4))"""
    cat = tk.get("category", "")
    name = tk.get("name", "")
    if cat == "전문특기병":
        return 1
    elif cat == "어학병" or "어학병" in name:
        return 2
    elif "기술행정" in cat or "전문기술" in cat or "일반기술" in cat:
        return 3
    else:
        return 4


def filter_eligible_teukgi(teukgi_master, user, include_unknown=True):
    """
    전체 특기 중 사용자가 지원 가능한 것만 필터링.
    우선순위: 2(직접 매칭) > 1(부분 매칭) > 0(제한 없음)
    그 안에서 카테고리 랭크: 전문특기병 > 어학병 > 기술행정병 > 기타 순
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

    # 정렬: 블로커 없는 것 우선, 그 안에서 priority 높은 것 우선, 카테고리 랭크 우선, 동순위는 이름순
    results.sort(key=lambda x: (
        len(x[1]["blockers"]),          # 블로커 없는 것 우선 (오름차순)
        -x[1].get("priority", 0),       # priority 높은 것 우선 (내림차순)
        get_category_rank(x[0]),        # 카테고리 랭크 (오름차순: 1->2->3->4)
        x[0]["name"],                   # 이름 가나다순
    ))
    return results
