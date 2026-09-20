import os
import re
import sys
import json
import time
import sqlite3
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = 'reader_device.db'
CACHE_PATH = 'converted_pages_cache.json'
OUT_TXT_LOCAL = 'book_converted.txt'
OUT_TXT_USER = r'C:\Users\lmo03\Downloads\book_converted.txt'

OCR_REPLACEMENTS = [
    (r'\b맛춤화\b', '맞춤화'),
    (r'\b맛춤\b', '맞춤'),
    (r'\b스위지\b', '스위치'),
    (r'\b마지\b', '마치'),
    (r'\b임겟값\b', '임계값'),
    (r'\b파인류님\b', '파인튜닝'),
    (r'\b파인뉴님\b', '파인튜닝'),
    (r'\b위키숙스\b', '위키북스'),
    (r'\b저직권\b', '저작권'),
    (r'\b어린선\b', '어텐션'),
    (r'\b독사들\b', '독자들'),
    (r'\b감들올\b', '값들을'),
    (r'\b담변\b', '답변'),
    (r'\b의건\b', '의견'),
    (r'\b평기가\b', '평가'),
    (r'\b제인\b', '제안'),
    (r'\b동해\b(?=\s+[A-Za-z가-힣]+을|를|에)', '통해'),
    (r'\bAl\b', 'AI'),
]

def pre_clean_ocr(text: str) -> str:
    t = text
    for pat, rep in OCR_REPLACEMENTS:
        t = re.sub(pat, rep, t)
    return t

def is_noise(text: str, top: int, bottom: int, page_height: int) -> bool:
    t = text.strip()
    if not t:
        return True
    # Barcode & ISBN tracking numbers
    if re.search(r'^(9[Ttr0-9]{8,}|[0-9a-zA-Z_\-]{14,})', t):
        return True
    if top > page_height * 0.88 and re.match(r'^[0-9a-zA-Z\s\-_]{10,}$', t):
        return True
    # Margin page numbers
    if re.match(r'^[0-9ivxIVX]{1,4}$', t) and (top < page_height * 0.08 or bottom > page_height * 0.92):
        return True
    # Book title running header (< 8% page height)
    if bottom < page_height * 0.08 and ('한 권으로' in t or '파인튜닝' in t or len(t) < 40):
        return True
    # Running footer (> 92% page height)
    if top > page_height * 0.92 and ('위키북스' in t or len(t) < 40):
        return True
    # Standalone noise characters
    if t in ['.', '-', '_', '~', ',', '`', '\'', '"', '|', '/', '\\', '·', ':']:
        return True
    return False

def clean_output_markdown(text: str) -> str:
    t = text.strip()
    if t.startswith('```markdown'):
        t = t[11:].strip()
    elif t.startswith('```'):
        t = t[3:].strip()
    if t.endswith('```'):
        t = t[:-3].strip()
    
    hanja_map = {
        '和': '와',
        '的': '의',
        '是': '는',
        '及': ' 및 ',
        '與': '와',
        '在': '에서'
    }
    for h, k in hanja_map.items():
        t = t.replace(h, k)
    
    t = re.sub(r'\s+([.,!?:;])', r'\1', t)
    t = re.sub(r'([가-힣]+)\s+(을|를|이|가|의|에|에서|로|으로|와|과|도|은|는)\b', r'\1\2', t)
    t = re.sub(r'\b(있습|합|였습|되었습|하겠습|되겠습)\s+(니다)\b', r'\1\2', t)
    
    return t.strip()

def main():
    print("Loading model Qwen/Qwen2.5-3B-Instruct on RTX 5080...", flush=True)
    model_name = 'Qwen/Qwen2.5-3B-Instruct'
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.bfloat16,
        device_map='cuda'
    )
    model.eval()
    print("Model loaded successfully.", flush=True)

    cache = {}
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, 'r', encoding='utf-8') as f:
                cache = json.load(f)
            print(f"Loaded existing cache with {len(cache)} pages.", flush=True)
        except Exception as e:
            print(f"Cache load error: {e}", flush=True)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    pages = c.execute('SELECT number, width, height FROM Page ORDER BY number').fetchall()
    total_pages = len(pages)
    print(f"Total pages to process: {total_pages}", flush=True)

    start_time = time.time()
    processed_count = 0
    
    for idx, (p_num, p_w, p_h) in enumerate(pages):
        page_str = str(p_num)
        if page_str in cache and cache[page_str].strip():
            continue

        p_h = p_h if p_h and p_h > 0 else 2200
        blocks = c.execute(
            'SELECT left, top, right, bottom, text FROM Block WHERE page=? ORDER BY top, left',
            (p_num,)
        ).fetchall()

        valid_texts = []
        for left, top, right, bottom, b_text in blocks:
            if not is_noise(b_text, top, bottom, p_h):
                cleaned_b = pre_clean_ocr(b_text.strip())
                if cleaned_b:
                    valid_texts.append(cleaned_b)

        if not valid_texts:
            cache[page_str] = ""
            with open(CACHE_PATH, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
            continue

        raw_content = "\n\n".join(valid_texts)
        if len(raw_content.strip()) < 8:
            cache[page_str] = ""
            with open(CACHE_PATH, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
            continue

        # If page is just a very short title page (< 40 chars)
        if len(raw_content.strip()) < 40 and '\n' not in raw_content.strip():
            cleaned_text = f"# {raw_content.strip()}"
            cache[page_str] = cleaned_text
            with open(CACHE_PATH, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
            print(f"[{len(cache)}/{total_pages}] Page {p_num} (Short Title): {cleaned_text}", flush=True)
            continue

        prompt = f"""당신은 대한민국 최고의 IT 및 프로그래밍 도서 전문 출판 편집자입니다.
아래의 [스캔 OCR 원문]은 도서를 스캔하여 광학 문자 인식(OCR)한 텍스트입니다.
원문의 내용을 충실히 유지하며 출판 서적 품질의 완벽한 마크다운(Markdown)으로 교정하세요.

[교정 원칙]
1. 오탈자 및 띄어쓰기 교정: OCR 오인식(예: '마지'->'마치', '스위지'->'스위치', '임겟값'->'임계값', 'Al'->'AI', '독사들'->'독자들', '합 니다'->'합니다' 등)을 자연스러운 문맥으로 교정하세요.
2. 문단 개행 복원: 줄바꿈으로 끊겨 쪼개진 문장들을 하나의 자연스러운 문단으로 이어 붙이세요.
3. 코드/설정 블록: 파이썬(Python) 코드나 터미널 명령어, YAML 설정 등이 나오면 반드시 문법과 들여쓰기를 복원하여 ```python, ```bash, ```yaml 등 코드 블록으로 작성하세요.
4. 제목/소제목: 도서의 장/절/소제목(예: 1.1, 1.2.1, ▣ 01장 등)은 마크다운 헤더(#, ##, ###)로 적절히 정리하세요.
5. 잡음 제거: 페이지 번호, 바코드 숫자열, 반복되는 도서 제목(헤더/푸터)은 완전히 제거하세요.
6. 환각(Hallucination) 절대 금지: 원문에 없는 새로운 내용이나 설명, 뒷이야기를 절대 지어내지 마세요. 오직 원문에 존재하는 내용만 충실히 교정하세요.
7. 언어: 100% 한글과 영문으로만 작성하고, 절대 한자(漢字)나 중국어를 섞지 마세요.
8. 부연 설명 금지: 다른 인사말이나 설명 없이 오직 교정된 본문 텍스트만 출력하세요.

[스캔 OCR 원문]
{raw_content}
"""

        messages = [
            {'role': 'system', 'content': '당신은 전문 IT 도서 출판 편집자입니다. 한자를 사용하지 말고 원문에 없는 내용을 절대 지어내지 마세요.'},
            {'role': 'user', 'content': prompt}
        ]
        
        input_text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        model_inputs = tokenizer([input_text], return_tensors='pt').to('cuda')

        raw_char_len = len(raw_content)
        max_gen = min(1800, max(80, int(raw_char_len * 1.5)))

        t_page_start = time.time()
        with torch.no_grad():
            generated_ids = model.generate(
                **model_inputs,
                max_new_tokens=max_gen,
                do_sample=False
            )
        
        output_ids = [
            out[len(inp):] for inp, out in zip(model_inputs.input_ids, generated_ids)
        ]
        result_text = tokenizer.batch_decode(output_ids, skip_special_tokens=True)[0]
        cleaned_text = clean_output_markdown(result_text)

        cache[page_str] = cleaned_text
        processed_count += 1

        # Save cache every single page
        with open(CACHE_PATH, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)

        page_dur = time.time() - t_page_start
        pages_done = len(cache)
        pages_left = total_pages - pages_done
        avg_speed = (time.time() - start_time) / max(1, processed_count)
        eta_min = (pages_left * avg_speed) / 60
        print(f"[{pages_done}/{total_pages}] Page {p_num} restored ({len(cleaned_text)} chars in {page_dur:.1f}s) | ETA: {eta_min:.1f}m", flush=True)

    # Final save cache
    with open(CACHE_PATH, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    # Build final full text
    print("\nAssembling full book text...", flush=True)
    book_sections = []
    book_sections.append("# 한 권으로 끝내는 실전 LLM 파인튜닝\n\n**저자:** 강다솔 | **출판:** 위키북스\n**부제:** GPT 작동 원리부터 Gemma 2 / Llama 3 파인튜닝, vLLM 서빙까지\n\n---\n")

    for p_num in range(1, total_pages + 1):
        p_text = cache.get(str(p_num), "").strip()
        if p_text:
            book_sections.append(f"\n\n<!-- [Page {p_num}] -->\n{p_text}")

    full_content = "\n".join(book_sections)

    with open(OUT_TXT_LOCAL, 'w', encoding='utf-8') as f:
        f.write(full_content)
    print(f"Saved local file: {OUT_TXT_LOCAL} ({len(full_content)} chars)", flush=True)

    try:
        with open(OUT_TXT_USER, 'w', encoding='utf-8') as f:
            f.write(full_content)
        print(f"Saved user file: {OUT_TXT_USER}", flush=True)
    except Exception as e:
        print(f"Could not write to user downloads: {e}", flush=True)

    print("All tasks completed successfully!", flush=True)

if __name__ == '__main__':
    main()
