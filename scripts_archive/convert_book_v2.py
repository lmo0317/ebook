import sqlite3
import re
import json
import os

DB_PATH = 'reader_device.db'
OUT_TXT_LOCAL = 'book_converted.txt'
OUT_TXT_USER = r'C:\Users\lmo03\Downloads\book_converted.txt'

# Comprehensive dictionary of OCR misrecognitions found across the 348 pages
TYPO_REPLACEMENTS = [
    # ㅈ / ㅊ confusions
    (r'\b마지\b', '마치'),
    (r'\b스위지\b', '스위치'),
    (r'\b거지면서\b', '거치면서'),
    (r'\b순자적\b', '순차적'),
    (r'\b순자\s+저리\b', '순차 처리'),
    (r'\b가중지\b', '가중치'),
    (r'\b필수\s*절자\b', '필수 절차'),
    (r'\b절자\b(?=\s*(?:입니다|를|가|로|에))', '절차'),
    (r'\b자이점\b', '차이점'),
    (r'\b자이점도\b', '차이점도'),
    (r'\b사소한\s+자이\b', '사소한 차이'),
    (r'\b큰\s+자이\b', '큰 차이'),
    (r'\b자이(?:가|를|로|에|의)\b', lambda m: '차이' + m.group(0)[2:]),
    (r'\b자원의\s*저주\b', '차원의 저주'),
    (r'\b자원\s*축소\b', '차원 축소'),
    (r'\b(\d+)\s*자원\b', r'\1차원'),
    (r'\b자원\s*크기\b', '차원 크기'),
    (r'\b원래\s*자원으로\b', '원래 차원으로'),
    (r'\b결과의\s*자원을\b', '결과의 차원을'),
    (r'\b마지막\s*자원을\b', '마지막 차원을'),
    
    # 처리 / 저리 confusions
    (r'\b전저리\b', '전처리'),
    (r'\b전저리된\b', '전처리된'),
    (r'\b전저리와\b', '전처리와'),
    (r'\b자연어\s*저리\b', '자연어 처리'),
    (r'\b병렬\s*저리\b', '병렬 처리'),
    (r'\b순차적\s*저리\b', '순차적 처리'),
    (r'\b데이터\s*저리\b', '데이터 처리'),
    (r'\b텐서\s*병렬\s*저리\b', '텐서 병렬 처리'),
    (r'\b언어\s*저리\b', '언어 처리'),
    (r'\b저리\s*속도\b', '처리 속도'),
    (r'\b저리\s*시간\b', '처리 시간'),
    (r'\b저리\s*능력\b', '처리 능력'),
    (r'\b저리\s*과정\b', '처리 과정'),
    (r'\b저리(할|하는|하고|해|된|될|되어|되지|하지|하면|하게|됨을|되기|됩니다|했습)\b', r'처리\1'),
    (r'\b저리를\b', '처리를'),
    (r'\b저리합니다\b', '처리합니다'),
    (r'\b저리하지\b', '처리하지'),

    # ML / Tech term OCR confusions
    (r'\b모\s*텔\b', '모델'),
    (r'\b모텔\b(?=\s*(?:을|를|이|가|의|에|은|는|로|과|와|에서|훈련|학습|평가|서빙|구현|준비|생성|파라미터|크기|구조|이름))', '모델'),
    (r'\b시권스\b', '시퀀스'),
    (r'\b임겟값\b', '임계값'),
    (r'\b파인[류뉴]님\b', '파인튜닝'),
    (r'\b파인[류뉴]닝\b', '파인튜닝'),
    (r'\b서방\b(?=\s*(?:최적화|기술|까지|방법|원리|구현))', '서빙'),
    (r'\b독사들\b', '독자들'),
    (r'\b맛춤화\b', '맞춤화'),
    (r'\b맛춤\b', '맞춤'),
    (r'\b어텐선\b', '어텐션'),
    (r'\b소포트맥스\b', '소프트맥스'),
    (r'\b조조지타운\b', '조지타운'),
    (r'\b조지타운-BM\b', '조지타운-IBM'),
    (r'\bMIrT\b', 'MIT'),
    (r'\b아는\s+튜링\b', '이는 튜링'),
    (r'\b잠조\b(?=\s*(?:자료|문헌|하기|하여|해|테이블))', '참조'),
    (r'\b응납\b', '응답'),
    (r'\b응납자\b', '응답자'),
    (r'\b응납에서\b', '응답에서'),
    (r'\b명화히\b', '명확히'),
    (r'\b능려을\b', '능력을'),
    (r'\b점근하기\b', '접근하기'),
    (r'\b학습시길\b', '학습시킬'),
    (r'\b다랑면에서\b', '다방면에서'),
    (r'\b위키숙스\b', '위키북스'),
    (r'\b저직권\b', '저작권'),
    (r'\b감들올\b', '값들을'),
    (r'\b동해\b(?=\s+[A-Za-z가-힣]+(?:을|를|에))', '통해'),
    (r'\b것입나니다\b', '것입니다'),
    (r'\b추전드럽니다\b', '추천드립니다'),
    (r'\b감사드럽니다\b', '감사드립니다'),

    # Brand & code acronyms
    (r'\bOpenAl\b', 'OpenAI'),
    (r'\bOpenA\b(?=\s+API)', 'OpenAI'),
    (r'\bGP-4\b', 'GPT-4'),
    (r'\bAl\b', 'AI'),
    (r'\bVLLM\b', 'vLLM'),
    (r'\bRunpod\b', 'RunPod'),
    (r'\bpqdm\b', 'tqdm'),
    (r'\biser\b(?=\s*라는)', 'user'),
    (r'\bWegh\b', 'Weights'),
    (r'\b_parse\s+eva\b', '_parse_eval'),
    (r'\boN_Sum\b', 'on_sum'),
    (r'\bAexa\b', 'Alexa'),

    # Broken verb endings
    (r'\b([가-힣]+)함\s*니다\b', r'\1합니다'),
    (r'\b([가-힣]+)습\s+니다\b', r'\1습니다'),
    (r'\b([가-힣]+)합\s+니다\b', r'\1합니다'),
    (r'\b([가-힣]+)였습\s+니다\b', r'\1였습니다'),
    (r'\b([가-힣]+)되었습\s+니다\b', r'\1되었습니다'),
    (r'\b([가-힣]+)겠습\s+니다\b', r'\1겠습니다'),
    (r'\b([가-힣]+)있습\s+니다\b', r'\1있습니다'),
    (r'\b고민해이야합\s*니다\b', '고민해야 합니다'),
]

def apply_typo_fixes(text: str) -> str:
    t = text
    for item in TYPO_REPLACEMENTS:
        pat = item[0]
        rep = item[1]
        if callable(rep):
            t = re.sub(pat, rep, t)
        else:
            t = re.sub(pat, rep, t)
    return t

def is_noise(text: str, top: int, bottom: int, page_height: int) -> bool:
    t = text.strip()
    if not t:
        return True
    # Barcodes
    if re.search(r'^(9[Ttr0-9]{8,}|[0-9a-zA-Z_\-]{14,})', t):
        return True
    if top > page_height * 0.88 and re.match(r'^[0-9a-zA-Z\s\-_]{10,}$', t):
        return True
    # Margin page numbers
    if re.match(r'^[0-9ivxIVX]{1,4}$', t) and (top < page_height * 0.08 or bottom > page_height * 0.92):
        return True
    # Running header noise: book title, chapter title at extreme margins
    if bottom < page_height * 0.07:
        if any(w in t for w in ['한 권으로', '한권으로', '파인튜닝', 'PART', 'NLP의 과거']):
            return True
        if len(t) < 40:
            return True
    # Running footer noise
    if top > page_height * 0.92:
        if any(w in t for w in ['위키북스', 'WIKIBOOKS']):
            return True
        if len(t) < 35:
            return True
    # Standalone punctuation noise
    if t in ['.', '-', '_', '~', ',', '`', '\'', '"', '|', '/', '\\', '·', ':']:
        return True
    return False

def clean_spacing(text: str) -> str:
    t = text
    # Fix spacing before punctuation
    t = re.sub(r'\s+([.,!?;:])', r'\1', t)
    # Fix brackets
    t = re.sub(r'([(\[{<])\s+', r'\1', t)
    t = re.sub(r'\s+([)\]}>])', r'\1', t)
    # Fix numbered section headers: "1 . 2 . 3" -> "1.2.3"
    t = re.sub(r'(\d+)\s*\.\s*(\d+)', r'\1.\2', t)
    # Fix broken particles inside phrases
    t = re.sub(r'\b(기술|정보|데이터|이론|실습|학습|모델|신경망|컴퓨터|인간|기계)\s+(의|에|을|를|이|가|은|는|와|과|로|으로)\b', r'\1\2', t)
    # Fix broken syllables across line breaks
    t = re.sub(r'([가-힣])\s*\n\s*([가-힣])', r'\1 \2', t)
    # Collapse multiple spaces
    t = re.sub(r'[ \t]+', ' ', t)
    return t.strip()

def is_code_line(line: str) -> bool:
    l = line.strip()
    if not l:
        return False
    # Python / code indicators
    code_starts = [
        'import ', 'from ', 'def ', 'class ', 'return ', 'if __name__',
        'self.', 'torch.', 'nn.', 'F.', 'np.', 'plt.', 'model =', 'loss =',
        'optimizer =', 'tokenizer =', 'print(', 'super().', 'pip install',
        'git clone', 'cd ', 'python ', 'export ', 'curl ', 'wget ',
        'docker run', 'runpod ', 'wandb.'
    ]
    if any(l.startswith(cs) for cs in code_starts):
        return True
    if re.match(r'^(for|while|if|elif|else|try|except|with|finally)\s+.*:$', l):
        return True
    if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*\s*=\s*.*', l) and len(l) < 80:
        return True
    if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*\(.*\)', l) and len(l) < 80:
        return True
    return False

def format_heading(text: str) -> str:
    t = text.strip()
    # Major chapter: "01장", "Chapter 1", "PART 1"
    if re.match(r'^(?:0?\d장|Chapter\s*\d|PART\s*\d)', t, re.IGNORECASE):
        return f"\n\n# {t}\n"
    # Section: "1.1", "2.3"
    if re.match(r'^\d+\.\d+\s+', t):
        return f"\n\n## {t}\n"
    # Sub-section: "1.1.1", "2.3.4"
    if re.match(r'^\d+\.\d+\.\d+\s+', t):
        return f"\n\n### {t}\n"
    # Callout: "TIP", "NOTE"
    if re.match(r'^(?:TIP|Tip|NOTE|Note)\s+', t):
        return f"\n\n> **{t}**\n"
    return t

def process_book():
    print("Opening reader_device.db...")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    book_info = c.execute('SELECT id, title, pages FROM Book LIMIT 1').fetchone()
    if not book_info:
        print("No book found!")
        return
    book_id, title, total_pages = book_info
    print(f"Processing book: '{title}' ({total_pages} pages)")

    pages_text = []

    # Title header
    pages_text.append(
        "# 한 권으로 끝내는 실전 LLM 파인튜닝\n\n"
        "**저자:** 강다솔 | **출판:** 위키북스\n"
        "**부제:** GPT 작동 원리부터 Gemma 2 / Llama 3 파인튜닝, vLLM 서빙까지\n\n"
        "---\n"
    )

    for p_num in range(1, total_pages + 1):
        p_row = c.execute('SELECT width, height FROM Page WHERE number=?', (p_num,)).fetchone()
        p_h = p_row[1] if p_row and p_row[1] > 0 else 2200

        blocks = c.execute(
            'SELECT left, top, right, bottom, text FROM Block WHERE page=? ORDER BY top, left',
            (p_num,)
        ).fetchall()

        if not blocks:
            continue

        valid_blocks = []
        for left, top, right, bottom, b_text in blocks:
            if not is_noise(b_text, top, bottom, p_h):
                t = b_text.strip()
                if len(t) > 0:
                    valid_blocks.append(t)

        if not valid_blocks:
            continue

        # Process blocks into paragraphs
        page_paragraphs = []
        current_para = ""
        in_code_block = False
        code_lines = []

        for b_raw in valid_blocks:
            b_clean = clean_spacing(b_raw)
            b_clean = apply_typo_fixes(b_clean)

            # Check if this block is a heading
            if re.match(r'^(?:0?\d장|Chapter|PART|\d+\.\d+(\.\d+)?|TIP)\s+', b_clean):
                if current_para:
                    page_paragraphs.append(current_para)
                    current_para = ""
                page_paragraphs.append(format_heading(b_clean))
                continue

            # Check if block lines look like code
            lines = b_clean.split('\n')
            code_line_count = sum(1 for ln in lines if is_code_line(ln))
            if len(lines) >= 2 and code_line_count >= len(lines) * 0.6:
                if current_para:
                    page_paragraphs.append(current_para)
                    current_para = ""
                page_paragraphs.append(f"\n```python\n{b_clean}\n```\n")
                continue

            # Normal text block merging
            # If current_para exists, determine if we should merge or start new paragraph
            if not current_para:
                current_para = b_clean
            else:
                # Does previous text end with sentence terminal?
                prev_ends_sentence = bool(re.search(r'[.?!:;”"’\)]\s*$', current_para))
                # Does current block start with sentence continuation?
                next_starts_cont = bool(re.match(r'^(?:니다|습니다|입니다|였다|했다|있었다|으로|에서|로서|에게|과|와)\b', b_clean))
                # Does current block look like a list item?
                is_list_item = bool(re.match(r'^(?:[0-9]+[\.\)]|[-*•])\s+', b_clean))

                if not prev_ends_sentence or next_starts_cont:
                    # Check for syllable split (e.g. "사례였습" + "니다")
                    if re.search(r'[가-힣]+[습합]$', current_para) and re.match(r'^니다\b', b_clean):
                        current_para += b_clean
                    else:
                        current_para += " " + b_clean
                else:
                    page_paragraphs.append(current_para)
                    current_para = b_clean

        if current_para:
            page_paragraphs.append(current_para)

        # Assemble page content
        page_body = "\n\n".join(page_paragraphs)
        page_body = apply_typo_fixes(page_body)
        
        pages_text.append(f"\n\n<!-- [Page {p_num}] -->\n\n{page_body}")

    full_text = "\n".join(pages_text)
    
    # Final global polish
    full_text = apply_typo_fixes(full_text)
    full_text = clean_spacing(full_text)

    # Save to local file
    with open(OUT_TXT_LOCAL, 'w', encoding='utf-8') as f:
        f.write(full_text)
    print(f"Saved {OUT_TXT_LOCAL} ({len(full_text)} characters, {len(full_text.splitlines())} lines)")

    # Save to user downloads
    try:
        with open(OUT_TXT_USER, 'w', encoding='utf-8') as f:
            f.write(full_text)
        print(f"Saved {OUT_TXT_USER}")
    except Exception as e:
        print(f"Could not save to user downloads: {e}")

    print("Reconstruction complete!")

if __name__ == '__main__':
    process_book()
