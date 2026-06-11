"""
1단계: API 응답 구조 진단 스크립트
키 발급 후 가장 먼저 이걸 돌려서 실제 데이터가 어떻게 오는지 확인하세요.
특히 gjhangmokNm(기준항목명)에 시력/신체등급이 어떤 텍스트로 오는지 봐야 합니다.
"""
import requests
import xml.etree.ElementTree as ET
from collections import Counter
import sys

# 출력을 utf-8 파일로 직접 저장하도록 리다이렉션
sys.stdout = open("explore_result.txt", "w", encoding="utf-8")

# ──────────────────────────────────────────────
# 공공데이터포털에서 발급받은 키를 여기에 붙여넣으세요 (Decoding 키 권장)
SERVICE_KEY = "db820f4dfed47f436073bf16ed4cfdb84c224a9fc7bad39eeb7f197295e28a28"
# ──────────────────────────────────────────────

GSTG_URL = "http://apis.data.go.kr/1300000/gsTgMastr/list/gsTgMastr/list"
JIWON_URL = "http://apis.data.go.kr/1300000/mjbJiWon/list"


def fetch(url, rows=100, page=1):
    """API 호출 후 XML 파싱해서 item 리스트 반환"""
    params = {
        "serviceKey": SERVICE_KEY,
        "numOfRows": rows,
        "pageNo": page,
    }
    res = requests.get(url, params=params, timeout=10)
    res.encoding = "utf-8"
    print(f"  HTTP {res.status_code} | URL: {res.url[:80]}...")

    root = ET.fromstring(res.text)

    # 에러 체크
    result_code = root.findtext(".//resultCode")
    result_msg = root.findtext(".//resultMsg")
    print(f"  resultCode={result_code}, resultMsg={result_msg}")

    items = []
    for item in root.iter("item"):
        d = {child.tag: (child.text or "").strip() for child in item}
        items.append(d)
    return items


def explore_gstg():
    print("\n" + "=" * 60)
    print("① 군사특기마스타 (gsTgMastr) 구조 확인")
    print("=" * 60)
    items = fetch(GSTG_URL, rows=200)
    print(f"\n총 {len(items)}건 수신")

    if not items:
        print("⚠️ 데이터 없음 - 모집 기간이 아니거나 키 문제일 수 있음")
        return

    # 첫 행 전체 필드 출력
    print("\n[첫 번째 항목 전체 필드]")
    for k, v in items[0].items():
        print(f"  {k}: {v}")

    # ★핵심: 기준항목명(gjhangmokNm)에 어떤 값들이 오는지
    print("\n[★ gjhangmokNm(기준항목명) 종류 - 여기서 시력/신체등급 텍스트 확인]")
    hangmok = Counter(it.get("gjhangmokNm", "") for it in items)
    for name, cnt in hangmok.most_common():
        print(f"  '{name}': {cnt}건")

    # 군종 분포
    print("\n[군구분명 분포]")
    guns = Counter(it.get("gunGbnm", "") for it in items)
    for g, c in guns.most_common():
        print(f"  {g}: {c}건")

    # 특기 종류
    print("\n[군사특기명 샘플 (최대 20개)]")
    teukgis = sorted(set(it.get("gsteukgiNm", "") for it in items))
    for t in teukgis[:20]:
        print(f"  - {t}")

    return items


def explore_jiwon():
    print("\n" + "=" * 60)
    print("② 지원가능 정보 (mjbJiWon) 구조 확인")
    print("=" * 60)
    items = fetch(JIWON_URL, rows=100)
    print(f"\n총 {len(items)}건 수신")

    if not items:
        print("⚠️ 데이터 없음")
        return

    print("\n[첫 번째 항목 전체 필드]")
    for k, v in items[0].items():
        print(f"  {k}: {v}")

    return items


if __name__ == "__main__":
    if SERVICE_KEY.startswith("여기에"):
        print("⚠️ 먼저 SERVICE_KEY에 발급받은 API 키를 입력하세요!")
    else:
        explore_gstg()
        explore_jiwon()
        print("\n✅ 진단 완료. 위 결과(특히 gjhangmokNm 종류)를 보고 매칭 로직을 확정합니다.")
