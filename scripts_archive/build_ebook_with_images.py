import fitz
import cv2
import sqlite3
import re
import os
import sys
import time
import shutil
import zipfile
import json
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding='utf-8')

PDF_PATH = r'C:\Users\lmo03\Downloads\book_cropped.pdf'
DB_PATH = 'reader_device.db'
OUTPUT_LIVE_DB = 'device_reader_live.db'
IMAGES_DIR = 'book_images'
OUT_TXT_FILE = 'c0000000-0000-0000-0000-000000000001.txt'
COVER_PATH = 'c0000000-0000-0000-0000-000000000001.jpg'
BOOK_ID = 'c0000000-0000-0000-0000-000000000001'
ZIP_PACKAGE_PATH = 'book_package.zip'

os.makedirs(IMAGES_DIR, exist_ok=True)

# Comprehensive OCR typo fixes
TYPO_REPLACEMENTS = [
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
    (r'\bOpenAl\b', 'OpenAI'),
    (r'\bGP-4\b', 'GPT-4'),
    (r'\bAl\b', 'AI'),
    (r'\bVLLM\b', 'vLLM'),
    (r'\bRunpod\b', 'RunPod'),
    (r'\bpqdm\b', 'tqdm'),
    (r'\biser\b(?=\s*라는)', 'user'),
    (r'\b([가-힣]+)함\s*니다\b', r'\1합니다'),
    (r'\b([가-힣]+)습\s+니다\b', r'\1습니다'),
    (r'\b([가-힣]+)합\s+니다\b', r'\1합니다'),
    (r'\b([가-힣]+)합니\s+다\b', r'\1합니다'),
    (r'\b([가-힣]+)였습\s+니다\b', r'\1였습니다'),
    (r'\b([가-힣]+)되었습\s+니다\b', r'\1되었습니다'),
    (r'\b([가-힣]+)겠습\s+니다\b', r'\1겠습니다'),
    (r'\b([가-힣]+)있습\s+니다\b', r'\1있습니다'),
]

def apply_typo_fixes(text: str) -> str:
    t = text
    for pat, rep in TYPO_REPLACEMENTS:
        t = re.sub(pat, rep, t)
    return t

def clean_spacing(text: str) -> str:
    t = text
    t = re.sub(r'\s+([.,!?;:])', r'\1', t)
    t = re.sub(r'([(\[{<])\s+', r'\1', t)
    t = re.sub(r'\s+([)\]}>])', r'\1', t)
    t = re.sub(r'(\d+)\s*\.\s*(\d+)', r'\1.\2', t)
    t = re.sub(r'([가-힣])\s*\n\s*([가-힣])', r'\1 \2', t)
    t = re.sub(r'[ \t]+', ' ', t)
    return t.strip()

def is_noise(text: str, top: int, bottom: int, page_height: int) -> bool:
    t = text.strip()
    if not t:
        return True
    if re.search(r'^(9[Ttr0-9]{8,}|[0-9a-zA-Z_\-]{14,})', t):
        return True
    if top > page_height * 0.88 and re.match(r'^[0-9a-zA-Z\s\-_]{10,}$', t):
        return True
    if re.match(r'^[0-9ivxIVX]{1,4}$', t) and (top < page_height * 0.08 or bottom > page_height * 0.92):
        return True
    if bottom < page_height * 0.075:
        if any(w in t for w in ['한 권으로', '한권으로', '파인튜닝', 'PART', 'NLP의 과거', '전체 파인튜닝', 'vLLM']):
            return True
        if len(t) < 40:
            return True
    if top > page_height * 0.925:
        if any(w in t for w in ['위키북스', 'WIKIBOOKS']):
            return True
        if len(t) < 35:
            return True
    if t in ['.', '-', '_', '~', ',', '`', '\'', '"', '|', '/', '\\', '·', ':']:
        return True
    return False

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
    syntax_score = sum(1 for ln in lines if re.search(r'(=|\{|\}|\[|\]|\(\)|:\s*$)', ln))
    return (code_score >= 2) or (len(lines) >= 3 and (code_score + syntax_score) >= len(lines) * 0.75)

def format_clean_code(text: str) -> str:
    lines = text.splitlines()
    cleaned = []
    indent = 0
    for l in lines:
        s = l.strip()
        if not s:
            continue
        s = s.replace('def_init_', 'def __init__')
        s = s.replace('super()._init_', 'super().__init__')
        s = s.replace('self. token_embedding _table', 'self.token_embedding_table')
        s = s.replace('self. position_embedding _table', 'self.position_embedding_table')
        s = s.replace('nn. Linear', 'nn.Linear')
        s = s.replace('nn. Embedding', 'nn.Embedding')
        s = s.replace('F.cross_ent ropy', 'F.cross_entropy')
        s = s.replace('max _new_tokens', 'max_new_tokens')
        
        if s.startswith(('elif ', 'else:', 'except', 'finally:')):
            indent = max(0, indent - 4)
        cleaned.append(' ' * indent + s)
        if s.endswith(':'):
            indent += 4
        elif s.startswith('return '):
            indent = max(0, indent - 4)
    return f"```python\n" + "\n".join(cleaned) + "\n```"

def is_true_caption(text: str) -> bool:
    t = text.strip().replace('\n', ' ')
    if not re.match(r'^(?:그림|Figure)\s*\d+[\.\-_]\d+', t):
        return False
    if re.search(r'(습니다|입니다|했다|였다|있다|다|냐|까|요|죠|됨)\s*[.?!]*$', t):
        return False
    if len(t) > 50:
        return False
    return True

def make_styled_cover(output_path):
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
        b_font = ImageFont.truetype(font_path, 18)
        t_font = ImageFont.truetype(font_path, 26)
        a_font = ImageFont.truetype(font_path, 16)
    else:
        b_font = t_font = a_font = ImageFont.load_default()
    draw.text((width // 2, 70), "[ Illustrated e-Book ]", fill="#38BDF8", font=b_font, anchor="mm")
    draw.text((width // 2, 220), "한 권으로 끝내는", fill="#FFFFFF", font=t_font, anchor="mm")
    draw.text((width // 2, 265), "실전 LLM 파인튜닝", fill="#60A5FA", font=t_font, anchor="mm")
    draw.text((width // 2, 335), "(고화질 도표/삽화 수록 전자책)", fill="#94A3B8", font=b_font, anchor="mm")
    draw.text((width // 2, 510), "저자: 강다솔 | 위키북스", fill="#CBD5E1", font=a_font, anchor="mm")
    img.save(output_path, "JPEG", quality=92)
    print(f"Cover generated: {output_path}")

def build_ebook():
    print("=" * 60)
    print("Building Illustrated e-Book Package with Figures & Reflow Text")
    print("=" * 60)

    doc = fitz.open(PDF_PATH)
    total_pages = len(doc)
    print(f"Loaded PDF: {PDF_PATH} ({total_pages} pages)")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    make_styled_cover(COVER_PATH)

    book_content_parts = []
    database_paragraphs = []
    extracted_images_count = 0
    order_counter = 1

    # Book Title Header
    book_header = (
        "# 한 권으로 끝내는 실전 LLM 파인튜닝\n\n"
        "**저자:** 강다솔 | **출판:** 위키북스\n"
        "**부제:** GPT 작동 원리부터 Gemma 2 / Llama 3 파인튜닝, vLLM 서빙까지 (고화질 도표 수록)\n\n"
        "---\n"
    )
    book_content_parts.append(book_header)
    database_paragraphs.append((BOOK_ID, 1, order_counter, book_header.strip(), None, 50, 50, 950, 1450, "BODY", "BODY"))
    order_counter += 1

    caption_regex = re.compile(r'^(?:그림|Figure)\s*(\d+)[\.\-_](\d+)(.*)')

    for p_num in range(1, total_pages + 1):
        p_row = c.execute('SELECT width, height FROM Page WHERE number=?', (p_num,)).fetchone()
        p_w = p_row[0] if p_row and p_row[0] > 0 else 1639
        p_h = p_row[1] if p_row and p_row[1] > 0 else 2200

        blocks = c.execute(
            'SELECT left, top, right, bottom, text FROM Block WHERE page=? ORDER BY top, left',
            (p_num,)
        ).fetchall()

        if not blocks:
            continue

        # Find true captions on this page
        page_captions = []
        for idx, b in enumerate(blocks):
            if is_true_caption(b[4]):
                page_captions.append((idx, b))

        # If there are captions, render high-res page image to crop diagrams
        page_img = None
        sx, sy = 1.0, 1.0
        if page_captions:
            pix = doc[p_num - 1].get_pixmap(dpi=200)
            tmp_path = f"extracted_test_p{p_num}.png"
            pix.save(tmp_path)
            page_img = cv2.imread(tmp_path)
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            if page_img is not None:
                h_img, w_img = page_img.shape[:2]
                sx = w_img / float(p_w)
                sy = h_img / float(p_h)

        # Process blocks and extract images
        page_items = [] # list of (item_type, content, top_y, caption_block)
        suppressed_block_indices = set()

        for c_idx, c_block in page_captions:
            c_text = c_block[4].strip().replace('\n', ' ')
            m = caption_regex.match(c_text)
            ch_tag, fig_tag = (m.group(1), m.group(2)) if m else ("0", str(extracted_images_count + 1))
            clean_caption = f"그림 {ch_tag}.{fig_tag} {m.group(3).strip() if m else ''}".strip()

            # Find top boundary of diagram (preceding body text block)
            prev_bottom = int(140)
            for j in range(c_idx - 1, -1, -1):
                pb = blocks[j]
                if pb[3] < c_block[1] - 30:
                    if (pb[2] - pb[0] > 450) or len(pb[4].strip()) > 30 or is_code_block_text(pb[4]):
                        prev_bottom = pb[3]
                        break

            # Suppress noisy small text blocks inside diagram region
            diag_top = prev_bottom
            diag_bottom = c_block[3]
            for j in range(len(blocks)):
                if j != c_idx:
                    b_mid_y = (blocks[j][1] + blocks[j][3]) / 2
                    if diag_top < b_mid_y < diag_bottom:
                        suppressed_block_indices.add(j)

            # Crop image
            if page_img is not None:
                c_top_px = max(0, int((prev_bottom + 15) * sy))
                c_bot_px = min(page_img.shape[0], int((c_block[3] + 15) * sy))
                c_left_px = max(0, int(150 * sx))
                c_right_px = min(page_img.shape[1], int(1490 * sx))

                if (c_bot_px - c_top_px) > 100:
                    crop = page_img[c_top_px:c_bot_px, c_left_px:c_right_px]
                    # Trim whitespace
                    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                    _, thresh = cv2.threshold(gray, 245, 255, cv2.THRESH_BINARY_INV)
                    coords = cv2.findNonZero(thresh)
                    if coords is not None:
                        x, y, cw, ch = cv2.boundingRect(coords)
                        pad = 12
                        x1 = max(0, x - pad)
                        y1 = max(0, y - pad)
                        x2 = min(crop.shape[1], x + cw + pad)
                        y2 = min(crop.shape[0], y + ch + pad)
                        crop = crop[y1:y2, x1:x2]

                    img_filename = f"p{p_num:03d}_fig_{ch_tag}_{fig_tag}.png"
                    img_save_path = os.path.join(IMAGES_DIR, img_filename)
                    cv2.imwrite(img_save_path, crop)
                    extracted_images_count += 1

                    # Register IMAGE item
                    image_tag = f"[IMAGE:images/{img_filename}|{clean_caption}]"
                    page_items.append(("IMAGE", image_tag, c_block[1], clean_caption, img_filename))
                    suppressed_block_indices.add(c_idx)

        # Build regular text and code blocks
        for idx, b in enumerate(blocks):
            if idx in suppressed_block_indices:
                continue
            b_text = b[4].strip()
            if is_noise(b_text, b[1], b[3], p_h):
                continue
            if not b_text:
                continue

            b_clean = clean_spacing(b_text)
            b_clean = apply_typo_fixes(b_clean)

            if is_code_block_text(b_text):
                code_formatted = format_clean_code(b_text)
                page_items.append(("CODE", code_formatted, b[1], None, None))
            elif re.match(r'^(?:0?\d장|Chapter|PART|\d+\.\d+(\.\d+)?|TIP)\s+', b_clean):
                if re.match(r'^(?:0?\d장|Chapter\s*\d|PART\s*\d)', b_clean, re.IGNORECASE):
                    page_items.append(("TITLE", f"# {b_clean}", b[1], None, None))
                elif re.match(r'^\d+\.\d+\s+', b_clean):
                    page_items.append(("TITLE", f"## {b_clean}", b[1], None, None))
                elif re.match(r'^\d+\.\d+\.\d+\s+', b_clean):
                    page_items.append(("TITLE", f"### {b_clean}", b[1], None, None))
                elif re.match(r'^(?:TIP|Tip)\s+', b_clean):
                    page_items.append(("BODY", f"> **{b_clean}**", b[1], None, None))
            else:
                page_items.append(("BODY", b_clean, b[1], None, None))

        # Sort items on this page by vertical Y position (natural reading order)
        page_items.sort(key=lambda item: item[2])

        # Page paragraph stitching
        merged_page_paras = []
        current_text_buf = ""

        for item in page_items:
            itype = item[0]
            icontent = item[1]

            if itype in ("IMAGE", "CODE", "TITLE"):
                if current_text_buf:
                    merged_page_paras.append(("BODY", current_text_buf))
                    current_text_buf = ""
                merged_page_paras.append((itype, icontent))
            else:
                # BODY text paragraph flow
                if not current_text_buf:
                    current_text_buf = icontent
                else:
                    prev_ends = bool(re.search(r'[.?!:;”"’\)]\s*$', current_text_buf))
                    next_cont = bool(re.match(r'^(?:니다|습니다|입니다|였다|했다|있었다|으로|에서|로서|에게|과|와)\b', icontent))
                    if not prev_ends or next_cont:
                        if re.search(r'[가-힣]+[습합]$', current_text_buf) and re.match(r'^니다\b', icontent):
                            current_text_buf += icontent
                        else:
                            current_text_buf += " " + icontent
                    else:
                        merged_page_paras.append(("BODY", current_text_buf))
                        current_text_buf = icontent

        if current_text_buf:
            merged_page_paras.append(("BODY", current_text_buf))

        # Format into page markdown and database records
        if merged_page_paras:
            page_text_blocks = []
            for p_type, p_txt in merged_page_paras:
                p_txt = apply_typo_fixes(p_txt)
                page_text_blocks.append(p_txt)
                database_paragraphs.append((
                    BOOK_ID,
                    p_num,
                    order_counter,
                    p_txt,
                    None,
                    50, 50, 950, 1450,
                    p_type,
                    "BODY"
                ))
                order_counter += 1

            page_full_text = "\n\n".join(page_text_blocks)
            book_content_parts.append(f"\n\n<!-- [Page {p_num}] -->\n\n{page_full_text}")

        if p_num % 40 == 0 or p_num == total_pages:
            print(f"Processed page {p_num}/{total_pages} | Extracted images so far: {extracted_images_count}")

    # Write complete text file
    final_book_text = "\n".join(book_content_parts)
    final_book_text = apply_typo_fixes(final_book_text)
    final_book_text = clean_spacing(final_book_text)

    with open(OUT_TXT_FILE, 'w', encoding='utf-8') as f:
        f.write(final_book_text)
    with open('book_converted.txt', 'w', encoding='utf-8') as f:
        f.write(final_book_text)
    print(f"\nSaved structured eBook text: {OUT_TXT_FILE} ({len(final_book_text)} chars)")

    # Build SQLite Live Database
    print(f"Building SQLite database: {OUTPUT_LIVE_DB}...")
    if os.path.exists(OUTPUT_LIVE_DB):
        os.remove(OUTPUT_LIVE_DB)

    live_conn = sqlite3.connect(OUTPUT_LIVE_DB)
    lc = live_conn.cursor()

    # Create tables
    lc.execute("""
        CREATE TABLE IF NOT EXISTS Book (
            id TEXT PRIMARY KEY NOT NULL,
            title TEXT NOT NULL,
            uri TEXT NOT NULL,
            fileName TEXT NOT NULL,
            size INTEGER NOT NULL,
            hash TEXT NOT NULL,
            pages INTEGER NOT NULL,
            created INTEGER NOT NULL,
            opened INTEGER NOT NULL,
            status TEXT NOT NULL,
            done INTEGER NOT NULL,
            author TEXT NOT NULL,
            memo TEXT NOT NULL,
            error TEXT NOT NULL
        )
    """)
    lc.execute("""
        CREATE TABLE IF NOT EXISTS Page (
            bookId TEXT NOT NULL,
            number INTEGER NOT NULL,
            width INTEGER NOT NULL,
            height INTEGER NOT NULL,
            rotation INTEGER NOT NULL,
            status TEXT NOT NULL,
            error TEXT NOT NULL,
            PRIMARY KEY(bookId, number)
        )
    """)
    lc.execute("""
        CREATE TABLE IF NOT EXISTS Block (
            id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            bookId TEXT NOT NULL,
            page INTEGER NOT NULL,
            text TEXT NOT NULL,
            left INTEGER NOT NULL,
            top INTEGER NOT NULL,
            right INTEGER NOT NULL,
            bottom INTEGER NOT NULL,
            linesJson TEXT NOT NULL
        )
    """)
    lc.execute("CREATE INDEX IF NOT EXISTS `index_Block_bookId` ON `Block` (`bookId`)")
    lc.execute("""
        CREATE TABLE IF NOT EXISTS Paragraph (
            id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            bookId TEXT NOT NULL,
            page INTEGER NOT NULL,
            `order` INTEGER NOT NULL,
            original TEXT NOT NULL,
            edited TEXT,
            left INTEGER NOT NULL,
            top INTEGER NOT NULL,
            right INTEGER NOT NULL,
            bottom INTEGER NOT NULL,
            type TEXT NOT NULL,
            region TEXT NOT NULL
        )
    """)
    lc.execute("CREATE INDEX IF NOT EXISTS `index_Paragraph_bookId` ON `Paragraph` (`bookId`)")
    lc.execute("""
        CREATE TABLE IF NOT EXISTS Position (
            bookId TEXT PRIMARY KEY NOT NULL,
            page INTEGER NOT NULL,
            paragraphId INTEGER NOT NULL,
            `index` INTEGER NOT NULL,
            `offset` INTEGER NOT NULL
        )
    """)
    lc.execute("""
        CREATE TABLE IF NOT EXISTS Bookmark (
            id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            bookId TEXT NOT NULL,
            page INTEGER NOT NULL,
            paragraphId INTEGER NOT NULL,
            `offset` INTEGER NOT NULL,
            memo TEXT NOT NULL,
            created INTEGER NOT NULL
        )
    """)
    lc.execute("CREATE INDEX IF NOT EXISTS `index_Bookmark_bookId` ON `Bookmark` (`bookId`)")
    lc.execute("CREATE TABLE IF NOT EXISTS room_master_table (id INTEGER PRIMARY KEY, identity_hash TEXT)")
    lc.execute("INSERT OR REPLACE INTO room_master_table (id, identity_hash) VALUES(42, 'd5ff8686cb0182fe692967642ccb9c13')")

    now_ms = int(time.time() * 1000)
    file_bytes = final_book_text.encode('utf-8')
    import hashlib
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    book_title = "한 권으로 끝내는 실전 LLM 파인튜닝 (고화질 도표 e-Book)"
    lc.execute("""
        INSERT INTO Book VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        BOOK_ID,
        book_title,
        f"file:///sdcard/Download/{OUT_TXT_FILE}",
        OUT_TXT_FILE,
        len(file_bytes),
        file_hash,
        total_pages,
        now_ms,
        now_ms + 100000,
        "READY",
        total_pages,
        "강다솔 (위키북스)",
        f"고화질 도표 {extracted_images_count}개 수록 하이브리드 전자책",
        ""
    ))

    for p in range(1, total_pages + 1):
        lc.execute("INSERT INTO Page VALUES (?, ?, ?, ?, ?, ?, ?)", (BOOK_ID, p, 1000, 1500, 0, "COMPLETED", ""))

    lc.executemany("""
        INSERT INTO Paragraph (bookId, page, `order`, original, edited, left, top, right, bottom, type, region)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, database_paragraphs)

    live_conn.commit()
    live_conn.close()
    print(f"Database built successfully! Total paragraphs: {len(database_paragraphs)}")

    # Create ZIP Package for standalone distribution
    print(f"Packaging into standalone distribution: {ZIP_PACKAGE_PATH}...")
    manifest = {
        "id": BOOK_ID,
        "title": book_title,
        "author": "강다솔",
        "publisher": "위키북스",
        "pages": total_pages,
        "figuresCount": extracted_images_count,
        "paragraphsCount": len(database_paragraphs),
        "buildTime": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    with open("manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    with zipfile.ZipFile(ZIP_PACKAGE_PATH, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write("manifest.json", "manifest.json")
        z.write(OUT_TXT_FILE, "book.txt")
        z.write(COVER_PATH, "cover.jpg")
        for img_name in os.listdir(IMAGES_DIR):
            if img_name.endswith(('.png', '.jpg')):
                z.write(os.path.join(IMAGES_DIR, img_name), f"images/{img_name}")

    print(f"Standalone package created: {ZIP_PACKAGE_PATH} ({os.path.getsize(ZIP_PACKAGE_PATH) / (1024*1024):.2f} MB)")
    print("\n" + "=" * 60)
    print(f"SUCCESS! Extracted {extracted_images_count} figures and generated full eBook!")
    print("=" * 60)

if __name__ == '__main__':
    build_ebook()
