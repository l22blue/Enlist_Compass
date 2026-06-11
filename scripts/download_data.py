"""
공공 API를 통해 병무청 모집병 정보를 다운로드하고 정제하여 로컬 JSON 데이터베이스로 저장하는 스크립트
"""
import os
import sys
import json

# 프로젝트 루트 경로를 sys.path에 추가 (api 모듈 로딩용)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api import mma_api

def download_and_save(service_key, output_path):
    """
    병무청 API에서 전체 데이터를 받아 병합하고 지정된 JSON 경로에 저장합니다.
    """
    print("1. 병무청 군사특기마스타 정보를 조회 중...")
    # 캐시를 사용하지 않고 새로 고치기 위해, mma_api의 st.cache_data를 우회하지는 못하지만 
    # CLI 단독 스크립트 실행 환경이므로 Streamlit 캐싱 영향 없이 바로 조회됩니다.
    teukgi_master = mma_api.get_teukgi_master(service_key)
    if not teukgi_master:
        print("에러: 군사특기마스타 정보를 수집하지 못했습니다.")
        return False

    print("2. 병무청 모집병 지원가능 분야 정보를 조회 중...")
    jiwon_info = mma_api.get_jiwon_info(service_key)

    print("3. 데이터 병합 중...")
    for code, tk in teukgi_master.items():
        tk["licenses"] = jiwon_info.get(code, {}).get("licenses", [])
        tk["majors"] = jiwon_info.get(code, {}).get("majors", [])

    # 출력 폴더 생성
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # JSON 저장
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(teukgi_master, f, ensure_ascii=False, indent=2)

    print(f"성공: 총 {len(teukgi_master)}개의 군사 특기 정보가 '{output_path}'에 저장되었습니다.")
    return True

if __name__ == "__main__":
    # 1. 인자로 키를 넘겼는지 확인
    key = ""
    if len(sys.argv) > 1:
        key = sys.argv[1].strip()

    # 2. 인자가 없다면 secrets.toml 로드 시도
    if not key:
        try:
            import toml
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            secrets_path = os.path.join(project_root, ".streamlit", "secrets.toml")
            if os.path.exists(secrets_path):
                secrets = toml.load(secrets_path)
                key = secrets.get("MMA_API_KEY", "").strip()
        except Exception as e:
            print(f"경고: secrets.toml을 로드하는 중 에러 발생: {e}")

    if not key or "여기에" in key:
        print("에러: 유효한 병무청 API 키를 찾을 수 없습니다. secrets.toml 파일이나 인자를 확인하세요.")
        sys.exit(1)

    # 기본 출력 경로 설정 (project_root/data/military_specialties.json)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_out = os.path.join(project_root, "data", "military_specialties.json")

    success = download_and_save(key, default_out)
    if not success:
        sys.exit(1)
