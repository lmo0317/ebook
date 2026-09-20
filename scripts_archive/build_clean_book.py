import sqlite3
import re
import os
import json

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
    (r'\b응담\b', '응답'),
    (r'\b담변\b', '답변'),
    (r'\b평기가\b', '평가'),
    (r'\b의건\b', '의견'),
    (r'\b점자\s*발전\b', '점차 발전'),
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
    (r'\b튜랑의\b', '튜링의'),
    (r'\b여전하\s+남기고\b', '여전히 남기고'),
    (r'\b서자유롭지\b', '에서 자유롭지'),
    (r'\b서크게\b', '에서 크게'),
    (r'\bIntelligcnce\b', 'Intelligence'),
    (r'\b복\s*하고\s*다층적인\b', '복잡하고 다층적인'),
    (r'\b때문임니다\b', '때문입니다'),
    (r'\b([가-힣]+)임니다\b', r'\1입니다'),

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
    (r'\b([가-힣]+)합니\s+다\b', r'\1합니다'),
    (r'\b합\s+니다\b', '합니다'),
    (r'\b([가-힣]+)였습\s+니다\b', r'\1였습니다'),
    (r'\b([가-힣]+)되었습\s+니다\b', r'\1되었습니다'),
    (r'\b([가-힣]+)겠습\s+니다\b', r'\1겠습니다'),
    (r'\b([가-힣]+)있습\s+니다\b', r'\1있습니다'),
    (r'\b고민해이야합\s*니다\b', '고민해야 합니다'),

    # Morphological corrections without \b boundary issues
    (r'맛춤화', '맞춤화'),
    (r'맛춤', '맞춤'),
    (r'독사들', '독자들'),
    (r'모델텔', '모델'),
    (r'파라미터\s*뷰닝', '파라미터 튜닝'),
    (r'지집서', '지침서'),
    (r'터테디노트', '테디노트'),
    (r'깃혀브', '깃허브'),
    (r'실습0로', '실습으로'),
    (r'브브릭메이트', '브릭메이트'),
    (r'wWeb', 'Web'),
    (r'인공지식에', '인공지능에'),
    (r'자근차근', '차근차근'),
    (r'통동해', '통해'),
    (r'([을를]|이|그|이러한\s+[가-힣]+|저러한\s+[가-힣]+)\s+동해\b', r'\1 통해'),
    (r'AT\s*모[텔델]', 'AI 모델'),
    (r'\bLlaMA\b', 'Llama'),
]

def apply_typo_fixes(text: str) -> str:
    t = text
    for pat, rep in TYPO_REPLACEMENTS:
        if callable(rep):
            t = re.sub(pat, rep, t)
        else:
            t = re.sub(pat, rep, t)
    return t

def is_noise(text: str, top: int, bottom: int, page_height: int) -> bool:
    t = text.strip()
    if not t:
        return True
    # Barcodes & tracking strings
    if re.search(r'^(9[Ttr0-9]{8,}|[0-9a-zA-Z_\-]{14,})', t):
        return True
    if top > page_height * 0.88 and re.match(r'^[0-9a-zA-Z\s\-_]{10,}$', t):
        return True
    # Standalone margin page numbers
    if re.match(r'^[0-9ivxIVX]{1,4}$', t) and (top < page_height * 0.08 or bottom > page_height * 0.92):
        return True
    # Running header noise: book title, chapter title at extreme margins
    if bottom < page_height * 0.075:
        if any(w in t for w in ['한 권으로', '한권으로', '파인튜닝', 'PART', 'NLP의 과거', '전체 파인튜닝', 'vLLM']):
            return True
        if len(t) < 40:
            return True
    # Running footer noise
    if top > page_height * 0.925:
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

def is_code_block_text(text: str) -> bool:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return False
    code_indicators = [
        'import ', 'from ', 'def ', 'class ', 'return ', 'if __name__',
        'self.', 'torch.', 'nn.', 'F.', 'np.', 'plt.', 'model =', 'loss =',
        'optimizer =', 'tokenizer =', 'print(', 'super().', 'pip install',
        'git clone', 'cd ', 'python ', 'export ', 'curl ', 'wget ',
        'docker run', 'runpod ', 'wandb.', 'def __init__', 'def forward'
    ]
    code_score = sum(1 for ln in lines if any(ln.startswith(ci) for ci in code_indicators))
    # Check syntax patterns: colons at end of line, indentation, assignments
    syntax_score = sum(1 for ln in lines if re.search(r'(=|\{|\}|\[|\]|\(\)|:\s*$)', ln))
    return (code_score >= 2) or (len(lines) >= 3 and (code_score + syntax_score) >= len(lines) * 0.75)

def format_clean_code(text: str) -> str:
    lines = text.splitlines()
    cleaned_lines = []
    indent = 0
    for l in lines:
        s = l.strip()
        if not s:
            continue
        # Un-corrupt common OCR errors in Python
        s = s.replace('def_init_', 'def __init__')
        s = s.replace('super()._init_', 'super().__init__')
        s = s.replace('self. token_embedding _table', 'self.token_embedding_table')
        s = s.replace('self. position_embedding _table', 'self.position_embedding_table')
        s = s.replace('nn. Linear', 'nn.Linear')
        s = s.replace('nn. Embedding', 'nn.Embedding')
        s = s.replace('F.cross_ent ropy', 'F.cross_entropy')
        s = s.replace('max _new_tokens', 'max_new_tokens')
        
        # Adjust indent
        if s.startswith(('elif ', 'else:', 'except', 'finally:')):
            indent = max(0, indent - 4)
        if s.startswith('return ') and indent >= 8:
            pass
            
        cleaned_lines.append(' ' * indent + s)
        
        if s.endswith(':'):
            indent += 4
        elif s.startswith('return '):
            indent = max(0, indent - 4)
            
    code_content = '\n'.join(cleaned_lines)
    return f"```python\n{code_content}\n```"

def build_book():
    print("Connecting to reader_device.db...")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    book_info = c.execute('SELECT id, title, pages FROM Book LIMIT 1').fetchone()
    if not book_info:
        print("No book found!")
        return
    book_id, title, total_pages = book_info
    print(f"Building clean eBook for: '{title}' ({total_pages} pages)")

    full_pages = []

    # Book Title Header
    full_pages.append(
        "# 한 권으로 끝내는 실전 LLM 파인튜닝\n\n"
        "**저자:** 강다솔 | **출판:** 위키북스\n"
        "**부제:** GPT 작동 원리부터 Gemma 2 / Llama 3 파인튜닝, vLLM 서빙까지\n\n"
        "---\n"
    )

    pending_continuation = ""

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

        # Page paragraphs builder
        page_paras = []
        current_para = ""

        # Prepend pending continuation from previous page if exists
        if pending_continuation:
            first_b = clean_spacing(valid_blocks[0])
            first_b = apply_typo_fixes(first_b)
            # Syllable merge or space merge
            if re.search(r'[가-힣]$', pending_continuation) and re.match(r'^[가-힣]', first_b):
                current_para = pending_continuation + first_b
            else:
                current_para = pending_continuation + " " + first_b
            valid_blocks = valid_blocks[1:]
            pending_continuation = ""

        for b_raw in valid_blocks:
            b_clean = clean_spacing(b_raw)
            b_clean = apply_typo_fixes(b_clean)

            # Check headings
            if re.match(r'^(?:0?\d장|Chapter|PART|\d+\.\d+(\.\d+)?|TIP)\s+', b_clean):
                if current_para:
                    page_paras.append(current_para)
                    current_para = ""
                # Format heading
                if re.match(r'^(?:0?\d장|Chapter\s*\d|PART\s*\d)', b_clean, re.IGNORECASE):
                    page_paras.append(f"\n# {b_clean}\n")
                elif re.match(r'^\d+\.\d+\s+', b_clean):
                    page_paras.append(f"\n## {b_clean}\n")
                elif re.match(r'^\d+\.\d+\.\d+\s+', b_clean):
                    page_paras.append(f"\n### {b_clean}\n")
                elif re.match(r'^(?:TIP|Tip)\s+', b_clean):
                    page_paras.append(f"\n> **{b_clean}**\n")
                continue

            # Check code block
            if is_code_block_text(b_raw):
                if current_para:
                    page_paras.append(current_para)
                    current_para = ""
                page_paras.append(format_clean_code(b_raw))
                continue

            # Paragraph flow
            if not current_para:
                current_para = b_clean
            else:
                prev_ends = bool(re.search(r'[.?!:;”"’\)]\s*$', current_para))
                next_cont = bool(re.match(r'^(?:니다|습니다|입니다|였다|했다|있었다|으로|에서|로서|에게|과|와)\b', b_clean))

                if not prev_ends or next_cont:
                    # Broken verb ending stitch (e.g. "사례였습" + "니다")
                    if re.search(r'[가-힣]+[습합]$', current_para) and re.match(r'^니다\b', b_clean):
                        current_para += b_clean
                    else:
                        current_para += " " + b_clean
                else:
                    page_paras.append(current_para)
                    current_para = b_clean

        # Check if the last paragraph continues across to the next page
        if current_para:
            if not re.search(r'[.?!:;”"’\)]\s*$', current_para) and len(current_para) > 20:
                pending_continuation = current_para
            else:
                page_paras.append(current_para)

        if page_paras:
            page_content = "\n\n".join(page_paras)
            page_content = apply_typo_fixes(page_content)
            full_pages.append(f"\n\n<!-- [Page {p_num}] -->\n\n{page_content}")

    # Add any leftover
    if pending_continuation:
        full_pages.append(f"\n\n{pending_continuation}")

    full_book_text = "\n".join(full_pages)
    full_book_text = apply_typo_fixes(full_book_text)
    full_book_text = clean_spacing(full_book_text)

    # Save to local
    with open(OUT_TXT_LOCAL, 'w', encoding='utf-8') as f:
        f.write(full_book_text)
    print(f"Saved: {OUT_TXT_LOCAL} ({len(full_book_text)} chars)")

    # Save to app book cache file for device deployment
    app_txt = 'c0000000-0000-0000-0000-000000000001.txt'
    with open(app_txt, 'w', encoding='utf-8') as f:
        f.write(full_book_text)
    print(f"Saved: {app_txt}")

    # Save to user downloads
    try:
        with open(OUT_TXT_USER, 'w', encoding='utf-8') as f:
            f.write(full_book_text)
        print(f"Saved: {OUT_TXT_USER}")
    except Exception as e:
        print(f"Error saving user file: {e}")

    print("eBook generated successfully!")

if __name__ == '__main__':
    build_book()
