"""
E-Book OCR Learned Corrections Engine & Knowledge Base Manager
스캔본 OCR 오탈자를 학습 데이터(data/learned_corrections.json) 기반으로
우선 교정하고, 지속적으로 새로운 교정 지식을 저장/확장하는 모듈
"""

import os
import json
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KB_PATH = os.path.join(BASE_DIR, "data", "learned_corrections.json")

def load_learned_kb():
    if not os.path.exists(KB_PATH):
        return {}
    try:
        with open(KB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[KB Warning] Failed to load {KB_PATH}: {e}")
        return {}

def save_learned_kb(kb_data):
    os.makedirs(os.path.dirname(KB_PATH), exist_ok=True)
    temp_path = KB_PATH + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(kb_data, f, ensure_ascii=False, indent=2)
    if os.path.exists(KB_PATH):
        os.remove(KB_PATH)
    os.rename(temp_path, KB_PATH)

def add_learned_pair(wrong: str, correct: str, category: str = "기타"):
    kb = load_learned_kb()
    terms = kb.setdefault("terms", {})
    cat_dict = terms.setdefault(category, {})
    cat_dict[wrong] = correct
    save_learned_kb(kb)

# Precompile regex rules for deep cleaning
COMPILED_PATTERNS = [
    # 1. 파인튜닝 모든 OCR 왜곡 일괄 치환
    (re.compile(r"파인[튜특류뉴듯][님낭빌딩넣]|파인튜-(?=\s*\(Fine-tuning\))"), "파인튜닝"),
    (re.compile(r"파인튜닝이[관과]"), "파인튜닝이란"),
    
    # 2. 어미 왜곡: [가-힣]*[임습합]나다 -> \1[임습합]니다
    (re.compile(r"([가-힣]*)([임습합])나다"), r"\1\2니다"),
    
    # 3. 튜링 인명 및 테스트 복원
    (re.compile(r"[탤엘알][런럴]\s*[튜특][껑립굉령링]"), "앨런 튜링"),
    (re.compile(r"[튜특][껑립굉령링]\s*테스트"), "튜링 테스트"),
    (re.compile(r"[튜특][껑립굉령](?=[은는이가을를에게의와과도])"), "튜링"),
    
    # 4. 퍼셉트론 / 로젠블랫
    (re.compile(r"로[젠전제]불?렉"), "로젠블랫"),
    (re.compile(r"퍼센트론"), "퍼셉트론"),
    
    # 5. 인프라 / 어텐션
    (re.compile(r"런[되맛핏]"), "런팟"),
    (re.compile(r"플[렉랍]\s*품"), "플랫폼"),
    (re.compile(r"어[텐렌린]선"), "어텐션"),
    (re.compile(r"소포트맥스"), "소프트맥스"),
    (re.compile(r"모\s*텔"), "모델"),
    (re.compile(r"첫지피티"), "챗지피티"),
    (re.compile(r"프로적트"), "프로젝트"),
    (re.compile(r"알고리증"), "알고리즘"),
    (re.compile(r"컴퓨텅"), "컴퓨팅"),
    (re.compile(r"맥각(?=[에의을를은는서])"), "맥락"),
    
    # 6. 불완전 음절 / 조사
    (re.compile(r"([가-힣]+)올(?=\s|$|[,\.\?!])"), r"\1을"),
    (re.compile(r"([가-힣]+)으미(?=\s|$|[,\.\?!])"), r"\1으며"),
    (re.compile(r"([가-힣]+)켓([가-힣]+)"), r"\1겠\2"),
    (re.compile(r"([가-힣]+)햇([가-힣]+)"), r"\1했\2"),
    (re.compile(r"앞게(?=\s*볼|\s*있|\s*됩|\s*다루|\s*만들)"), "있게"),
    (re.compile(r"앞는(?=\s*가|\s*지)"), "왔는"),
    (re.compile(r"보젯습니다"), "보겠습니다"),
    (re.compile(r"신회할"), "신뢰할"),
    (re.compile(r"덥니다"), "됩니다"),
    (re.compile(r"뒷습니다"), "됐습니다"),
    (re.compile(r"워습니다"), "였습니다"),
    (re.compile(r"눈문"), "논문"),
    (re.compile(r"눈매(?=\s*을|\s*를|\s*의|\s*에)"), "문맥"),
    (re.compile(r"임젯"), "임계값"),
    (re.compile(r"데이터젯"), "데이터셋"),
    (re.compile(r"자원의\s*저주"), "차원의 저주"),
    (re.compile(r"자원\s*축소"), "차원 축소"),
]

def apply_learned_knowledge(text: str) -> str:
    """학습 데이터베이스 및 정밀 규칙을 순차 적용하여 텍스트 정밀 교정"""
    if not text:
        return text
    
    # 1. Regex 패턴 적용
    t = text
    for pat, repl in COMPILED_PATTERNS:
        t = pat.sub(repl, t)
        
    # 2. Key-Value 딕셔너리 정밀 치환
    kb = load_learned_kb()
    terms = kb.get("terms", {})
    for cat_name, pair_dict in terms.items():
        for wrong, correct in pair_dict.items():
            if wrong in t:
                t = t.replace(wrong, correct)
                
    # 3. 띄어쓰기 및 구두점 정리
    t = re.sub(r"\s+([.,!?;:])", r"\1", t)
    t = re.sub(r"([(\[{<])\s+", r"\1", t)
    t = re.sub(r"\s+([)\]}>])", r"\1", t)
    t = re.sub(r"[ \t]+", " ", t)
    return t.strip()
