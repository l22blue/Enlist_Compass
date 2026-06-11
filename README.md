# 🧭 입대 나침반 (EnlistCompass)

> 끌려가지 말고, 목표를 세우고 입대하자.

내 신체등급·시력·학과·자격증 조건으로 **지금 지원 가능한 군 보직**을 찾아주는 서비스.
합격 예측이나 점수 계산은 하지 않습니다 — 오직 "지금 내가 지원할 자격이 되는가"만 보여줍니다.

## 왜 만들었나
병무청 웹에서 보직을 직접 찾는 건 번거롭습니다. 조건만 입력하면
지원 가능한 보직이 한눈에 보이도록 만들었습니다.

## 설치
```bash
pip install -r requirements.txt
```

## 키 설정 (Streamlit secrets 권장)
`.streamlit/secrets.toml.example` 을 `secrets.toml` 로 복사 후 키 입력:
```toml
MMA_API_KEY = "병무청_공공데이터포털_키"
SOLAR_API_KEY = "Upstage_Solar_키"
```
secrets에 키가 있으면 자동 로드되고, 없으면 사이드바 입력창이 뜹니다.

## 실행 순서

### 1단계: API 응답 구조 먼저 확인 ⭐
키 발급 후 반드시 먼저 실행해 실제 데이터 구조를 확인하세요.
```bash
# explore_api.py 의 SERVICE_KEY 에 키 입력 후
python explore_api.py
```
출력 중 **gjhangmokNm(기준항목명) 종류**를 꼭 확인하세요.
시력이 "시력"인지 "교정시력"인지, 나안/교정 구분되는지에 따라
`utils/matching.py` 의 키워드를 보정합니다.

### 2단계: 앱 실행
```bash
streamlit run app.py
```

## 구조
```
app.py                 # 메인 앱 (입력폼/결과/비교)
explore_api.py         # ① 먼저 돌릴 진단 스크립트
api/
  mma_api.py           # 병무청 API 호출
  solar_api.py         # Solar 학과/자격증 정규화
utils/
  matching.py          # 자격 게이트 필터링 로직
.streamlit/
  secrets.toml.example # 키 템플릿
```

## 쓰는 API
- 군사특기마스타 (gsTgMastr) — 특기 목록 + 신체조건 + 모집일정
- 모집병 군별 특기별 지원가능 정보 (mjbJiWon) — 자격/전공 매칭

## ⚠️ 실제 데이터 보고 보정할 부분
1. mjbJiWon 의 자격/전공 필드명 — api/mma_api.py 의 get_jiwon_info
2. 시력/신체등급 항목명 — utils/matching.py
3. 모집 기간 외엔 데이터가 비어있을 수 있음
