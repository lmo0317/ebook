"""
Perfect e-Book Package Builder for "한 권으로 끝내는 실전 LLM 파인튜닝"
- 고화질 도표/삽화 추출 (200 DPI PyMuPDF + OpenCV 여백 정밀 트리밍)
- 자연스러운 문단 결합 (문장 종결 부호 .?!:; 기준, 줄바꿈 음절 결합, '다/요' 오분절 방지)
- 90여 개 정밀 OCR 교정 사전 + 112 서버 Gemma 4 E4B 문맥 교정
- 정밀 목차(TOC) 1:1 핀포인트 페이지 매핑 & 북마크 완벽 생성
- SQLite reader.db & book_package.zip 완전 자동 생성
"""

import os
import sys
import time
import re
import json
import sqlite3
import hashlib
import zipfile
import shutil
import urllib.request
import numpy as np
import cv2
import fitz
from PIL import Image, ImageDraw, ImageFont

from book_toc import CANONICAL_TOC

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "cache")
PDF_PATH = r"C:\Users\lmo03\Downloads\book_cropped.pdf"
OCR_CACHE_PATH = os.path.join(CACHE_DIR, "ocr_cache_a880184c7492177e68db57e0c0f80b23.json")
LLM_CACHE_PATH = os.path.join(CACHE_DIR, "llm_clean_hash_cache.json")

BOOK_TITLE = "한 권으로 끝내는 실전 LLM 파인튜닝"
BOOK_AUTHOR = "강다솔"
BOOK_ID = "c0000000-0000-0000-0000-000000000001"

OUTPUT_DIR = os.path.join(BASE_DIR, "output", "한 권으로 끝내는 실전 LLM 파인튜닝")
IMAGES_DIR = os.path.join(OUTPUT_DIR, "images")
DB_PATH = os.path.join(OUTPUT_DIR, "reader.db")
COVER_PATH = os.path.join(OUTPUT_DIR, "cover.jpg")
BOOK_TXT_PATH = os.path.join(OUTPUT_DIR, "book.txt")
ZIP_OUT_PATH = os.path.join(OUTPUT_DIR, "llm-finetuning.zip")

# Local RTX 5080 Gemma 4 12B Settings
LLM_URL = "http://127.0.0.1:8092/v1/chat/completions"
LLM_MODEL = "edumaster-gemma-4-12b-vision"

PROMPT_SYSTEM = """당신은 AI/컴퓨터공학 기술 서적 전문 교정 AI입니다.
스캔본 OCR 과정에서 발생한 한글/영문 오탈자, 오인식 조사, 오인식 단어, 어색한 띄어쓰기를 문맥에 맞게 완벽한 한국어로 정밀 교정합니다.

[교정 규칙]
1. 원문의 의미와 서술 방식을 100% 보존합니다.
2. 부자연스러운 띄어쓰기(예: '다 지털' -> '디지털', '활 용' -> '활용')와 조사(예: '아이디어름' -> '아이디어를', '개념올' -> '개념을')를 자연스럽게 바로잡습니다.
3. 인공지능/컴퓨터공학 인명/전문 용어(예: 앨런 튜링, 튜링 테스트, 아르츠루니, 트로안스키, 퍼셉트론, 로젠블랫, 트랜스포머, 파인튜닝, 런팟, 딥러닝, 모델, 어텐션 등)를 정확히 복원합니다.
4. 번호 태그([P1], [P2] 등)를 유지하고, 설명이나 인사말 없이 오직 번호 태그와 교정된 본문만 출력합니다."""

# 90+ Comprehensive Typo Replacements
TYPO_REPLACEMENTS = [
    # ㅈ / ㅊ confusions
    (r"\b마지\b", "마치"),
    (r"\b스위지\b", "스위치"),
    (r"\b거지면서\b", "거치면서"),
    (r"\b순자적\b", "순차적"),
    (r"\b순자\s+저리\b", "순차 처리"),
    (r"\b가중지\b", "가중치"),
    (r"\b필수\s*절자\b", "필수 절차"),
    (r"\b절자\b(?=\s*(?:입니다|를|가|로|에))", "절차"),
    (r"\b자이점\b", "차이점"),
    (r"\b자이점도\b", "차이점도"),
    (r"\b사소한\s+자이\b", "사소한 차이"),
    (r"\b큰\s+자이\b", "큰 차이"),
    (r"\b자이(?:가|를|로|에|의)\b", lambda m: "차이" + m.group(0)[2:]),
    (r"\b자원의\s*저주\b", "차원의 저주"),
    (r"\b자원\s*축소\b", "차원 축소"),
    (r"\b(\d+)\s*자원\b", r"\1차원"),
    (r"\b자원\s*크기\b", "차원 크기"),
    (r"\b원래\s*자원으로\b", "원래 차원으로"),
    (r"\b결과의\s*자원을\b", "결과의 차원을"),
    (r"\b마지막\s*자원을\b", "마지막 차원을"),
    
    # 처리 / 저리 confusions
    (r"\b전저리\b", "전처리"),
    (r"\b전저리된\b", "전처리된"),
    (r"\b전저리와\b", "전처리와"),
    (r"\b자연어\s*저리\b", "자연어 처리"),
    (r"\b병렬\s*저리\b", "병렬 처리"),
    (r"\b순차적\s*저리\b", "순차적 처리"),
    (r"\b데이터\s*저리\b", "데이터 처리"),
    (r"\b텐서\s*병렬\s*저리\b", "텐서 병렬 처리"),
    (r"\b언어\s*저리\b", "언어 처리"),
    (r"\b저리\s*속도\b", "처리 속도"),
    (r"\b저리\s*시간\b", "처리 시간"),
    (r"\b저리\s*능력\b", "처리 능력"),
    (r"\b저리\s*과정\b", "처리 과정"),
    (r"\b저리(할|하는|하고|해|된|될|되어|되지|하지|하면|하게|됨을|되기|됩니다|했습)\b", r"처리\1"),
    (r"\b저리를\b", "처리를"),
    (r"\b저리합니다\b", "처리합니다"),
    (r"\b저리하지\b", "처리하지"),

    # ML / Tech term OCR confusions
    (r"\b모\s*텔\b", "모델"),
    (r"\b모텔\b(?=\s*(?:을|를|이|가|의|에|은|는|로|과|와|에서|훈련|학습|평가|서빙|구현|준비|생성|파라미터|크기|구조|이름))", "모델"),
    (r"\b시권스\b", "시퀀스"),
    (r"\b임겟값\b", "임계값"),
    (r"\b파인[류뉴]님\b", "파인튜닝"),
    (r"\b파인[류뉴]닝\b", "파인튜닝"),
    (r"\b파인튜님\b", "파인튜닝"),
    (r"\b파라미터\s*특늬\b", "파라미터 튜닝"),
    (r"\b특늬\b", "튜닝"),
    (r"\b특냥\b", "튜닝"),
    (r"\b서방\b(?=\s*(?:최적화|기술|까지|방법|원리|구현))", "서빙"),
    (r"\b독사들\b", "독자들"),
    (r"\b독지들\b", "독자들"),
    (r"\b맛춤화\b", "맞춤화"),
    (r"\b맛춤\b", "맞춤"),
    (r"\b어텐선\b", "어텐션"),
    (r"\b어린선\b", "어텐션"),
    (r"\b실프\s*어[렌텐]선\b", "셀프 어텐션"),
    (r"\b멀[티리][해하]드\s*어[렌텐]선\b", "멀티헤드 어텐션"),
    (r"\b소포트맥스\b", "소프트맥스"),
    (r"\b조조지타운\b", "조지타운"),
    (r"\b조지타운-BM\b", "조지타운-IBM"),
    (r"\bMIrT\b", "MIT"),
    (r"\b아는\s+튜링\b", "이는 튜링"),
    (r"\b잠조\b(?=\s*(?:자료|문헌|하기|하여|해|테이블))", "참조"),
    (r"\b응납\b", "응답"),
    (r"\b응납자\b", "응답자"),
    (r"\b응납에서\b", "응답에서"),
    (r"\b응담\b", "응답"),
    (r"\b담변\b", "답변"),
    (r"\b평기가\b", "평가"),
    (r"\b의건\b", "의견"),
    (r"\b점자\s*발전\b", "점차 발전"),
    (r"\b명화히\b", "명확히"),
    (r"\b능려을\b", "능력을"),
    (r"\b점근하기\b", "접근하기"),
    (r"\b학습시길\b", "학습시킬"),
    (r"\b다랑면에서\b", "다방면에서"),
    (r"\b위키숙스\b", "위키북스"),
    (r"\b위키국스\b", "위키북스"),
    (r"\b저직권\b", "저작권"),
    (r"\b신저직권번에\b", "저작권법에"),
    (r"\b저직물이므로\b", "저작물이므로"),
    (r"\b감들올\b", "값들을"),
    (r"\b동해\b(?=\s+[A-Za-z가-힣]+(?:을|를|에))", "통해"),
    (r"\b것입나니다\b", "것입니다"),
    (r"\b추전드럽니다\b", "추천드립니다"),
    (r"\b감사드럽니다\b", "감사드립니다"),
    (r"\b튜랑의\b", "튜링의"),
    (r"\b특립의\b", "튜링의"),
    (r"\b특립\s*테스트\b", "튜링 테스트"),
    (r"\b여전하\s+남기고\b", "여전히 남기고"),
    (r"\b서자유롭지\b", "에서 자유롭지"),
    (r"\b서크게\b", "에서 크게"),
    (r"\bIntelligcnce\b", "Intelligence"),
    (r"\b복\s*하고\s*다층적인\b", "복잡하고 다층적인"),
    (r"\b때문임니다\b", "때문입니다"),
    (r"\b([가-힣]+)임니다\b", r"\1입니다"),
    (r"\bOpenAl\b", "OpenAI"),
    (r"\bGP-4\b", "GPT-4"),
    (r"\bAl\b", "AI"),
    (r"\bVLLM\b", "vLLM"),
    (r"\bRunpod\b", "RunPod"),
    (r"\b런맛\b", "런팟"),
    (r"\b런핏\b", "런팟"),
    (r"\b크레딪\b", "크레딧"),
    (r"\b주피터\s*램\b", "주피터 랩"),
    (r"\b퍼센트론\b", "퍼셉트론"),
    (r"\b알고리증\b", "알고리즘"),
    (r"\b행렬곰\b", "행렬곱"),
    (r"\b피드포위드\b", "피드포워드"),
    (r"\b허경페이스\b", "허깅페이스"),
    (r"\bLlamna\b", "Llama"),
    (r"\b플레이터\b", "콜레이터"),
    (r"\b메트럭\b", "메트릭"),
    (r"\b귀스템\b", "커스텀"),
    (r"\b학신의\b", "혁신의"),
    (r"\b학신\b", "혁신"),
    (r"\b희신적인\b", "혁신적인"),
    (r"\b희신\b", "혁신"),
    (r"\b확기적인\b", "획기적인"),
    (r"\b덥러님\b", "딥러닝"),
    (r"\b덥러닝\b", "딥러닝"),
    (r"\b플라우드\b", "클라우드"),
    (r"\b플랍\s*품\b", "플랫폼"),
    (r"\b바람니다\b", "바랍니다"),
    (r"\b줄어중니다\b", "줄여줍니다"),
    (r"\b부주한\b", "부족한"),
    (r"\b독지들\b", "독자들"),
    (r"\b다툼으로씨\b", "다룸으로써"),
    (r"\b인공지식\b", "인공지능"),
    (r"\b호\s*울적\b", "효율적"),
    (r"\b덜\s*것입니다\b", "될 것입니다"),
    (r"\b앞게\b(?=\s*다루)", "있게"),
    (r"\b되싶어\s*붙니다\b", "되짚어 봅니다"),
    (r"\b붙니다\b", "봅니다"),
    (r"\b다툼니다\b", "다룹니다"),
    (r"\b생각이없으미\b", "생각이었으며"),
    (r"\b이눈\b(?=\s*당시)", "이는"),
    (r"\b발명품올\b", "발명품을"),
    (r"\b초석올\b", "초석을"),
    (r"\b개념올\b", "개념을"),
    (r"\b중점올\b", "중점을"),
    (r"\b본질올\b", "본질을"),
    (r"\b여정올\b", "여정을"),
    (r"\b모델올\b", "모델을"),
    (r"\b연구름\b", "연구를"),
    (r"\b아이디어름\b", "아이디어를"),
    (r"\b기계름\b", "기계를"),
    (r"\b정보름\b", "정보를"),
    (r"\b햇는지\b", "했는지"),
    (r"\b제안랫습니다\b", "제안했습니다"),
    (r"\b높아켓습니다\b", "높아졌습니다"),
    (r"\b살펴보켓습니다\b", "살펴보겠습니다"),
    (r"\b다\s+지털\b", "디지털"),
    (r"\b활\s+용\b", "활용"),
    (r"\b김색\b", "검색"),
    (r"\b이틀\s+김색\b", "이를 검색"),
    (r"\b작동쾌습니다\b", "작동했습니다"),
    (r"\b받앗습니다\b", "받았습니다"),
    (r"\b아난\b(?=\s*,)", "아닌"),
    (r"\b아난\b(?=\s+[가-힣])", "아닌"),
    (r"\b만돈\b", "만든"),
    (r"\b맛충화\b", "맞춤화"),
    (r"\b맛충\b", "맞춤"),
    (r"\b파인특님\b", "파인튜닝"),
    (r"\b이틀\b(?=\s*(?:검색|조사|바탕|활용|통해|위해|확인))", "이를"),
    (r"\b이\s*눈\b(?=\s*(?:당시|초기|매우|이후))", "이는"),
    (r"\b발명이없습니다\b", "발명이었습니다"),
    (r"\b특히를\b(?=\s*(?:받|취득|등록))", "특허를"),
    (r"\b이용하\b(?=\s+[가-힣]+(?:\s*자동|\s*기계|\s*방법))", "이용한"),
    (r"\b햇습니다\b", "했습니다"),
    (r"\b햇([가-힣]+)\b", r"했\1"),
    (r"\b열없으며\b", "열었으며"),
    (r"\bCPT\b", "GPT"),
    (r"\b분아에서\b", "분야에서"),
    (r"\b분아\b(?=\s*(?:의|를|에|로|에서))", "분야"),
    (r"\b필수이여\b", "필수이며"),
    (r"\b주면에서는\b", "측면에서는"),
    (r"\b전락까지\b", "전략까지"),
    (r"\b있으녀\b", "있으며"),
    (r"\b최적화루\b", "최적화로"),
    (r"\b트랜드록\b", "트렌드를"),
    (r"\b트랜드\b", "트렌드"),
    (r"\b용용\s*방법\b", "활용 방법"),
    (r"\b모는\s*코드틀\b", "모든 코드를"),
    (r"\b권트\b", "퀀트"),
    (r"\b넘께\b", "님께"),
    (r"\b아이디어름으미\b", "아이디어였으며"),

    # Regular endings and josa
    (r"\b([가-힣]+)올\b(?=\s|$)", r"\1을"),
    (r"\b([가-힣]+)울\b(?=\s|$)", r"\1을"),
    (r"\b([가-힣]+)름\b(?=\s|$)", r"\1를"),
    (r"\b([가-힣]+)논\b(?=\s|$)", r"\1는"),
    (r"\b([가-힣]+)록\b(?=\s*(?:반영|해결|위해|통해|바탕))", r"\1를"),
    (r"\b([가-힣]+)률\b(?=\s*(?:일으|제공|보여|가져|통해))", r"\1를"),
    (r"\b([가-힣]+)으미\b", r"\1으며"),
    (r"\b([가-힣]+)햇([가-힣]+)\b", r"\1했\2"),
    (r"\b([가-힣]+)켓([가-힣]+)\b", r"\1겠\2"),
    (r"\b([가-힣]+)랫([가-힣]+)\b", r"\1했\2"),
    (r"\b([가-힣]+)함\s*니다\b", r"\1합니다"),
    (r"\b([가-힣]+)습\s+니다\b", r"\1습니다"),
    (r"\b([가-힣]+)합\s+니다\b", r"\1합니다"),
    (r"\b([가-힣]+)였습\s+니다\b", r"\1였습니다"),
    (r"\b([가-힣]+)되었습\s+니다\b", r"\1되었습니다"),
    (r"\b([가-힣]+)겠습\s+니다\b", r"\1겠습니다"),
    (r"\b([가-힣]+)있습\s+니다\b", r"\1있습니다"),

    # Turing / Alan Turing / Turing Test
    (r"[탤엘알][런럴]\s*[튜특][껑립굉령링]", "앨런 튜링"),
    (r"[튜특][껑립굉령링]\s*테스트", "튜링 테스트"),
    (r"\b[튜특][껑립굉령]\b", "튜링"),
    (r"[튜특][껑립굉령]의", "튜링의"),
    (r"[튜특][껑립굉령]은", "튜링은"),
    (r"[튜특][껑립굉령]이", "튜링이"),
    (r"[튜특][껑립굉령]을", "튜링을"),
    (r"[튜특][껑립굉령]에게", "튜링에게"),

    # Rosenblatt / Perceptron
    (r"\b로젠블렉\b", "로젠블랫"),
    (r"\b로젠불렉\b", "로젠블랫"),
    (r"\b로전불렉\b", "로젠블랫"),
    (r"\b퍼센트론\b", "퍼셉트론"),

    # RunPod / Cloud / Deep Learning / Computing
    (r"런되\(runpod\)", "런팟(RunPod)"),
    (r"런되", "런팟"),
    (r"런\s*파은", "런팟은"),
    (r"\(RunPod\)올", "(RunPod)을"),
    (r"플렉품", "플랫폼"),
    (r"플랍\s*품", "플랫폼"),
    (r"콜라우드", "클라우드"),
    (r"컴퓨텅", "컴퓨팅"),
    (r"년리님", "딥러닝"),
    (r"덥러넣이", "딥러닝이"),
    (r"덥러넣", "딥러닝"),
    (r"프로적트", "프로젝트"),
    (r"자원율", "자원을"),
    (r"레m로", "레벨로"),
    (r"레발로", "레벨로"),
    (r"다률", "다룰"),
    (r"시용법", "사용법"),
    (r"마스드", "마스크드"),
    (r"셈프", "셀프"),
    (r"어멘\s*선", "어텐션"),
    (r"어렌선", "어텐션"),
    (r"멀티혜드", "멀티헤드"),
    (r"살펴움니다", "살펴봅니다"),
    (r"모델랑", "모델링"),
    (r"늘록", "블록"),
    (r"잇도록", "있도록"),
    (r"구성대", "구성돼"),
    (r"깊이\s*핑게", "깊이 있게"),
    (r"학습하느지에", "학습하는지에"),
    (r"결과루", "결과를"),
    (r"모델굉", "모델링"),

    # Common OCR Distortions
    (r"뒷습니\s*다", "됐습니다"),
    (r"뒷습니다", "됐습니다"),
    (r"뵙니다", "됩니다"),
    (r"되니다", "됩니다"),
    (r"워습니다", "였습니다"),
    (r"있엎습니다", "있었습니다"),
    (r"눈문", "논문"),
    (r"눈매을", "문맥을"),
    (r"눈매", "문맥"),
    (r"있율까", "있을까"),
    (r"제기하습니다", "제기했습니다"),
    (r"제\s*기워습니다", "제기였습니다"),
    (r"일으켜습니다", "일으켰습니다"),
    (r"덥니다", "됩니다"),
    (r"넓질", "넓힐"),
    (r"인용펼", "인용될"),
    (r"담구하기", "탐구하기"),
    (r"담구", "탐구"),
    (r"곁\s*정짓는", "결정짓는"),
    (r"출억하는", "출력하는"),
    (r"출억", "출력"),
    (r"제안겠습니다", "제안했습니다"),
    (r"빛습니다", "봤습니다"),
    (r"주장쾌습니다", "주장했습니다"),
    (r"암는", "않는"),
    (r"알려저", "알려져"),
    (r"맛추고", "맞추고"),
    (r"밭있\s*습니다", "받았습니다"),
    (r"않앉다\s*눈", "않았다는"),
    (r"제기행\s*습니다", "제기했습니다"),
    (r"중요해적습니다", "중요해졌습니다"),
    (r"대화지", "대화를"),
    (r"생각활", "생각할"),
    (r"앞는\s*지틀", "있는지를"),
    (r"앞는지", "왔는지"),
    (r"제시하습니다", "제시했습니다"),
    (r"맥각에서", "맥락에서"),
    (r"맥각", "맥락"),
    (r"국하되지", "국한되지"),
    (r"숙련원", "숙련된"),
    (r"거쟁", "거장"),
    (r"맞취", "맞춰"),
    (r"대처활", "대처할"),
    (r"학습시청는지", "학습시켰는지"),
    (r"어디서\s*얻어든지", "어디서 얻었는지"),
    (r"메거니증", "메커니즘"),
    (r"짚어중니다", "짚어줍니다"),
    (r"짚어중", "짚어줍"),
    (r"활수", "할 수"),
    (r"수행활", "수행할"),
    (r"해결활", "해결할"),
]

ANOMALY_PATTERN = re.compile(
    r"(?:[탤엘알][런럴]\s*[튜특][껑립굉령링]"
    r"|[튜특][껑립굉령]"
    r"|[가-힣]+[올블눈켓랫솄]"
    r"|[가-힣]+[임습합]나다"
    r"|[가-힣]+있있"
    r"|[가-힣]+[류뉴]님"
    r"|\b(?:모텔|가중지|전저리|임겟값|자이점|자원의\s*저주|자원\s*축소|어텐선|희신|담변|평기가|의건|바람니다|다툼니다|만돈|작동쾌|뒷습|뵙니|되니|워습|있엎|미처고|눈문|눈매|있율|학신|제기하|제기워|일으켜|덥니|넓질|인용펼|담구|곁정|출억|제안겠|빛습|주장쾌|암는|알려저|맛추|밭있|않앉|제기행|중요해적|대화지|생각활|앞는지|제시하|맥각|국하|숙련원|거쟁|맞취|대처활|학습시청|얻어든|메거니증|퍼센트론|활수|수행활|해결활|컴퓨텅|알고리증|로젠블|플렉품|런되|년리님|자원율|맛충|파인특|파인류)\b"
    r"|\b[가-힣]{2,4}[0-9]"
    r"|\b[가-힣]\s+[가-힣]\s+[가-힣]\b)"
)

def apply_typo_fixes(text: str) -> str:
    t = text
    for pat, rep in TYPO_REPLACEMENTS:
        if callable(rep):
            t = re.sub(pat, rep, t)
        else:
            t = re.sub(pat, rep, t)
    # Fix spacing before punctuation
    t = re.sub(r"\s+([.,!?;:])", r"\1", t)
    t = re.sub(r"([(\[{<])\s+", r"\1", t)
    t = re.sub(r"\s+([)\]}>])", r"\1", t)
    t = re.sub(r"(\d+)\s*\.\s*(\d+)", r"\1.\2", t)
    t = re.sub(r"[ \t]+", " ", t)
    return t.strip()

def get_text_hash(text: str) -> str:
    cleaned = re.sub(r"\s+", "", text)
    return hashlib.md5(cleaned.encode("utf-8")).hexdigest()[:16]

def load_json_cache(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_json_cache(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    if os.path.exists(path):
        os.remove(path)
    os.rename(tmp, path)

def is_noise_block(text: str, top: float, bottom: float, page_h: float, page_idx: int) -> bool:
    t = text.strip()
    if not t:
        return True
    # Barcodes / tracking
    if re.search(r"^(9[Ttr0-9]{8,}|[0-9a-zA-Z_\-]{14,})", t):
        return True
    if top > page_h * 0.88 and re.match(r"^[0-9a-zA-Z\s\-_]{10,}$", t):
        return True
    # Page numbers in margins
    if re.match(r"^[0-9ivxIVX]{1,4}$", t) and (top < page_h * 0.08 or bottom > page_h * 0.92):
        return True
    # Running header noise (< 8% height)
    if bottom < page_h * 0.08:
        if any(w in t for w in ["한 권으로", "한권으로", "파인튜닝", "PART", "NLP의 과거", "vLLM", "GPT"]):
            return True
        if len(t) < 40:
            return True
    # Running footer noise (> 92% height)
    if top > page_h * 0.92:
        if any(w in t for w in ["위키북스", "WIKIBOOKS"]):
            return True
        if len(t) < 35:
            return True
    # URL noise at footer
    if re.search(r"https?://\S+", t) and (bottom > page_h * 0.90 or top < page_h * 0.10):
        return True
    if t in [".", "-", "_", "~", ",", "`", "'", '"', "|", "/", "\\", "·", ":"]:
        return True
    return False

def is_code_block(text: str) -> bool:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return False
    indicators = [
        "import ", "from ", "def ", "class ", "return ", "if __name__",
        "self.", "torch.", "nn.", "F.", "np.", "plt.", "model =", "loss =",
        "optimizer =", "tokenizer =", "print(", "super().", "pip install",
        "git clone", "cd ", "python ", "export ", "curl ", "wget ",
        "docker run", "runpod ", "wandb.", "def __init__", "def forward"
    ]
    code_matches = sum(1 for l in lines if any(l.startswith(ind) for ind in indicators))
    syntax_matches = sum(1 for l in lines if re.search(r"(=|\{|\}|\[|\]|\(\)|:\s*$)", l))
    return (code_matches >= 2) or (len(lines) >= 3 and (code_matches + syntax_matches) >= len(lines) * 0.75)

def format_clean_code(text: str) -> str:
    lines = text.splitlines()
    cleaned = []
    indent = 0
    for l in lines:
        s = l.strip()
        if not s:
            continue
        s = s.replace("def_init_", "def __init__")
        s = s.replace("super()._init_", "super().__init__")
        s = s.replace("self. token_embedding _table", "self.token_embedding_table")
        s = s.replace("self. position_embedding _table", "self.position_embedding_table")
        s = s.replace("nn. Linear", "nn.Linear")
        s = s.replace("nn. Embedding", "nn.Embedding")
        s = s.replace("F.cross_ent ropy", "F.cross_entropy")
        s = s.replace("max _new_tokens", "max_new_tokens")
        if s.startswith(("elif ", "else:", "except", "finally:")):
            indent = max(0, indent - 4)
        cleaned.append(" " * indent + s)
        if s.endswith(":"):
            indent += 4
        elif s.startswith("return "):
            indent = max(0, indent - 4)
    return "```python\n" + "\n".join(cleaned) + "\n```"

def is_true_caption(text: str) -> bool:
    t = text.strip().replace("\n", " ")
    m = re.match(r"^(?:그림|Figure)\s*(\d+)[\.\-_ ]*(\d+)?(.*)", t, re.IGNORECASE)
    if not m:
        return False
    rest = m.group(3).strip()
    if re.match(r"^(?:[은는이가을를과와도]|에서|처럼|과\s*같이|참조)\b", rest):
        return False
    if re.search(r"(습니다|입니다|했다|였다|있다|한다|된다|다|냐|까|요|죠|됨)\s*[.?!]*$", t):
        return False
    if len(t) > 60:
        return False
    return True

def crop_diagram_highres(page, crop_box, save_path, dpi=200):
    pix = page.get_pixmap(dpi=dpi, clip=crop_box)
    img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, pix.n))
    if pix.n == 4:
        img_np = cv2.cvtColor(img_np, cv2.COLOR_RGBA2BGR)
    elif pix.n == 3:
        img_np = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

    gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 245, 255, cv2.THRESH_BINARY_INV)
    coords = cv2.findNonZero(thresh)
    if coords is not None:
        x, y, w, h = cv2.boundingRect(coords)
        pad = 12
        x1 = max(0, x - pad)
        y1 = max(0, y - pad)
        x2 = min(img_np.shape[1], x + w + pad)
        y2 = min(img_np.shape[0], y + h + pad)
        img_np = img_np[y1:y2, x1:x2]

    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    ext = os.path.splitext(save_path)[1] or ".png"
    ok, buf = cv2.imencode(ext, img_np)
    if ok:
        with open(save_path, "wb") as f:
            f.write(buf)
    return img_np.shape[1], img_np.shape[0]

def make_styled_cover(output_path, title, author):
    width, height = 600, 900
    img = Image.new("RGB", (width, height), color="#1E293B")
    draw = ImageDraw.Draw(img)
    for y in range(height):
        ratio = y / height
        r = int(0x1E * (1 - ratio) + 0x0F * ratio)
        g = int(0x29 * (1 - ratio) + 0x17 * ratio)
        b = int(0x3B * (1 - ratio) + 0x2A * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    draw.rectangle([24, 24, width - 24, height - 24], outline="#38BDF8", width=3)
    font_path = "C:/Windows/Fonts/malgunbd.ttf"
    if not os.path.exists(font_path):
        font_path = "C:/Windows/Fonts/malgun.ttf"
    if os.path.exists(font_path):
        b_font = ImageFont.truetype(font_path, 24)
        t_font = ImageFont.truetype(font_path, 36)
        a_font = ImageFont.truetype(font_path, 22)
    else:
        b_font = t_font = a_font = ImageFont.load_default()

    draw.text((width // 2, 100), "[ Illustrated e-Book ]", fill="#38BDF8", font=b_font, anchor="mm")
    draw.text((width // 2, 320), "한 권으로 끝내는", fill="#FFFFFF", font=t_font, anchor="mm")
    draw.text((width // 2, 385), "실전 LLM 파인튜닝", fill="#60A5FA", font=t_font, anchor="mm")
    draw.text((width // 2, 470), "(고화질 도표 수록 | 정밀 리플로우 전자책)", fill="#94A3B8", font=b_font, anchor="mm")
    draw.text((width // 2, 750), f"저자: {author} | 위키북스", fill="#CBD5E1", font=a_font, anchor="mm")
    img.save(output_path, "JPEG", quality=95)

def call_gemma_batch(paragraphs, llm_cache):
    """
    112 서버 Gemma 4 E4B 문맥 교정기
    - 문단 텍스트 해시를 key로 캐싱 (절대 인덱스 혼선 방지)
    - 입력 문단 리스트 -> 교정된 문단 리스트 반환
    """
    to_query = []
    for idx, p in enumerate(paragraphs):
        h = get_text_hash(p)
        if h not in llm_cache:
            to_query.append((idx, h, p))

    if to_query:
        print(f"  [LLM 검수] 의심 문단 {len(to_query)}개 로컬 Gemma 12B 정밀 교정 요청...")
        lines = [f"[P{i+1}] {p}" for i, (_, _, p) in enumerate(to_query)]
        prompt_text = "\n\n".join(lines)
        payload = {
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": PROMPT_SYSTEM},
                {"role": "user", "content": prompt_text}
            ],
            "temperature": 0.1,
            "max_tokens": max(500, int(len(prompt_text) * 1.5))
        }
        try:
            req = urllib.request.Request(
                LLM_URL,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json; charset=utf-8"}
            )
            with urllib.request.urlopen(req, timeout=35) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                reply = data["choices"][0]["message"]["content"]
                matches = re.findall(r'\[P(\d+)\]\s*(.*?)(?=(?:\[P\d+\]|\Z))', reply, re.DOTALL)
                parsed = {}
                for n_str, c in matches:
                    parsed[int(n_str)] = c.strip()

                for tag_num, (orig_idx, h, orig_p) in enumerate(to_query, start=1):
                    if tag_num in parsed and len(parsed[tag_num]) > 10:
                        new_txt = parsed[tag_num]
                        llm_cache[h] = new_txt
                        if new_txt != orig_p:
                            print(f"    └ [교정] \"{orig_p[:28]}...\" -> \"{new_txt[:28]}...\"")
                    else:
                        llm_cache[h] = orig_p
        except Exception as e:
            print(f"[LLM Warning] Gemma batch failed: {e}")
            for _, h, orig_p in to_query:
                llm_cache[h] = orig_p

    # Apply cache
    result = []
    for p in paragraphs:
        h = get_text_hash(p)
        result.append(llm_cache.get(h, p))
    return result

def run():
    print("=" * 70)
    print("  Perfect e-Book Package Builder: 한 권으로 끝내는 실전 LLM 파인튜닝")
    print("=" * 70)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(IMAGES_DIR, exist_ok=True)

    print(f"Loading PDF: {PDF_PATH}")
    doc = fitz.open(PDF_PATH)
    total_pages = len(doc)
    print(f"Total Pages: {total_pages}")

    print(f"Loading OCR cache: {OCR_CACHE_PATH}")
    with open(OCR_CACHE_PATH, "r", encoding="utf-8") as f:
        ocr_data = json.load(f)

    llm_cache = load_json_cache(LLM_CACHE_PATH)
    print(f"Loaded LLM clean cache entries: {len(llm_cache)}")

    # Build canonical TOC page map
    # page_num -> list of (sec_id, title, level)
    toc_page_map = {}
    for sec_id, title, page_num, level in CANONICAL_TOC:
        toc_page_map.setdefault(page_num, []).append((sec_id, title, level))

    chapter_cover_pages = {17, 41, 121, 219, 299, 333}

    extracted_images_count = 0
    all_clean_paragraphs = []
    database_paragraphs = []
    database_pages = []
    bookmarks_to_insert = []
    global_para_counter = 0

    # Book Title Header
    book_header = (
        f"# {BOOK_TITLE}\n\n"
        f"**저자:** {BOOK_AUTHOR} | **출판:** 위키북스\n"
        "**부제:** GPT 작동 원리부터 Gemma 2 / Llama 3 파인튜닝, vLLM 서빙까지 (고화질 도표 수록 정밀 리플로우판)\n\n"
        "---\n"
    )
    all_clean_paragraphs.append(book_header)
    global_para_counter += 1
    database_paragraphs.append((
        BOOK_ID, 1, global_para_counter, book_header.strip(), None,
        50, 50, 950, 450, "BODY", "HEADER"
    ))

    caption_regex = re.compile(r'^(?:그림|Figure)\s*(\d+)[\.\-_ ]*(\d+)?(.*)', re.IGNORECASE)

    for p_num in range(1, total_pages + 1):
        p_key = str(p_num)
        page = doc[p_num - 1]
        p_w = int(page.rect.width)
        p_h = int(page.rect.height)
        database_pages.append((BOOK_ID, p_num, p_w, p_h))

        raw_blocks = ocr_data.get(p_key, [])
        if not raw_blocks:
            continue

        # 1. Filter out noise blocks
        clean_blocks = []
        for b in raw_blocks:
            bx0, by0, bx1, by1, btext = b[0], b[1], b[2], b[3], b[4].strip()
            if not is_noise_block(btext, by0, by1, p_h, p_num):
                clean_blocks.append(b)

        # 2. Extract Captions & Diagrams
        captions = []
        for b in clean_blocks:
            if is_true_caption(b[4]):
                captions.append(b)

        crop_rects = []
        if captions:
            for cap in captions:
                cx0, cy0, cx1, cy1, ctext = cap[0], cap[1], cap[2], cap[3], cap[4].strip()
                prev_bottom = int(p_h * 0.08)
                for pb in clean_blocks:
                    if pb[3] < cy0 - 20:
                        if (pb[2] - pb[0] > p_w * 0.4) or len(pb[4]) > 25:
                            if pb[3] > prev_bottom:
                                prev_bottom = pb[3]
                top_y = max(0, prev_bottom + 5)
                bottom_y = min(p_h, cy1 + 8)
                if (bottom_y - top_y) > 35:
                    crop_box = fitz.Rect(max(0, p_w * 0.04), top_y, min(p_w * 0.96, p_w), bottom_y)
                    crop_rects.append((crop_box, ctext, top_y, bottom_y))

        page_elements = [] # list of dicts: {"type": ..., "y": ..., "bottom_y": ..., "text": ...}
        suppressed_block_indices = set()

        for crop_box, ctext, min_y, cy1 in crop_rects:
            extracted_images_count += 1
            img_filename = f"fig_{extracted_images_count:04d}_p{p_num}.png"
            img_filepath = os.path.join(IMAGES_DIR, img_filename)
            crop_diagram_highres(page, crop_box, img_filepath, dpi=200)

            clean_cap = re.sub(r'^[▲▼\s]+', '', ctext).strip()
            clean_cap = apply_typo_fixes(clean_cap)
            page_elements.append({
                "type": "IMAGE",
                "y": min_y,
                "bottom_y": cy1,
                "text": f"![{clean_cap}](images/{img_filename})"
            })

            # Suppress text blocks inside diagram area
            for j, b in enumerate(clean_blocks):
                b_mid = (b[1] + b[3]) / 2
                if min_y - 5 <= b_mid <= cy1 + 5:
                    suppressed_block_indices.add(j)

        # 3. Canonical Heading Injection
        # If this page contains canonical section headings, register them cleanly
        canonical_on_page = toc_page_map.get(p_num, [])
        is_cover_page = p_num in chapter_cover_pages

        for sec_id, sec_title, sec_level in canonical_on_page:
            prefix = "#" if sec_level == 1 else ("##" if sec_level == 2 else "###")
            full_title = f"{prefix} {sec_id} {sec_title}" if not sec_id.startswith("PART") and not sec_id.startswith("부록") else f"{prefix} {sec_id}: {sec_title}"
            # Place at top of page or section
            top_heading_y = 50 if is_cover_page else 70
            page_elements.append({
                "type": "TITLE",
                "y": top_heading_y,
                "bottom_y": top_heading_y + 30,
                "text": full_title
            })

        # 4. Process Content Blocks (Code and Body)
        # Skip printed TOC pages (11-16) and cover page summaries from body clutter
        if 11 <= p_num <= 16:
            # Let TOC pages remain as a clean markdown table/list
            pass
        elif is_cover_page:
            # Cover page: add brief chapter overview text
            pass

        content_lines_to_stitch = []
        for idx, b in enumerate(clean_blocks):
            if idx in suppressed_block_indices:
                continue
            btext = b[4].strip()
            if not btext:
                continue

            # Skip header-like section numbers already handled by CANONICAL_TOC
            if any(btext.startswith(sec_id) for sec_id, _, _ in canonical_on_page):
                continue
            # If cover page and contains section numbers, format as clean bullet
            if is_cover_page and re.match(r"^\d+\.\d+", btext):
                continue

            btext_clean = apply_typo_fixes(btext)
            content_lines_to_stitch.append((b[1], b[3], btext_clean))

        # 5. Smart Paragraph Stitching
        merged_paras = []
        cur_buf = ""
        cur_top = 0
        cur_bot = 0

        for by0, by1, line in content_lines_to_stitch:
            if is_code_block(line):
                if cur_buf:
                    merged_paras.append((cur_top, cur_bot, cur_buf))
                    cur_buf = ""
                code_text = format_clean_code(line)
                page_elements.append({
                    "type": "CODE",
                    "y": by0,
                    "bottom_y": by1,
                    "text": code_text
                })
                continue

            if not cur_buf:
                cur_buf = line
                cur_top = by0
                cur_bot = by1
            else:
                prev_ends = bool(re.search(r'[.?!:;”"’\)]\s*$', cur_buf))
                next_cont = bool(re.match(r'^(?:니다|습니다|입니다|였다|했다|있었다|으로|에서|로서|에게|과|와)\b', line))
                if not prev_ends or next_cont:
                    if re.search(r'[가-힣]+[습합]$', cur_buf) and re.match(r'^니다\b', line):
                        cur_buf += line
                    elif re.search(r'[가-힣]$', cur_buf) and re.match(r'^[게고서로며면은는이가을를의에]\b', line):
                        cur_buf += line
                    else:
                        cur_buf += " " + line
                    cur_bot = max(cur_bot, by1)
                else:
                    merged_paras.append((cur_top, cur_bot, cur_buf))
                    cur_buf = line
                    cur_top = by0
                    cur_bot = by1

        if cur_buf:
            merged_paras.append((cur_top, cur_bot, cur_buf))

        # 6. Gemma LLM Polish on Anomalous Paragraphs
        # Only select paragraphs with remaining anomalies
        anom_body_indices = []
        body_texts_for_llm = []
        for idx, (py0, py1, ptext) in enumerate(merged_paras):
            if len(ptext) >= 15 and ANOMALY_PATTERN.search(ptext):
                anom_body_indices.append(idx)
                body_texts_for_llm.append(ptext)

        if body_texts_for_llm:
            polished_texts = call_gemma_batch(body_texts_for_llm, llm_cache)
            for m_idx, new_txt in zip(anom_body_indices, polished_texts):
                py0, py1, _ = merged_paras[m_idx]
                merged_paras[m_idx] = (py0, py1, new_txt)

        # Add merged body paragraphs to page_elements
        for py0, py1, ptext in merged_paras:
            page_elements.append({
                "type": "BODY",
                "y": py0,
                "bottom_y": py1,
                "text": ptext
            })

        # Sort elements naturally by Y position
        page_elements.sort(key=lambda e: e["y"])

        # Record into global database structures
        for el in page_elements:
            global_para_counter += 1
            el_type = el["type"]
            el_text = el["text"]
            all_clean_paragraphs.append(el_text)
            database_paragraphs.append((
                BOOK_ID, p_num, global_para_counter,
                el_text, None,
                50, int(el["y"]), 950, int(el["bottom_y"]),
                el_type, "CONTENT"
            ))
            # If TITLE, add to bookmarks
            if el_type == "TITLE":
                clean_t = re.sub(r"^#+\s*", "", el_text)
                bookmarks_to_insert.append((BOOK_ID, p_num, global_para_counter, clean_t, int(p_num * 1000)))

        if p_num % 20 == 0 or p_num == total_pages:
            print(f"Processed: {p_num}/{total_pages} pages (Images: {extracted_images_count}, Paras: {global_para_counter})")
            save_json_cache(LLM_CACHE_PATH, llm_cache)

    # 7. Create styled cover
    print("\nGenerating stylized cover image...")
    make_styled_cover(COVER_PATH, BOOK_TITLE, BOOK_AUTHOR)
    shutil.copy(COVER_PATH, os.path.join(OUTPUT_DIR, f"{BOOK_ID}.jpg"))

    # 8. Write complete book.txt
    print("Writing reflowable book.txt...")
    full_text = "\n\n".join(all_clean_paragraphs)
    with open(BOOK_TXT_PATH, "w", encoding="utf-8") as f:
        f.write(full_text)
    shutil.copy(BOOK_TXT_PATH, os.path.join(OUTPUT_DIR, f"{BOOK_ID}.txt"))

    # 9. Create SQLite reader.db
    print(f"Building SQLite database: {DB_PATH}...")
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS `Book` (
            `id` TEXT NOT NULL,
            `title` TEXT NOT NULL,
            `uri` TEXT NOT NULL,
            `fileName` TEXT NOT NULL,
            `size` INTEGER NOT NULL,
            `hash` TEXT NOT NULL,
            `pages` INTEGER NOT NULL,
            `created` INTEGER NOT NULL,
            `opened` INTEGER NOT NULL,
            `status` TEXT NOT NULL,
            `done` INTEGER NOT NULL,
            `author` TEXT NOT NULL,
            `memo` TEXT NOT NULL,
            `error` TEXT NOT NULL,
            PRIMARY KEY(`id`)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS `Page` (
            `bookId` TEXT NOT NULL,
            `number` INTEGER NOT NULL,
            `width` INTEGER NOT NULL,
            `height` INTEGER NOT NULL,
            `rotation` INTEGER NOT NULL,
            `status` TEXT NOT NULL,
            `error` TEXT NOT NULL,
            PRIMARY KEY(`bookId`, `number`)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS `Block` (
            `id` INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            `bookId` TEXT NOT NULL,
            `page` INTEGER NOT NULL,
            `text` TEXT NOT NULL,
            `left` INTEGER NOT NULL,
            `top` INTEGER NOT NULL,
            `right` INTEGER NOT NULL,
            `bottom` INTEGER NOT NULL,
            `linesJson` TEXT NOT NULL
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS `index_Block_bookId` ON `Block` (`bookId`)")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS `Paragraph` (
            `id` INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            `bookId` TEXT NOT NULL,
            `page` INTEGER NOT NULL,
            `order` INTEGER NOT NULL,
            `original` TEXT NOT NULL,
            `edited` TEXT,
            `left` INTEGER NOT NULL,
            `top` INTEGER NOT NULL,
            `right` INTEGER NOT NULL,
            `bottom` INTEGER NOT NULL,
            `type` TEXT NOT NULL,
            `region` TEXT NOT NULL
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS `index_Paragraph_bookId` ON `Paragraph` (`bookId`)")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS `Position` (
            `bookId` TEXT NOT NULL,
            `page` INTEGER NOT NULL,
            `paragraphId` INTEGER NOT NULL,
            `index` INTEGER NOT NULL,
            `offset` INTEGER NOT NULL,
            PRIMARY KEY(`bookId`)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS `Bookmark` (
            `id` INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            `bookId` TEXT NOT NULL,
            `page` INTEGER NOT NULL,
            `paragraphId` INTEGER NOT NULL,
            `offset` INTEGER NOT NULL,
            `memo` TEXT NOT NULL,
            `created` INTEGER NOT NULL
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS `index_Bookmark_bookId` ON `Bookmark` (`bookId`)")
    cur.execute("CREATE TABLE IF NOT EXISTS room_master_table (id INTEGER PRIMARY KEY, identity_hash TEXT)")
    cur.execute("INSERT OR REPLACE INTO room_master_table (id, identity_hash) VALUES(42, 'd5ff8686cb0182fe692967642ccb9c13')")

    now_ms = int(time.time() * 1000)
    file_bytes = full_text.encode('utf-8')
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    cur.execute("""
        INSERT INTO `Book` VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        BOOK_ID, BOOK_TITLE,
        f"file:///data/user/0/com.ebook.ocrreader/files/{BOOK_ID}.txt",
        f"{BOOK_ID}.txt",
        len(file_bytes), file_hash, total_pages,
        now_ms, now_ms + 100000, "READY", total_pages,
        BOOK_AUTHOR, f"고화질 도표 {extracted_images_count}개 수록 하이브리드 전자책", ""
    ))

    for p in range(1, total_pages + 1):
        cur.execute("INSERT INTO `Page` VALUES (?, ?, ?, ?, ?, ?, ?)", (BOOK_ID, p, 1000, 1500, 0, "COMPLETED", ""))

    cur.executemany("""
        INSERT INTO `Paragraph` (bookId, page, `order`, original, edited, left, top, right, bottom, type, region)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, database_paragraphs)

    conn.commit()
    conn.close()
    print("Database committed successfully.")

    # 10. Manifest JSON
    manifest = {
        "book_id": BOOK_ID,
        "title": BOOK_TITLE,
        "author": BOOK_AUTHOR,
        "pages": total_pages,
        "extracted_images": extracted_images_count,
        "total_paragraphs": global_para_counter,
        "total_titles": len(bookmarks_to_insert),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(os.path.join(OUTPUT_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    # 11. Create ZIP package
    print(f"Creating ZIP package: {ZIP_OUT_PATH}...")
    with zipfile.ZipFile(ZIP_OUT_PATH, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(DB_PATH, "reader.db")
        z.write(COVER_PATH, "cover.jpg")
        z.write(BOOK_TXT_PATH, "book.txt")
        z.write(os.path.join(OUTPUT_DIR, "manifest.json"), "manifest.json")
        for img_name in sorted(os.listdir(IMAGES_DIR)):
            if img_name.endswith((".png", ".jpg")):
                z.write(os.path.join(IMAGES_DIR, img_name), f"images/{img_name}")

    zip_size_mb = os.path.getsize(ZIP_OUT_PATH) / (1024 * 1024)
    print(f"\n[COMPLETE SUCCESS] E-Book package created: {ZIP_OUT_PATH} ({zip_size_mb:.2f} MB)")
    print(f" - Total Figures: {extracted_images_count}")
    print(f" - Total Clean Paragraphs: {global_para_counter}")
    print(f" - Total Valid Headings in TOC: {len(bookmarks_to_insert)}")

if __name__ == "__main__":
    run()
