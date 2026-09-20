"""
E-Book OCR Learned Corrections Engine & Knowledge Base Manager
스캔본 OCR 오탈자를 학습 데이터(data/learned_corrections.json) 및
체계적 정규식 규칙 기반으로 우선 교정하고, 지속적으로 새로운 교정 지식을 저장/확장하는 모듈
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

# Precompile comprehensive regex rules for deep cleaning
COMPILED_PATTERNS = [
    # 1. 파인튜닝 왜곡 일괄 (파인5님, 파인5낭, 파인특, 파인류, 파인듯낭 등)
    (re.compile(r"파인[0-9가-힣]*[님낭딩빌넣]"), "파인튜닝"),
    (re.compile(r"파인튜-(?=\s*\(Fine-tuning\))"), "파인튜닝"),
    (re.compile(r"파인튜닝이[관과]"), "파인튜닝이란"),
    (re.compile(r"파인튜닝중"), "파인튜닝 중"),
    (re.compile(r"파인튜닝을\s*하늘\s*이유"), "파인튜닝을 하는 이유"),
    (re.compile(r"하늘\s*이유"), "하는 이유"),
    (re.compile(r"파라미터\s*특[님늬냥녕]"), "파라미터 튜닝"),
    (re.compile(r"특[님늬냥녕](?=\s*(?:기법|방식|을|를|이|가|은|는|의|에|으로|과|와))"), "튜닝"),
    (re.compile(r"\bPET\b(?=\s*(?:기법|\)))"), "PEFT"),
    
    # 2. 하드웨어/정밀도/자료형 왜곡
    (re.compile(r"BFI6|BFtG"), "BF16"),
    (re.compile(r"bfloatt6"), "bfloat16"),
    (re.compile(r"F[PI]I?6|F머16"), "FP16"),
    (re.compile(r"FP6\)"), "FP16)"),
    (re.compile(r"BFP16"), "BF16"),
    (re.compile(r"16비I트"), "16비트"),
    (re.compile(r"32비I트"), "32비트"),
    (re.compile(r"부동소수제은"), "부동소수점은"),
    (re.compile(r"부동소수제(?=[이가을를의에과와])"), "부동소수점"),
    (re.compile(r"부동소수점와"), "부동소수점과"),
    (re.compile(r"정말도(?=\s*(?:는|가|를|의|로|보다|틀))"), "정밀도"),
    (re.compile(r"\b낯습니다\b"), "낮습니다"),
    (re.compile(r"메모리\s*사용랑"), "메모리 사용량"),
    (re.compile(r"\b사용랑\b"), "사용량"),
    (re.compile(r"호\s*울성"), "효율성"),
    
    # 3. 텐서/벡터/디렉터리
    (re.compile(r"\b렌서"), "텐서"),
    (re.compile(r"\b넥터"), "벡터"),
    (re.compile(r"\b디넥터리"), "디렉터리"),
    
    # 4. 옵티마이저/옵션
    (re.compile(r"올티마이저"), "옵티마이저"),
    (re.compile(r"\b올선(?=[과와을를은는이가])"), "옵션"),
    
    # 5. 메커니즘/출력/알고리즘/컴퓨팅/프로젝트
    (re.compile(r"메거니[증롬좀름]"), "메커니즘"),
    (re.compile(r"메거니\s*Value"), "메커니즘(Value"),
    (re.compile(r"출억"), "출력"),
    (re.compile(r"알고리[으증]"), "알고리즘"),
    (re.compile(r"컴퓨텅"), "컴퓨팅"),
    (re.compile(r"프로적트"), "프로젝트"),
    
    # 6. 확률/학습률/손실률/다룰
    (re.compile(r"확물(?=[적인으로을를이가은는의과와도]|\b)"), "확률"),
    (re.compile(r"학습물(?=[으로을를이가은는의과와도까지]|\b)"), "학습률"),
    (re.compile(r"손실물(?=[으로을를이가은는의과와도]|\b)"), "손실률"),
    (re.compile(r"\b다[물률]\b"), "다룰"),
    (re.compile(r"다물\s*내용"), "다룰 내용"),
    
    # 7. 조사 틀 -> 를 (예: 이틀 통해 -> 이를 통해, 텍스트틀 -> 텍스트를)
    (re.compile(r"\b이틀(?=\s+통해)"), "이를"),
    (re.compile(r"\b예틀(?=\s+들어)"), "예를"),
    (re.compile(r"FP32틀"), "FP32를"),
    (re.compile(r"([A-Za-z0-9]+)틀(?=\s|$|[,\.\?!])"), r"\1를"),
    (re.compile(r"(?<!기)(?<!\b)([가-힣]{2,})틀(?=\s|$|[,\.\?!])"), r"\1를"),
    
    # 8. 조사 루 -> 를 / 로
    (re.compile(r"(결과|효과|평가|역전파|성과|메시지|최적화|활성화|병렬화|이해|조직화)루(?=\s|$|[,\.\?!])"), r"\1를"),
    (re.compile(r"(숫자|글자|문자|가중치|기중치|위치|절차)루(?=\s|$|[,\.\?!])"), r"\1로"),
    (re.compile(r"기중치루"), "가중치로"),
    
    # 9. 조사 올 -> 을
    (re.compile(r"([A-Za-z0-9]+)올(?=\s|$|[,\.\?!])"), r"\1을"),
    (re.compile(r"([가-힣]{2,})올(?=\s|$|[,\.\?!])"), r"\1을"),
    (re.compile(r"([A-Za-z0-9가-힣]+)\s+올(?=\s|$|[,\.\?!])"), r"\1을"),
    (re.compile(r"\b데이터지\s*저장"), "데이터를 저장"),
    
    # 10. 조사 눈 -> 은 / 는
    (re.compile(r"([가-힣]{2,})논데"), r"\1는데"),
    (re.compile(r"([가-힣]{2,})논(?=\s)"), r"\1는"),
    (re.compile(r"([가-힣]{2,})눈(?=\s+[가-힣]+(?:은|는|이|가|을|를|의|에|로|와|과|도))"), r"\1는"),
    (re.compile(r"([A-Za-z0-9_\]\)]+)눈(?=\s)"), r"\1은"),
    
    # 11. 동사/형용사 어미 왜곡 (중니다, 움니다, 흉니다, 럽니다, 입나다, 합나다, 습나다)
    (re.compile(r"([가-힣]*)해중니다"), r"\1해줍니다"),
    (re.compile(r"([가-힣]*)어중니다"), r"\1어줍니다"),
    (re.compile(r"([가-힣]*)려중니다"), r"\1려줍니다"),
    (re.compile(r"([가-힣]*)와중니다"), r"\1와줍니다"),
    (re.compile(r"([가-힣]*)줄여중니다"), r"\1줄여줍니다"),
    (re.compile(r"([가-힣]*)높여중니다"), r"\1높여줍니다"),
    (re.compile(r"([가-힣]*)가져움니다"), r"\1가져옵니다"),
    (re.compile(r"([가-힣]*)러움니다"), r"\1러옵니다"),
    (re.compile(r"([가-힣]*)여움니다"), r"\1여옵니다"),
    (re.compile(r"([가-힣]*)펴움니다"), r"\1펴봅니다"),
    (re.compile(r"([가-힣]*)제거움니다"), r"\1제거됩니다"),
    (re.compile(r"([가-힣]*)업로드움니다"), r"\1업로드됩니다"),
    (re.compile(r"([가-힣]*)시흉니다"), r"\1시됩니다"),
    (re.compile(r"([가-힣]*)비흉니다"), r"\1비됩니다"),
    (re.compile(r"([가-힣]*)바흉니다"), r"\1바뀝니다"),
    (re.compile(r"추천드럽니다"), "추천드립니다"),
    (re.compile(r"기다럽니다"), "기다립니다"),
    (re.compile(r"([가-힣]*)입나다"), r"\1입니다"),
    (re.compile(r"([가-힣]*)[임합습]나다"), r"\1니다"),
    (re.compile(r"생길니다"), "생깁니다"),
    (re.compile(r"빠름니다"), "빠릅니다"),
    (re.compile(r"유지켜까요"), "유지될까요"),
    (re.compile(r"줄어들/는데"), "줄어드는데"),
    (re.compile(r"사용-니다"), "사용됩니다"),
    
    # 12. 가능형 및 조동사 (수 있게, 할 수)
    (re.compile(r"수\s*[엇핑잎앗D잇앞]게"), "수 있게"),
    (re.compile(r"([가-힣]+)활\s*수\s*있"), r"\1할 수 있"),
    (re.compile(r"만들없습니다"), "만들었습니다"),
    (re.compile(r"\b쉽제\b"), "쉽게"),
    (re.compile(r"패m"), "패턴"),
    
    # 13. 인명 및 AI 역사
    (re.compile(r"[탤엘알][런럴]\s*[튜특][껑립굉령링]"), "앨런 튜링"),
    (re.compile(r"[튜특][껑립굉령링]\s*테스트"), "튜링 테스트"),
    (re.compile(r"[튜특][껑립굉령](?=[은는이가을를에게의와과도])"), "튜링"),
    (re.compile(r"로[젠전제]불?렉"), "로젠블랫"),
    (re.compile(r"퍼센트론"), "퍼셉트론"),
    (re.compile(r"조조지타운"), "조지타운"),
    (re.compile(r"조지타운-BM"), "조지타운-IBM"),
    (re.compile(r"어[텐렌린]선"), "어텐션"),
    (re.compile(r"실프\s*어[렌텐]선"), "셀프 어텐션"),
    (re.compile(r"멀[티리][해하]드\s*어[렌텐]선"), "멀티헤드 어텐션"),
    (re.compile(r"소포트맥스"), "소프트맥스"),
    (re.compile(r"모\s*텔"), "모델"),
    (re.compile(r"첫지피티"), "챗지피티"),
    (re.compile(r"첫GPT"), "ChatGPT"),
    
    # 14. 문맥상 빈출 OCR 오탈자
    (re.compile(r"도움이\s*뵙니\s*다"), "도움이 됩니다"),
    (re.compile(r"사고가\s*발생있다"), "사고가 발생했다"),
    (re.compile(r"발생있다"), "발생했다"),
    (re.compile(r"유주은"), "유족은"),
    (re.compile(r"신고하지\s*안고"), "신고하지 않고"),
    (re.compile(r"피해를\s*키원다"), "피해를 키웠다"),
    (re.compile(r"일으권"), "일으킨"),
    (re.compile(r"형의를\s*받흔다"), "혐의를 받는다"),
    (re.compile(r"받흔다"), "받는다"),
    (re.compile(r"받앗"), "받았"),
    (re.compile(r"잡앗"), "잡았"),
    (re.compile(r"뇌출변로"), "뇌출혈로"),
    (re.compile(r"뇌출변"), "뇌출혈"),
    (re.compile(r"내려적고"), "내려졌고"),
    (re.compile(r"시망있다"), "사망했다"),
    (re.compile(r"키위드"), "키워드"),
    (re.compile(r"\b예\s+들어,"), "예를 들어,"),
    (re.compile(r"들없다고"), "들었다고"),
    (re.compile(r"맛취"), "맞춰"),
    (re.compile(r"맛게"), "맞게"),
    (re.compile(r"맛춤"), "맞춤"),
    (re.compile(r"기중치\s*패티이"), "가중치 패턴이"),
    (re.compile(r"패티이"), "패턴이"),
    (re.compile(r"기중치"), "가중치"),
    (re.compile(r"변경월\s*수"), "변경될 수"),
    (re.compile(r"손실월\s*수"), "손실될 수"),
    (re.compile(r"월\s*수\s*있"), "될 수 있"),
    (re.compile(r"저장되\s*있던"), "저장돼 있던"),
    (re.compile(r"\b하무로\b"), "하므로"),
    (re.compile(r"\b비레해\b"), "비례해"),
    (re.compile(r"\b이어저\b"), "이어져"),
    (re.compile(r"연구자들\s*에제"), "연구자들에게"),
    (re.compile(r"좌우염니다"), "좌우됩니다"),
    (re.compile(r"분아에는"), "분야에는"),
    (re.compile(r"인공지능\s*분아"), "인공지능 분야"),
    (re.compile(r"\b겨언이\b"), "격언이"),
    (re.compile(r"데이터률"), "데이터를"),
    (re.compile(r"\b십지\s*않은"), "쉽지 않은"),
    (re.compile(r"\b어려을\s*수"), "어려울 수"),
    (re.compile(r"\b운리적\b"), "윤리적"),
    (re.compile(r"성-이나"), "성별이나"),
    (re.compile(r"높\s*아집니다"), "높아집니다"),
    (re.compile(r"고려\s*사랑입니다"), "고려 사항입니다"),
    (re.compile(r"머신러님"), "머신러닝"),
    (re.compile(r"떨어저도"), "떨어져도"),
    (re.compile(r"잎\s*논"), "있는"),
    (re.compile(r"\b잎는\b"), "있는"),
    (re.compile(r"\b업는\b"), "없는"),
    (re.compile(r"\b종은\b(?=\s+대안)"), "좋은"),
    (re.compile(r"\b근\s+규모"), "큰 규모"),
    (re.compile(r"\b근\s+문제"), "큰 문제"),
    (re.compile(r"제시햇\s*습니다"), "제시했습니다"),
    (re.compile(r"비교하켓"), "비교하겠"),
    (re.compile(r"버티목"), "버팀목"),
    (re.compile(r"보젯습니다"), "보겠습니다"),
    (re.compile(r"신회할"), "신뢰할"),
    (re.compile(r"신회"), "신뢰"),
    (re.compile(r"뒷습니\s*다"), "됐습니다"),
    (re.compile(r"뒷습니다"), "됐습니다"),
    (re.compile(r"워습니다"), "였습니다"),
    (re.compile(r"있엎습니다"), "있었습니다"),
    (re.compile(r"눈문"), "논문"),
    (re.compile(r"눈매"), "문맥"),
    (re.compile(r"있율까"), "있을까"),
    (re.compile(r"인용펼"), "인용될"),
    (re.compile(r"담구하기"), "탐구하기"),
    (re.compile(r"담구"), "탐구"),
    (re.compile(r"곁\s*정짓는"), "결정짓는"),
    (re.compile(r"제안겠습니다"), "제안했습니다"),
    (re.compile(r"빛습니다"), "봤습니다"),
    (re.compile(r"주장쾌습니다"), "주장했습니다"),
    (re.compile(r"암는"), "않는"),
    (re.compile(r"알려저"), "알려져"),
    (re.compile(r"밭있\s*습니다"), "받았습니다"),
    (re.compile(r"않앉다\s*눈"), "않았다는"),
    (re.compile(r"제기행\s*습니다"), "제기했습니다"),
    (re.compile(r"중요해적습니다"), "중요해졌습니다"),
    (re.compile(r"대화지"), "대화를"),
    (re.compile(r"생각활"), "생각할"),
    (re.compile(r"앞는\s*지틀"), "있는지를"),
    (re.compile(r"앞는지"), "왔는지"),
    (re.compile(r"제시하습니다"), "제시했습니다"),
    (re.compile(r"앞게"), "있게"),
    (re.compile(r"앞는"), "있는"),
    (re.compile(r"콜라우드"), "클라우드"),
    (re.compile(r"콜래스|콤래스"), "클래스"),
    (re.compile(r"프콤프트"), "프롬프트"),
    (re.compile(r"콜라이언트"), "클라이언트"),
    (re.compile(r"인텍스"), "인덱스"),
    (re.compile(r"시권스"), "시퀀스"),
    (re.compile(r"임겟값"), "임계값"),
    (re.compile(r"자원의\s*저주"), "차원의 저주"),
    (re.compile(r"자원\s*축소"), "차원 축소"),
    (re.compile(r"전저리"), "전처리"),
    (re.compile(r"\b저리\b(?=\s*(?:속도|시간|능력|과정|방법))"), "처리"),
    (re.compile(r"저리(할|하는|하고|해|된|될|되어|되지|하지|하면|하게|됨을|되기|됩니다|했습)"), r"처리\1"),
    (re.compile(r"자이점"), "차이점"),
    (re.compile(r"자이(?:가|를|로|에|의)"), lambda m: "차이" + m.group(0)[2:]),
    (re.compile(r"사소한\s*자이"), "사소한 차이"),
    (re.compile(r"큰\s*자이"), "큰 차이"),
    (re.compile(r"독사들|독지들"), "독자들"),
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
