"""
PDF to e-Book Studio (Windows GUI)
PDF 문서를 고화질 도표/이미지와 보정된 텍스트가 결합된 전용 e-Book 파일로 변환하는 독립 제작 도구
"""

import os
import sys
import time
import json
import re
import shutil
import zipfile
import hashlib
import sqlite3
import threading
import uuid
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont

from llm_corrector import (
    check_112_server,
    correct_text_with_llm,
    correct_page_body_elements,
    get_llm_cache_path,
    load_llm_cache,
    save_llm_cache
)
from ocr_engine import (
    is_scanned_pdf,
    get_cache_path,
    load_cache,
    save_cache,
    get_ocr_reader,
    get_page_blocks,
    is_caption_text,
    crop_diagram_highres
)

# Global Configurations & Defaults
DEFAULT_BOOK_ID = "c0000000-0000-0000-0000-000000000001"
BOOK_ID = DEFAULT_BOOK_ID
DEFAULT_PDF = r"C:\Users\lmo03\Downloads\book_cropped.pdf"
DEFAULT_TITLE = "한 권으로 끝내는 실전 LLM 파인튜닝"
DEFAULT_AUTHOR = "강다솔 (위키북스)"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)

def sanitize_folder_name(name):
    # Remove characters forbidden in Windows directories: \ / : * ? " < > |
    s = re.sub(r'[\\/*?:"<>|]', '_', name).strip()
    return s if s else "Untitled_Book"

def make_styled_cover(output_path, title, author):
    width, height = 400, 600
    img = Image.new("RGB", (width, height), color="#1E293B")
    draw = ImageDraw.Draw(img)
    for y in range(height):
        ratio = y / height
        r = int(0x1E * (1 - ratio) + 0x0F * ratio)
        g = int(0x29 * (1 - ratio) + 0x17 * ratio)
        b = int(0x3B * (1 - ratio) + 0x2A * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    draw.rectangle([16, 16, width - 16, height - 16], outline="#334155", width=2)
    font_path = "C:/Windows/Fonts/malgunbd.ttf"
    if not os.path.exists(font_path):
        font_path = "C:/Windows/Fonts/malgun.ttf"
    if os.path.exists(font_path):
        b_font = ImageFont.truetype(font_path, 16)
        t_font = ImageFont.truetype(font_path, 22)
        a_font = ImageFont.truetype(font_path, 15)
    else:
        b_font = t_font = a_font = ImageFont.load_default()
    draw.text((width // 2, 70), "[ Illustrated e-Book ]", fill="#38BDF8", font=b_font, anchor="mm")
    
    # Title splitting if long
    if len(title) > 16:
        draw.text((width // 2, 215), title[:16], fill="#FFFFFF", font=t_font, anchor="mm")
        draw.text((width // 2, 255), title[16:], fill="#60A5FA", font=t_font, anchor="mm")
    else:
        draw.text((width // 2, 235), title, fill="#FFFFFF", font=t_font, anchor="mm")
        
    draw.text((width // 2, 335), "(고화질 도표/삽화 수록 전자책)", fill="#94A3B8", font=b_font, anchor="mm")
    draw.text((width // 2, 510), f"저자: {author}", fill="#CBD5E1", font=a_font, anchor="mm")
    img.save(output_path, "JPEG", quality=92)

# OCR Typo Replacements
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

    # Regular endings and josa
    (r"\b([가-힣]+)올\b(?=\s|$)", r"\1을"),
    (r"\b([가-힣]+)울\b(?=\s|$)", r"\1을"),
    (r"\b([가-힣]+)름\b(?=\s|$)", r"\1를"),
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
]

def fix_typos(text):
    for pattern, replacement in TYPO_REPLACEMENTS:
        if callable(replacement):
            text = re.sub(pattern, replacement, text)
        else:
            text = re.sub(pattern, replacement, text)
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)
    text = re.sub(r"([(\[{<])\s+", r"\1", text)
    text = re.sub(r"\s+([)\]}>])", r"\1", text)
    text = re.sub(r"(\d+)\s*\.\s*(\d+)", r"\1.\2", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()

is_true_caption = is_caption_text

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class EbookStudioApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("PDF to e-Book Studio — 전자책 제작 변환 도구")
        self.geometry("820x680")
        self.minsize(750, 600)

        self.is_processing = False
        self.last_output_dir = None

        self.build_ui()

    def build_ui(self):
        # 1. Header Frame
        header_frame = ctk.CTkFrame(self, corner_radius=10, fg_color=("#2b2b2b", "#1e1e1e"))
        header_frame.pack(fill="x", padx=16, pady=(16, 8))

        title_lbl = ctk.CTkLabel(
            header_frame,
            text="📖 PDF to e-Book Studio",
            font=ctk.CTkFont(family="Malgun Gothic", size=20, weight="bold"),
            text_color="#4da6ff"
        )
        title_lbl.pack(anchor="w", padx=16, pady=(12, 2))

        desc_lbl = ctk.CTkLabel(
            header_frame,
            text="PDF 문서를 분석하여 원본 도표/이미지는 고화질로 추출하고, 글씨는 오탈자가 교정된 깔끔한 전자책 파일로 변환합니다.",
            font=ctk.CTkFont(family="Malgun Gothic", size=12),
            text_color="#aaaaaa"
        )
        desc_lbl.pack(anchor="w", padx=16, pady=(0, 12))

        # 2. Input Settings Card
        card_frame = ctk.CTkFrame(self, corner_radius=10)
        card_frame.pack(fill="x", padx=16, pady=6)

        # PDF File Selector
        pdf_row = ctk.CTkFrame(card_frame, fg_color="transparent")
        pdf_row.pack(fill="x", padx=16, pady=(14, 8))

        ctk.CTkLabel(pdf_row, text="PDF 파일:", width=80, anchor="w", font=ctk.CTkFont(family="Malgun Gothic", size=13, weight="bold")).pack(side="left")
        
        default_pdf_path = DEFAULT_PDF if os.path.exists(DEFAULT_PDF) else ""
        self.pdf_entry = ctk.CTkEntry(pdf_row, placeholder_text="변환할 PDF 파일을 선택하세요...")
        self.pdf_entry.insert(0, default_pdf_path)
        self.pdf_entry.pack(side="left", fill="x", expand=True, padx=(8, 8))

        browse_btn = ctk.CTkButton(pdf_row, text="찾아보기...", width=90, command=self.browse_pdf)
        browse_btn.pack(side="right")

        # Book Title & Author
        meta_row = ctk.CTkFrame(card_frame, fg_color="transparent")
        meta_row.pack(fill="x", padx=16, pady=4)

        ctk.CTkLabel(meta_row, text="도서 제목:", width=80, anchor="w", font=ctk.CTkFont(family="Malgun Gothic", size=13)).pack(side="left")
        self.title_entry = ctk.CTkEntry(meta_row, placeholder_text="도서 제목")
        self.title_entry.insert(0, DEFAULT_TITLE)
        self.title_entry.pack(side="left", fill="x", expand=True, padx=(8, 16))

        ctk.CTkLabel(meta_row, text="저자:", width=50, anchor="w", font=ctk.CTkFont(family="Malgun Gothic", size=13)).pack(side="left")
        self.author_entry = ctk.CTkEntry(meta_row, width=170, placeholder_text="저자 / 출판사")
        self.author_entry.insert(0, DEFAULT_AUTHOR)
        self.author_entry.pack(side="left")

        # Conversion Options
        opt_frame = ctk.CTkFrame(card_frame, fg_color="transparent")
        opt_frame.pack(fill="x", padx=16, pady=(10, 14))

        self.opt_crop_images = ctk.CTkCheckBox(opt_frame, text="도표/다이어그램 고화질(200 DPI) 자동 크롭 및 본문 인라인 삽입", font=ctk.CTkFont(family="Malgun Gothic", size=12))
        self.opt_crop_images.select()
        self.opt_crop_images.pack(anchor="w", pady=3)

        self.opt_fix_typos = ctk.CTkCheckBox(opt_frame, text="사전 기반 한글 OCR 오탈자 자동 교정 ('모텔'→'모델', '저리'→'처리' 등 300+ 단어)", font=ctk.CTkFont(family="Malgun Gothic", size=12))
        self.opt_fix_typos.select()
        self.opt_fix_typos.pack(anchor="w", pady=3)

        self.opt_filter_diagram_text = ctk.CTkCheckBox(opt_frame, text="도표 내부의 OCR 노이즈 글자 자동 제거 (도표는 이미지로만 보존)", font=ctk.CTkFont(family="Malgun Gothic", size=12))
        self.opt_filter_diagram_text.select()
        self.opt_filter_diagram_text.pack(anchor="w", pady=3)

        # 112 Gemma Server LLM Option
        llm_row = ctk.CTkFrame(opt_frame, fg_color="transparent")
        llm_row.pack(fill="x", pady=3)

        self.opt_use_llm = ctk.CTkCheckBox(
            llm_row,
            text="로컬 RTX 5080 Gemma 4 12B AI 문맥 오탈자 정밀 교정 (127.0.0.1:8092)",
            font=ctk.CTkFont(family="Malgun Gothic", size=12)
        )
        self.opt_use_llm.select()
        self.opt_use_llm.pack(side="left")

        self.test_llm_btn = ctk.CTkButton(
            llm_row,
            text="⚡ 통신 테스트",
            width=90,
            height=24,
            font=ctk.CTkFont(family="Malgun Gothic", size=11),
            fg_color="#334155",
            hover_color="#475569",
            command=self.test_llm_connection
        )
        self.test_llm_btn.pack(side="left", padx=(10, 0))

        self.opt_reset_llm_cache = ctk.CTkCheckBox(
            opt_frame,
            text="기존 LLM 캐시 초기화 (로컬 12B로 깨끗하게 새로 전수 재검수)",
            font=ctk.CTkFont(family="Malgun Gothic", size=12)
        )
        self.opt_reset_llm_cache.pack(anchor="w", pady=3)

        # 3. Action Buttons
        btn_card = ctk.CTkFrame(self, corner_radius=10)
        btn_card.pack(fill="x", padx=16, pady=6)

        btn_row = ctk.CTkFrame(btn_card, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=10)

        self.start_btn = ctk.CTkButton(
            btn_row,
            text="🚀 e-Book 변환 시작",
            font=ctk.CTkFont(family="Malgun Gothic", size=14, weight="bold"),
            height=42,
            fg_color="#1f77b4",
            hover_color="#145b8e",
            command=self.start_conversion
        )
        self.start_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.open_folder_btn = ctk.CTkButton(
            btn_row,
            text="📁 결과 폴더 열기",
            font=ctk.CTkFont(family="Malgun Gothic", size=13),
            height=42,
            width=130,
            fg_color="#4f5b66",
            hover_color="#3b444c",
            command=self.open_output_folder
        )
        self.open_folder_btn.pack(side="right")

        # 4. Progress and Log Frame
        log_frame = ctk.CTkFrame(self, corner_radius=10)
        log_frame.pack(fill="both", expand=True, padx=16, pady=(6, 16))

        # Progress Bar & Status Text
        prog_header = ctk.CTkFrame(log_frame, fg_color="transparent")
        prog_header.pack(fill="x", padx=16, pady=(12, 4))

        self.status_lbl = ctk.CTkLabel(prog_header, text="대기 중", font=ctk.CTkFont(family="Malgun Gothic", size=12, weight="bold"))
        self.status_lbl.pack(side="left")

        self.percent_lbl = ctk.CTkLabel(prog_header, text="0%", font=ctk.CTkFont(family="Malgun Gothic", size=12))
        self.percent_lbl.pack(side="right")

        self.progress_bar = ctk.CTkProgressBar(log_frame)
        self.progress_bar.pack(fill="x", padx=16, pady=(0, 10))
        self.progress_bar.set(0.0)

        # Log Text Box
        self.log_box = ctk.CTkTextbox(
            log_frame,
            font=ctk.CTkFont(family="Consolas", size=12),
            wrap="word",
            fg_color=("#1a1a1a", "#121212"),
            text_color="#00ff66"
        )
        self.log_box.pack(fill="both", expand=True, padx=16, pady=(0, 14))

        self.log("[System] PDF to e-Book Studio가 준비되었습니다.")
        self.log("[System] PDF 파일을 선택하고 'e-Book 변환 시작'을 누르면 전용 전자책 패키지가 생성됩니다.\n")

    def browse_pdf(self):
        filename = filedialog.askopenfilename(
            title="변환할 PDF 파일 선택",
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")]
        )
        if filename:
            self.pdf_entry.delete(0, tk.END)
            self.pdf_entry.insert(0, filename)

    def log(self, message):
        def _append():
            self.log_box.insert(tk.END, message + "\n")
            self.log_box.see(tk.END)
        self.after(0, _append)

    def update_progress(self, current, total, text=None):
        def _update():
            fraction = min(max(current / max(total, 1), 0.0), 1.0)
            self.progress_bar.set(fraction)
            self.percent_lbl.configure(text=f"{int(fraction * 100)}%")
            if text:
                self.status_lbl.configure(text=text)
        self.after(0, _update)

    def open_output_folder(self):
        target = self.last_output_dir if (self.last_output_dir and os.path.exists(self.last_output_dir)) else BASE_OUTPUT_DIR
        try:
            os.startfile(target)
        except Exception as e:
            messagebox.showerror("오류", f"폴더를 열 수 없습니다: {e}")

    def test_llm_connection(self):
        self.log("[LLM] 로컬 AI 서버 (http://127.0.0.1:8092) 통신 테스트 중...")
        ok, res = check_112_server()
        if ok:
            models, url_target = res
            model_str = ", ".join(models) if isinstance(models, list) else str(models)
            self.log(f"[LLM] AI 서버 연결 성공! (주소: {url_target}, 모델: {model_str})")
            messagebox.showinfo("통신 성공", f"Gemma 4 AI 서버와 정상 연결되었습니다!\n\n• 모델: {model_str}\n• 주소: {url_target}")
        else:
            self.log(f"[LLM] AI 서버 연결 실패: {res}")
            messagebox.showerror("통신 실패", f"AI 서버에 연결할 수 없습니다:\n{res}\n\n로컬 llama-server(8092) 또는 112 서버가 켜져있는지 확인하세요.")

    def set_busy(self, busy):
        self.is_processing = busy
        state = "disabled" if busy else "normal"
        self.after(0, lambda: self.start_btn.configure(state=state))

    def start_conversion(self):
        if self.is_processing:
            return
        pdf_path = self.pdf_entry.get().strip()
        if not pdf_path or not os.path.exists(pdf_path):
            messagebox.showerror("파일 오류", "올바른 PDF 파일 경로를 입력해 주세요.")
            return

        book_title = self.title_entry.get().strip() or DEFAULT_TITLE
        book_author = self.author_entry.get().strip() or DEFAULT_AUTHOR
        do_crop = bool(self.opt_crop_images.get())
        do_fix_typos = bool(self.opt_fix_typos.get())
        filter_diagram_text = bool(self.opt_filter_diagram_text.get())
        use_llm = bool(self.opt_use_llm.get())

        reset_llm_cache = bool(self.opt_reset_llm_cache.get())

        self.set_busy(True)
        thread = threading.Thread(
            target=self._run_conversion,
            args=(pdf_path, book_title, book_author, do_crop, do_fix_typos, filter_diagram_text, use_llm, reset_llm_cache),
            daemon=True
        )
        thread.start()

    def _run_conversion(self, pdf_path, book_title, book_author, do_crop, do_fix_typos, filter_diagram_text, use_llm, reset_llm_cache=False):
        try:

            # Create book-specific output directory
            book_folder_name = sanitize_folder_name(book_title)
            book_dir = os.path.join(BASE_OUTPUT_DIR, book_folder_name)
            images_dir = os.path.join(book_dir, "images")
            os.makedirs(images_dir, exist_ok=True)
            self.last_output_dir = book_dir

            # Unique Book ID
            if book_title == DEFAULT_TITLE:
                book_id = DEFAULT_BOOK_ID
            else:
                book_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{book_title}_{book_author}"))

            self.log("=" * 60)
            self.log(f"[변환 시작] 파일: {pdf_path}")
            self.log(f"도서명: {book_title} / 저자: {book_author}")
            self.log(f"결과 폴더: {book_dir}")
            self.log("=" * 60)

            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            self.log(f"총 {total_pages} 페이지 PDF 로딩 완료.")

            # Detect if scanned PDF (no digital text layer)
            is_scanned = is_scanned_pdf(doc)
            ocr_cache = None
            ocr_reader = None
            cache_path = None

            if is_scanned:
                self.log("\n[스캔본 감지] 디지털 텍스트가 없는 스캔본(이미지) PDF가 감지되었습니다.")
                cache_path = get_cache_path(pdf_path)
                ocr_cache = load_cache(cache_path)
                cached_count = len(ocr_cache)
                if cached_count >= total_pages:
                    self.log(f"[캐시 로드] 전체 {cached_count}페이지의 GPU OCR 캐시를 성공적으로 로드했습니다.")
                elif cached_count > 0:
                    self.log(f"[캐시 로드] 이전 분석 캐시({cached_count}/{total_pages}p) 확인. 잔여 페이지 GPU OCR을 재개합니다.")
                    self.log("[GPU OCR] NVIDIA RTX (EasyOCR ko+en) 가속 엔진 초기화 중...")
                    ocr_reader = get_ocr_reader(gpu=True)
                else:
                    self.log("[GPU OCR] NVIDIA RTX 5080 가속 (EasyOCR ko+en) 엔진을 가동합니다...")
                    self.update_progress(0, total_pages, "NVIDIA GPU OCR 엔진 가동 중...")
                    ocr_reader = get_ocr_reader(gpu=True)
                    self.log("[GPU OCR] 엔진 초기화 완료! RTX 5080 하드웨어 가속 추론을 시작합니다.")

            # Setup Local RTX 5080 Gemma LLM Cache
            llm_cache = None
            llm_cache_path = None
            if use_llm:
                llm_cache_path = get_llm_cache_path(pdf_path)
                if reset_llm_cache and os.path.exists(llm_cache_path):
                    try:
                        os.remove(llm_cache_path)
                        self.log("[LLM 초기화] 기존 LLM 캐시를 삭제하고 깨끗한 상태로 시작합니다.")
                    except Exception:
                        pass
                llm_cache = load_llm_cache(llm_cache_path) if not reset_llm_cache else {}
                cached_llm_count = len(llm_cache)
                if cached_llm_count > 0:
                    self.log(f"[LLM 캐시 로드] 유효 캐시 {cached_llm_count}페이지 확인 (미검수 페이지만 로컬 12B 실시간 추론)")
                else:
                    self.log("[LLM 실시간 검수] 로컬 RTX 5080 Gemma 4 12B (127.0.0.1:8092) 정밀 문맥 교정을 가동합니다.")

            extracted_images_count = 0
            all_clean_paragraphs = []
            database_paragraphs = []
            global_para_counter = 0

            self.update_progress(0, total_pages, "페이지 분석 및 도표 추출 중...")

            for p_num in range(total_pages):
                page = doc[p_num]
                page_idx = p_num + 1

                # Extract blocks using ocr_engine
                blocks, was_scanned = get_page_blocks(doc, p_num, ocr_cache, ocr_reader, dpi=135)
                if was_scanned and ocr_reader is not None and (page_idx % 10 == 0 or page_idx == total_pages):
                    save_cache(cache_path, ocr_cache)

                content_blocks = []
                p_h = page.rect.height
                p_w = page.rect.width
                for b in blocks:
                    bx0, by0, bx1, by1, btext = b[0], b[1], b[2], b[3], b[4].strip()
                    if not btext:
                        continue
                    # Exclude top headers and bottom footers
                    if by1 < p_h * 0.08 or by0 > p_h * 0.93:
                        if len(btext) < 35 and any(char.isdigit() for char in btext):
                            continue
                        if any(kw in btext for kw in ['한 권으로', '한권으로', '위키북스', 'WIKIBOOKS']) or re.search(r'PART\s*0?\d', btext, re.IGNORECASE):
                            continue
                    content_blocks.append(b)

                captions = []
                if do_crop:
                    for b in content_blocks:
                        btext = b[4].strip()
                        if is_caption_text(btext):
                            captions.append(b)

                crop_rects = []
                if do_crop and captions:
                    for cap in captions:
                        cx0, cy0, cx1, cy1, ctext = cap[0], cap[1], cap[2], cap[3], cap[4].strip()
                        # Find diagram top boundary: look up for preceding text
                        prev_bottom = int(p_h * 0.08)
                        for pb in content_blocks:
                            if pb[3] < cy0 - 20:
                                if (pb[2] - pb[0] > p_w * 0.4) or len(pb[4]) > 25:
                                    if pb[3] > prev_bottom:
                                        prev_bottom = pb[3]

                        top_y = max(0, prev_bottom + 5)
                        bottom_y = min(p_h, cy1 + 8)

                        if (bottom_y - top_y) > 35:
                            crop_box = fitz.Rect(
                                max(0, p_w * 0.04),
                                top_y,
                                min(p_w * 0.96, p_w),
                                bottom_y
                            )
                            crop_rects.append((crop_box, ctext, top_y, bottom_y))

                page_elements = []
                for crop_box, ctext, min_y, cy1 in crop_rects:
                    extracted_images_count += 1
                    img_filename = f"fig_{extracted_images_count:04d}_p{page_idx}.png"
                    img_filepath = os.path.join(images_dir, img_filename)
                    crop_diagram_highres(page, crop_box, img_filepath, dpi=200)

                    clean_cap = re.sub(r'^[▲▼\s]+', '', ctext).strip()
                    page_elements.append({
                        "type": "IMAGE",
                        "y": min_y,
                        "bottom_y": cy1,
                        "filename": img_filename,
                        "caption": clean_cap,
                        "raw_text": f"![{clean_cap}](images/{img_filename})"
                    })

                is_toc_or_index_page = (page_idx <= 17 or page_idx >= 335)

                # Pre-scan headings: Smart Heading Stitching for section numbers + titles
                heading_stitched_indices = set()
                precomputed_headings = {}  # index -> (by0, by1, combined_title)

                if not is_toc_or_index_page:
                    for i in range(len(content_blocks)):
                        if i in heading_stitched_indices:
                            continue
                        b = content_blocks[i]
                        btext = b[4].strip()
                        # Check pure section number like "1.1", "1.2", "1.3.1", "CHAPTER 1", "PART 1" (max 2 digits per segment)
                        num_match = re.match(r'^(제\s*[1-9]\d?\s*[장절편부]|CHAPTER\s+[1-9]\d?|PART\s+[1-9]\d?|[1-9]\d?\.[1-9]\d?(\.[1-9]\d?)?)$', btext, re.IGNORECASE)
                        if num_match:
                            combined = btext
                            min_y0, max_y1 = b[1], b[3]
                            # Look at adjacent blocks (next or prev within 45px vertically)
                            for cand_idx in [i + 1, i - 1]:
                                if 0 <= cand_idx < len(content_blocks) and cand_idx not in heading_stitched_indices:
                                    cand = content_blocks[cand_idx]
                                    ctext = cand[4].strip()
                                    v_dist = min(abs(cand[1] - b[3]), abs(b[1] - cand[3]))
                                    if v_dist < 45 and len(ctext) < 40 and not ctext.endswith(('.', '다', '요', '음', '임', '다.', '요.')):
                                        if re.search(r'[가-힣]', ctext) and not re.match(r'^(제?\s*\d|CHAPTER|PART|\d+\.|\d+\s*[\$\%])', ctext, re.IGNORECASE):
                                            combined = f"{btext} {ctext}"
                                            min_y0 = min(b[1], cand[1])
                                            max_y1 = max(b[3], cand[3])
                                            heading_stitched_indices.add(cand_idx)
                                            break
                            # Only accept if it combined with a real title, or if it's explicitly CHAPTER/PART
                            is_valid_heading = (combined != btext) or bool(re.match(r'^(제\s*\d|CHAPTER|PART|부록)', btext, re.IGNORECASE))
                            if is_valid_heading:
                                precomputed_headings[i] = (min_y0, max_y1, combined)
                                heading_stitched_indices.add(i)

                # Smart Paragraph Stitching: OCR로 분절된 줄들을 자연스러운 한글 문단으로 결합
                stitched_blocks = []
                cur_text_list = []
                cur_y0 = 0
                cur_y1 = 0

                for idx, b in enumerate(content_blocks):
                    if idx in precomputed_headings:
                        if cur_text_list:
                            stitched_text = " ".join(cur_text_list)
                            stitched_text = re.sub(r'([가-힣])\s+([은는이가을를의에로와과도]|(에서))\b', r'\1\2', stitched_text)
                            stitched_blocks.append(("BODY", cur_y0, cur_y1, stitched_text))
                            cur_text_list = []
                        hy0, hy1, htext = precomputed_headings[idx]
                        stitched_blocks.append(("TITLE", hy0, hy1, htext))
                        continue

                    if idx in heading_stitched_indices:
                        continue

                    bx0, by0, bx1, by1, btext = b[0], b[1], b[2], b[3], b[4].strip()
                    if not btext:
                        continue

                    # Skip diagram internal text
                    if filter_diagram_text and crop_rects:
                        is_inside_diagram = False
                        for _, _, d_top, d_bottom in crop_rects:
                            if d_top - 5 <= by0 and by1 <= d_bottom + 5:
                                is_inside_diagram = True
                                break
                        if is_inside_diagram:
                            continue

                    # Check if Title / Section Heading (Number + Title on the same line)
                    is_title = False
                    if not is_toc_or_index_page:
                        if len(btext) < 55 and not btext.endswith(('.', '다', '요', '음', '임', '다.', '요.', ':', ';', '!', '?')):
                            if re.match(r'^(제\s*[1-9]\d?\s*[장절편부]|CHAPTER\s+[1-9]\d?|PART\s+[1-9]\d?|[1-9]\d?\.[1-9]\d?(\.[1-9]\d?)?\s+[가-힣]|부록\s*[A-Z0-9])', btext):
                                is_title = True
                            elif re.match(r'^[1-9]\d?\s+[가-힣]{2,}', btext) and len(btext) < 30:
                                is_title = True

                    # Check if Code
                    is_code = ('import ' in btext or 'def ' in btext or 'class ' in btext or 'print(' in btext)

                    if is_title or is_code:
                        if cur_text_list:
                            stitched_text = " ".join(cur_text_list)
                            stitched_text = re.sub(r'([가-힣])\s+([은는이가을를의에로와과도]|(에서))\b', r'\1\2', stitched_text)
                            stitched_blocks.append(("BODY", cur_y0, cur_y1, stitched_text))
                            cur_text_list = []
                        stitched_blocks.append(("TITLE" if is_title else "CODE", by0, by1, btext))
                        continue

                    # Regular body text line
                    if not cur_text_list:
                        cur_text_list.append(btext)
                        cur_y0 = by0
                        cur_y1 = by1
                    else:
                        prev_ends = bool(re.search(r'[.?!:;”"’\)]\s*$', cur_text_list[-1]))
                        next_cont = bool(re.match(r'^(?:니다|습니|입니|였다|했다|있었다|으로|에서|로서|에게|과|와)\b', btext))
                        if not prev_ends or next_cont:
                            if re.search(r'[가-힣]+[습합]$', cur_text_list[-1]) and re.match(r'^니다\b', btext):
                                cur_text_list[-1] += btext
                            elif re.search(r'[가-힣]$', cur_text_list[-1]) and re.match(r'^[게고서로며면은는이가을를의에]\b', btext):
                                cur_text_list[-1] += btext
                            else:
                                cur_text_list.append(btext)
                            cur_y1 = max(cur_y1, by1)
                        else:
                            stitched_text = " ".join(cur_text_list)
                            stitched_text = re.sub(r'([가-힣])\s+([은는이가을를의에로와과도]|(에서))\b', r'\1\2', stitched_text)
                            stitched_blocks.append(("BODY", cur_y0, cur_y1, stitched_text))
                            cur_text_list = [btext]
                            cur_y0 = by0
                            cur_y1 = by1

                if cur_text_list:
                    stitched_text = " ".join(cur_text_list)
                    stitched_text = re.sub(r'([가-힣])\s+([은는이가을를의에로와과도]|(에서))\b', r'\1\2', stitched_text)
                    stitched_blocks.append(("BODY", cur_y0, cur_y1, stitched_text))

                for p_type, by0, by1, btext in stitched_blocks:
                    if do_fix_typos:
                        btext = fix_typos(btext)

                    page_elements.append({
                        "type": p_type,
                        "y": by0,
                        "bottom_y": by1,
                        "text": btext
                    })


                # Local RTX 5080 Gemma LLM high-speed page-batch contextual correction
                if use_llm:
                    page_elements = correct_page_body_elements(page_idx, page_elements, llm_cache, log_fn=self.log)
                    if (page_idx % 5 == 0 or page_idx == total_pages) and llm_cache_path:
                        save_llm_cache(llm_cache_path, llm_cache)

                page_elements.sort(key=lambda e: e["y"])


                for el in page_elements:
                    global_para_counter += 1
                    if el["type"] == "IMAGE":
                        all_clean_paragraphs.append(el["raw_text"])
                        database_paragraphs.append((
                            book_id, page_idx, global_para_counter,
                            el["raw_text"], el["raw_text"],
                            100, int(el["y"]), 900, int(el["bottom_y"]),
                            "IMAGE", "CONTENT"
                        ))
                    elif el["type"] == "TITLE":
                        all_clean_paragraphs.append(f"\n## {el['text']}\n")
                        database_paragraphs.append((
                            book_id, page_idx, global_para_counter,
                            el["text"], el["text"],
                            100, int(el["y"]), 900, int(el["bottom_y"]),
                            "TITLE", "CONTENT"
                        ))
                    elif el["type"] == "CODE":
                        all_clean_paragraphs.append(f"\n```python\n{el['text']}\n```\n")
                        database_paragraphs.append((
                            book_id, page_idx, global_para_counter,
                            el["text"], el["text"],
                            100, int(el["y"]), 900, int(el["bottom_y"]),
                            "CODE", "CONTENT"
                        ))
                    else:
                        all_clean_paragraphs.append(el["text"])
                        database_paragraphs.append((
                            book_id, page_idx, global_para_counter,
                            el["text"], el["text"],
                            100, int(el["y"]), 900, int(el["bottom_y"]),
                            "BODY", "CONTENT"
                        ))

                if (page_idx % 10 == 0) or page_idx == total_pages:
                    status_extra = " (LLM 교정 중)" if use_llm else ""
                    self.update_progress(
                        page_idx, total_pages,
                        f"변환 중: {page_idx}/{total_pages}p (도표 {extracted_images_count}개 추출{status_extra})"
                    )
                    self.log(f"  [진행] {page_idx}/{total_pages} 페이지 완료 (누적 도표: {extracted_images_count}개{status_extra})")

            doc.close()
            if is_scanned and ocr_cache and cache_path:
                save_cache(cache_path, ocr_cache)
            if use_llm and llm_cache and llm_cache_path:
                save_llm_cache(llm_cache_path, llm_cache)

            # Save Markdown TXT
            self.update_progress(total_pages, total_pages, "e-Book 데이터베이스 및 패키지 파일 생성 중...")
            self.log("\n[저장] 텍스트 및 SQLite 데이터베이스 생성 중...")
            
            final_book_text = "\n\n".join(all_clean_paragraphs)
            txt_path = os.path.join(book_dir, f"{book_id}.txt")
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(final_book_text)

            # Generate Cover Image if needed
            cover_path = os.path.join(book_dir, f"{book_id}.jpg")
            if not os.path.exists(cover_path):
                make_styled_cover(cover_path, book_title, book_author)

            # Build Live SQLite Database (Exact Room Schema)
            live_db_path = os.path.join(book_dir, "reader.db")
            if os.path.exists(live_db_path):
                os.remove(live_db_path)

            conn = sqlite3.connect(live_db_path)
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
            file_bytes = final_book_text.encode('utf-8')
            file_hash = hashlib.sha256(file_bytes).hexdigest()

            cur.execute("""
                INSERT INTO `Book` VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                book_id, book_title,
                f"file:///data/user/0/com.ebook.ocrreader/files/{book_id}.txt",
                f"{book_id}.txt",
                len(file_bytes), file_hash, total_pages,
                now_ms, now_ms + 100000, "READY", total_pages,
                book_author, f"고화질 도표 {extracted_images_count}개 수록 하이브리드 전자책", ""
            ))

            for p in range(1, total_pages + 1):
                cur.execute("INSERT INTO `Page` VALUES (?, ?, ?, ?, ?, ?, ?)", (book_id, p, 1000, 1500, 0, "COMPLETED", ""))

            cur.executemany("""
                INSERT INTO `Paragraph` (bookId, page, `order`, original, edited, left, top, right, bottom, type, region)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, database_paragraphs)

            conn.commit()
            conn.close()

            # Create Standalone ZIP Package
            manifest = {
                "id": book_id,
                "title": book_title,
                "author": book_author,
                "pages": total_pages,
                "figuresCount": extracted_images_count,
                "paragraphsCount": len(database_paragraphs),
                "buildTime": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            manifest_path = os.path.join(book_dir, "manifest.json")
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)

            zip_filename = f"{book_folder_name}.zip"
            zip_path = os.path.join(book_dir, zip_filename)
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
                z.write(manifest_path, "manifest.json")
                z.write(txt_path, "book.txt")
                z.write(cover_path, "cover.jpg")
                z.write(live_db_path, "reader.db")
                for img_name in os.listdir(images_dir):
                    if img_name.endswith(('.png', '.jpg')):
                        z.write(os.path.join(images_dir, img_name), f"images/{img_name}")

            zip_mb = os.path.getsize(zip_path) / (1024 * 1024)
            self.update_progress(total_pages, total_pages, "e-Book 제작 완료!")
            self.log(f"\n[성공] 전자책 패키지 파일 생성 완료: {zip_filename} ({zip_mb:.2f} MB)")
            self.log(f"• 고화질 도표 추출: {extracted_images_count}개")
            self.log(f"• 전체 텍스트 문단: {len(database_paragraphs):,}개")
            self.log(f"• 도서 전용 폴더: {book_dir}\n")

            self.after(0, lambda: messagebox.showinfo(
                "e-Book 제작 완료",
                f"전자책 패키지가 성공적으로 완성되었습니다!\n\n"
                f"• 도서명: {book_title}\n"
                f"• 패키지: {zip_filename} ({zip_mb:.2f} MB)\n"
                f"• 추출된 도표: {extracted_images_count}개\n"
                f"• 총 문단: {len(database_paragraphs):,}개\n\n"
                f"'결과 폴더 열기' 버튼을 누르면 해당 도서 폴더가 열립니다."
            ))

        except Exception as e:
            import traceback
            err = traceback.format_exc()
            self.log(f"\n[오류 발생] {e}\n{err}")
            self.update_progress(0, 1, "오류로 중단됨")
            self.after(0, lambda: messagebox.showerror("변환 오류", f"변환 중 오류가 발생했습니다:\n{e}"))
        finally:
            self.set_busy(False)

def main():
    app = EbookStudioApp()
    app.mainloop()

if __name__ == "__main__":
    main()
