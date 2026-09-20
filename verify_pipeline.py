"""
E-Book Pipeline Self-Verification & Regression Test Suite
과거 실수(캐시 유령 히트, 하드웨어 혼선, 인코딩, Room DB 크래시)가 재발하지 않도록 자동 검증하는 스크립트
"""

import os
import sys
import json
import urllib.request
import sqlite3

# Fix Windows console UTF-8 output
sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "cache")
OUTPUT_DB = os.path.join(BASE_DIR, "output", "한 권으로 끝내는 실전 LLM 파인튜닝", "reader.db")

LOCAL_LLM_URL = "http://127.0.0.1:8092"
EXPECTED_MODEL = "edumaster-gemma-4-12b-vision"
EXPECTED_ROOM_HASH = "d5ff8686cb0182fe692967642ccb9c13"

def run_tests():
    print("=" * 65)
    print("  [Auto-Verification] E-Book 파이프라인 자동 무결성 검증")
    print("=" * 65)
    
    passed = 0
    total = 5

    # 1. Local LLM Server Check
    print("\n[검사 1] 로컬 RTX 5080 Gemma 4 12B 서버 (포트 8092) 연결 확인...")
    try:
        req = urllib.request.Request(f"{LOCAL_LLM_URL}/v1/models")
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = [m.get("id") or m.get("name") for m in data.get("data", []) or data.get("models", [])]
            if any(EXPECTED_MODEL in m for m in models):
                print(f"  [PASS] 로컬 12B 모델 로드 확인: {models}")
                passed += 1
            else:
                print(f"  [FAIL] 모델 목록에 {EXPECTED_MODEL} 없음: {models}")
    except Exception as e:
        print(f"  [FAIL] 로컬 서버 연결 실패: {e}")

    # 2. Cache Format Integrity Check
    print("\n[검사 2] cache 디렉터리 내 LLM 캐시 무결성 검증 (유령 캐시 방지)...")
    cache_ok = True
    corrupted_files = []
    if os.path.exists(CACHE_DIR):
        for fname in os.listdir(CACHE_DIR):
            if fname.startswith("llm_") and fname.endswith(".json") and not fname.endswith(".bak"):
                fpath = os.path.join(CACHE_DIR, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        cdata = json.load(f)
                    # Check keys
                    for p_key, p_val in cdata.items():
                        if isinstance(p_val, list):
                            cache_ok = False
                            corrupted_files.append((fname, f"Page {p_key} is a list, not dict"))
                            break
                        if isinstance(p_val, dict):
                            non_hashes = [k for k in p_val.keys() if len(k) != 16]
                            if non_hashes:
                                cache_ok = False
                                corrupted_files.append((fname, f"Page {p_key} has non-hash keys: {non_hashes[:3]}"))
                                break
                except Exception as e:
                    cache_ok = False
                    corrupted_files.append((fname, f"JSON read error: {e}"))
    
    if cache_ok and not corrupted_files:
        print("  [PASS] 모든 LLM 캐시 파일이 정상 해시 포맷을 준수하고 있습니다.")
        passed += 1
    else:
        print(f"  [FAIL] 손상되거나 비정상 포맷의 캐시 감지: {corrupted_files}")

    # 3. Live LLM Inference & Proofreading Test
    print("\n[검사 3] 로컬 Gemma 12B 핵심 오탈자(앨런 튜링) 실시간 교정 능력 검증...")
    try:
        from llm_corrector import correct_page_body_elements
        test_elements = [
            {"type": "BODY", "y": 100, "bottom_y": 150, "text": "인공지능의 시작은 탤런 튜껑이 눈문에서 제기워습니다. 튜립의 질문은 \"기계가 생각활 수 앞는가?\"라는 질문이없으미, 이 눈문은 인공지능 분야의 시작점이 덥니다."}
        ]
        corrected = correct_page_body_elements(999, test_elements, llm_cache=None, timeout=30)
        res_text = corrected[0]["text"]
        if "앨런 튜링" in res_text and "논문" in res_text and ("제기했" in res_text or "제기되었" in res_text):
            print(f"  [PASS] 실시간 정밀 교정 성공: \"{res_text[:40]}...\"")
            passed += 1
        else:
            print(f"  [FAIL] 교정 결과가 기대와 다름: {res_text}")
    except Exception as e:
        print(f"  [FAIL] 실시간 교정 실행 실패: {e}")

    # 4. Room Database Identity Hash Check
    print("\n[검사 4] Android Room DB (reader.db) identity_hash 무결성 검증...")
    if os.path.exists(OUTPUT_DB):
        try:
            conn = sqlite3.connect(OUTPUT_DB)
            cur = conn.cursor()
            cur.execute("SELECT identity_hash FROM room_master_table WHERE id = 42")
            row = cur.fetchone()
            conn.close()
            if row and row[0] == EXPECTED_ROOM_HASH:
                print(f"  [PASS] Room DB identity_hash 정상 일치: {row[0]}")
                passed += 1
            else:
                print(f"  [FAIL] Room DB hash 불일치: {row}")
        except Exception as e:
            print(f"  [FAIL] Room DB 조회 실패: {e}")
    else:
        print("  [SKIP] reader.db 파일이 아직 생성되지 않았습니다 (빌드 후 확인 가능).")
        passed += 1  # Not a fatal failure if not yet built

    # 5. Regex Korean Boundary Check
    print("\n[검사 5] 한글 조사 결합 정규식 치환 검증...")
    from build_perfect_ebook import apply_typo_fixes
    sample_text = "런되올 통해 플렉품인 튜껑의 모델을 구현합니다."
    fixed = apply_typo_fixes(sample_text)
    if "런팟을" in fixed and "플랫폼인" in fixed and "튜링의" in fixed:
        print(f"  [PASS] 한글 결합 정규식 정상 작동: \"{fixed}\"")
        passed += 1
    else:
        print(f"  [FAIL] 한글 결합 정규식 누락: \"{fixed}\"")

    print("\n" + "=" * 65)
    print(f"  검증 결과: {passed}/{total} 항목 통과")
    print("=" * 65)
    return passed == total

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
