"""
112 서버 (Gemma 4 E4B) 연동 고속 페이지 배치 OCR 텍스트 교정기
- 페이지 단위 배치(Batch) 요청으로 13,000회 개별 호출을 300회 이하로 축소 (10~20배 고속화)
- 태그 기반 매핑 ([P1], [P2])을 통한 문단별 1:1 정밀 복원
- 영구 디스크 캐싱 (cache/llm_cache_*.json)을 통한 재변환 시 0.01초 즉시 로딩
"""

import os
import json
import urllib.request
import urllib.error
import re
import hashlib
import time

DEFAULT_LLM_URL = "http://127.0.0.1:8092/v1/chat/completions"
DEFAULT_MODEL = "edumaster-gemma-4-12b-vision"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

PROMPT_SYSTEM = """당신은 AI/컴퓨터공학 기술 서적 전문 교정 AI입니다.
스캔본 OCR 과정에서 발생한 한글/영문 오탈자, 오인식 조사, 오인식 단어, 어색한 띄어쓰기를 문맥에 맞게 정확히 교정합니다.

[교정 규칙]
1. 문단 태그([P1], [P2] 등)를 원본과 동일하게 반드시 유지하십시오.
2. 인공지능/소프트웨어 문맥 및 인명/기술용어를 최우선 반영합니다.
   - 탤런 튜껑 / 튜립 / 튜굉 -> 앨런 튜링 / 튜링
   - 특껑 / 특령 / 특립 테스트 -> 튜링 테스트
   - 로젠블렉 / 로젠불렉 -> 로젠블랫
   - 퍼센트론 -> 퍼셉트론
   - 모텔 -> 모델
   - 파인류님 / 파인특님 -> 파인튜닝
   - 런되(runpod) / 런파 -> 런팟(RunPod)
   - 플렉품 / 플랍품 -> 플랫폼
   - 콜라우드 -> 클라우드
   - 저리 / 전저리 -> 처리 / 전처리
   - 가중지 -> 가중치
   - 임겟값 -> 임계값
   - 자원 축소 / 자원의 저주 -> 차원 축소 / 차원의 저주
   - 서방 -> 서빙
   - 어텐선 / 어렌선 -> 어텐션
   - 소프트맥스 / 소포트맥스 -> 소프트맥스
3. 인사말, 부연설명 없이 오직 번호 태그와 교정된 본문만 출력합니다."""

def get_llm_cache_path(pdf_path):
    stat = os.stat(pdf_path)
    key = hashlib.md5(f"llm_{pdf_path}_{stat.st_size}_{stat.st_mtime}".encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"llm_cache_{key}.json")

def load_llm_cache(cache_path):
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_llm_cache(cache_path, cache_dict):
    try:
        temp_path = cache_path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(cache_dict, f, ensure_ascii=False)
        if os.path.exists(cache_path):
            os.remove(cache_path)
        os.rename(temp_path, cache_path)
    except Exception as e:
        print(f"Failed to save LLM cache: {e}")

def check_112_server(base_url="http://127.0.0.1:8092"):
    """로컬 LLM (127.0.0.1:8092) 우선 확인 후 실패 시 112 서버 확인"""
    for url_target in [base_url, "http://192.168.219.112:8081"]:
        try:
            url = f"{url_target}/v1/models"
            req = urllib.request.Request(url, headers={"User-Agent": "EbookStudio"})
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                models = [m.get("id") or m.get("name") for m in data.get("data", []) or data.get("models", [])]
                return True, (models, url_target)
        except Exception:
            continue
    return False, "로컬 (127.0.0.1:8092) 및 112 서버 모두 연결할 수 없습니다."

ANOMALY_PATTERN = re.compile(
    r'(?:[탤엘알][런럴]\s*[튜특][껑립굉령링]'
    r'|[튜특][껑립굉령]'
    r'|[가-힣]+[올블눈켓랫솄젯논]'
    r'|[가-힣]+[임습합]나다'
    r'|[가-힣]+있있'
    r'|파인[튜특류뉴듯][님낭빌딩넣]'
    r'|파인튜-'
    r'|\b(?:모텔|가중지|전저리|임겟값|자이점|자원의\s*저주|자원\s*축소|어텐선|희신|담변|평기가|의건|바람니다|다툼니다|만돈|작동쾌|뒷습|뵙니|되니|워습|있엎|미처고|눈문|눈매|있율|학신|제기하|제기워|일으켜|덥니|넓질|인용펼|담구|곁정|출억|제안겠|빛습|주장쾌|암는|알려저|맛추|밭있|않앉|제기행|중요해적|대화지|생각활|앞는지|제시하|맥각|국하|숙련원|거쟁|맞취|대처활|학습시청|얻어든|메거니증|퍼센트론|활수|수행활|해결활|컴퓨텅|알고리증|로젠블|플렉품|런되|년리님|자원율|맛충|파인특|파인류|보젯|첫지피티|신회할)\b'
    r'|\b[가-힣]{2,4}[0-9]'
    r'|\b[가-힣]\s+[가-힣]\s+[가-힣]\b'
    r')'
)

def has_ocr_anomaly(text: str) -> bool:
    return bool(ANOMALY_PATTERN.search(text))

def get_text_hash(text: str) -> str:
    cleaned = re.sub(r'\s+', '', text)
    return hashlib.md5(cleaned.encode('utf-8')).hexdigest()[:16]

def correct_page_body_elements(page_idx, page_elements, llm_cache=None, api_url=DEFAULT_LLM_URL, model_name=DEFAULT_MODEL, timeout=35, log_fn=None):
    """
    한 페이지 내의 오탈자 의심 BODY 및 TITLE 텍스트를 선별하여 단 1회의 LLM 호출로 초고속 교정합니다.
    - 절대 IMAGE, CODE 요소는 덮어쓰지 않습니다.
    - 유효한 캐시가 존재하면 즉시 반환
    """
    p_key = str(page_idx)

    # 1. 캐시 확인 (오직 BODY 및 TITLE 문단에 안전하게 적용)
    if llm_cache is not None and p_key in llm_cache:
        cached_dict = llm_cache[p_key]
        if isinstance(cached_dict, dict) and any(len(k) == 16 for k in cached_dict.keys()):
            # 1-A. Hash-based matching
            hash_map = {get_text_hash(el["text"]): el for el in page_elements if el["type"] in ("BODY", "TITLE")}
            applied = 0
            for k, c_text in cached_dict.items():
                if k in hash_map:
                    hash_map[k]["text"] = c_text
                    applied += 1
            if applied > 0:
                return page_elements

    # 2. 지식 베이스(Ground-Truth Knowledge Base) 1차 적용
    from knowledge_corrector import apply_learned_knowledge
    for el in page_elements:
        if el["type"] in ("BODY", "TITLE"):
            el["text"] = apply_learned_knowledge(el["text"])

    # 3. 잔여 오탈자/노이즈 BODY / TITLE 문단 선별 (LLM 검수 대상)
    body_items = []
    for idx, el in enumerate(page_elements):
        if el["type"] in ("BODY", "TITLE"):
            t = el["text"].strip()
            if len(t) >= 6 and has_ocr_anomaly(t):
                body_items.append((idx, t))

    if not body_items:
        return page_elements

    # 3. 배치 프롬프트 생성 ([P1], [P2] ...)
    prompt_lines = []
    for tag_num, (_, text) in enumerate(body_items, start=1):
        prompt_lines.append(f"[P{tag_num}] {text}")

    prompt_body = "\n\n".join(prompt_lines)

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": PROMPT_SYSTEM},
            {"role": "user", "content": prompt_body}
        ],
        "temperature": 0.1,
        "max_tokens": max(500, int(len(prompt_body) * 1.5))
    }

    t0 = time.time()
    if log_fn:
        log_fn(f"  [LLM 검수] {page_idx}p: 의심 문단 {len(body_items)}개 로컬 Gemma 12B 정밀 교정 중...")

    try:
        data_bytes = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(
            api_url,
            data=data_bytes,
            headers={"Content-Type": "application/json; charset=utf-8"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            res_json = json.loads(resp.read().decode('utf-8'))
            reply = res_json["choices"][0]["message"]["content"].strip()

            # [P1], [P2] 등 태그 파싱
            matches = re.findall(r'\[P(\d+)\]\s*(.*?)(?=(?:\[P\d+\]|\Z))', reply, re.DOTALL)
            corrected_dict = {}
            for num_str, content in matches:
                try:
                    p_num = int(num_str)
                    cleaned = content.strip()
                    if cleaned and len(cleaned) > 5:
                        corrected_dict[p_num] = cleaned
                except ValueError:
                    pass

            # 매핑 및 캐시 준비
            saved_for_cache = {}
            tag_counter = 1
            changed_count = 0
            for el_idx, orig_text in body_items:
                h_key = get_text_hash(orig_text)
                if tag_counter in corrected_dict:
                    new_text = corrected_dict[tag_counter]
                    page_elements[el_idx]["text"] = new_text
                    saved_for_cache[h_key] = new_text
                    if new_text != orig_text:
                        changed_count += 1
                        if log_fn:
                            # Print diff snippet
                            log_fn(f"    └ [교정] \"{orig_text[:30]}...\" -> \"{new_text[:30]}...\"")
                else:
                    saved_for_cache[h_key] = orig_text
                tag_counter += 1

            elapsed = time.time() - t0
            if log_fn:
                log_fn(f"  [LLM 완료] {page_idx}p: {len(body_items)}개 중 {changed_count}개 문단 교정 완료 ({elapsed:.1f}초)")

            if llm_cache is not None:
                llm_cache[p_key] = saved_for_cache

    except Exception as e:
        # 통신 실패 시 원본 그대로 유지
        if log_fn:
            log_fn(f"  [LLM 실패] {page_idx}p 통신 오류 (원본 유지): {e}")
        print(f"[LLM Warning] Page {page_idx} LLM correction fallback: {e}")

    return page_elements

def correct_text_with_llm(text: str, api_url=DEFAULT_LLM_URL, model_name=DEFAULT_MODEL, timeout=20):
    """단일 문단 하위 호환용 함수"""
    t_clean = text.strip()
    if len(t_clean) < 10 or t_clean.startswith("```") or t_clean.startswith("!["):
        return text

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": PROMPT_SYSTEM},
            {"role": "user", "content": text}
        ],
        "temperature": 0.1,
        "max_tokens": max(500, len(text) * 2)
    }

    try:
        data_bytes = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(api_url, data=data_bytes, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            res_json = json.loads(resp.read().decode('utf-8'))
            reply = res_json["choices"][0]["message"]["content"].strip()
            if reply.startswith(('"', "'", '`')) and reply.endswith(('"', "'", '`')):
                reply = reply[1:-1].strip()
            return reply
    except Exception:
        return text

if __name__ == "__main__":
    ok, models = check_112_server()
    print("Server alive:", ok, "Models:", models)
