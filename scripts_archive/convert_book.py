import sqlite3
import re
import json

def clean_text(raw: str) -> str:
    # Normalize unicode and whitespace
    t = raw.replace('\uFFFD', '').replace('\uFEFF', '').replace('\u200B', '')
    # Fix spacing before punctuation
    t = re.sub(r'\s+([.,!?;:])', r'\1', t)
    # Fix spacing inside brackets
    t = re.sub(r'([(\[{<])\s+', r'\1', t)
    t = re.sub(r'\s+([)\]}>])', r'\1', t)
    # Fix numbered section headers: "1 . 2 . 3" -> "1.2.3"
    t = re.sub(r'(\d+)\s*\.\s*(\d+)', r'\1.\2', t)
    # Collapse whitespace
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def is_noise_or_header_footer(text: str, top: int, bottom: int, page_height: int) -> bool:
    # Barcodes, ISBNs, tracking strings
    if re.search(r'^(9[Ttr]|978|ISBN|[0-9a-zA-Z_\-]{12,})', text) and len(text) >= 10:
        return True
    if top > page_height * 0.88 and re.match(r'^[0-9a-zA-Z\s\-_]{12,}$', text):
        return True
    
    # Page numbers at top or bottom margins
    if re.match(r'^[0-9ivxIVX]{1,4}$', text) and (top < page_height * 0.08 or bottom > page_height * 0.92):
        return True
        
    # Running header at top margin (<8% of page)
    if bottom < page_height * 0.08 and len(text) < 60:
        return True
        
    # Running footer at bottom margin (>92% of page)
    if top > page_height * 0.92 and len(text) < 60:
        return True
        
    # Standalone punctuation noise
    if text in ['.', '-', '_', '~', ',', '`', '\'', '"', '|', '/', '\\']:
        return True
        
    return False

def is_heading(text: str, height: int, median_height: int) -> bool:
    if len(text) > 65:
        return False
    # Check if ends with regular sentence ending
    if re.search(r'(습니다|입니다|했다|였다|있다|다|냐|까|요|죠|됨)\s*[.?!]*$', text):
        # Unless it clearly starts with Chapter/TIP
        if not re.match(r'^(제\s*\d+\s*[장절편부]|Chapter|CHAPTER|PART|Part|TIP|Tip)', text):
            return False
    # If it's a numbered list item like "1. 유망한..." with a colon or explanation, it's a list item, not a heading
    if re.match(r'^\d+[\.\)]\s+', text):
        if ':' in text or len(text) > 35:
            return False
    # Starts with section patterns: 1.2.3, 1.2, 14_, 3.1_, Chapter, PART, etc.
    if re.match(r'^(제\s*\d+\s*[장절편부]|\d+\.\d+(\.\d+)?|\d{1,2}_|Chapter|CHAPTER|PART|Part|TIP|Tip)', text):
        return True
    # Number followed by space and short title like "01 LLM이란"
    if re.match(r'^\d{1,2}\s+[가-힣A-Za-z]', text) and len(text) < 30 and ':' not in text:
        return True
    # Significantly taller font and relatively short
    if height > median_height * 1.35 and len(text) < 45 and not re.search(r'[:;,]', text):
        return True
    return False

def is_footnote(text: str, top: int, page_height: int) -> bool:
    if top > page_height * 0.82 and re.match(r'^\d{1,2}\s*(https?://|www\.|[가-힣A-Za-z])', text) and len(text) < 150:
        return True
    return False

def convert_book():
    conn = sqlite3.connect('reader_device.db')
    c = conn.cursor()
    
    book_info = c.execute('SELECT id, title, pages FROM Book LIMIT 1').fetchone()
    if not book_info:
        print("No book found in reader_device.db")
        return
        
    book_id, title, total_pages = book_info
    print(f"Converting book: {title} ({total_pages} pages)")
    
    all_paragraphs = []
    
    for page_num in range(1, total_pages + 1):
        page_row = c.execute('SELECT width, height FROM Page WHERE number=?', (page_num,)).fetchone()
        page_w = page_row[0] if page_row and page_row[0] > 0 else 1639
        page_h = page_row[1] if page_row and page_row[1] > 0 else 2200
        
        blocks = c.execute(
            'SELECT left, top, right, bottom, text, linesJson FROM Block WHERE page=? ORDER BY top, left',
            (page_num,)
        ).fetchall()
        
        if not blocks:
            continue
            
        # Calculate median height
        heights = [b[3] - b[1] for b in blocks]
        median_h = sorted(heights)[len(heights) // 2] if heights else 30
        
        page_paras = []
        
        for b in blocks:
            raw_text = b[4]
            lines = raw_text.split('\n')
            joined_lines = []
            for line in lines:
                l_str = line.strip()
                if not l_str:
                    continue
                if joined_lines and joined_lines[-1].endswith('-'):
                    joined_lines[-1] = joined_lines[-1][:-1] + l_str
                else:
                    joined_lines.append(l_str)
                    
            block_text = clean_text(' '.join(joined_lines))
            if not block_text:
                continue
                
            top, bottom = b[1], b[3]
            block_h = bottom - top
            
            if is_noise_or_header_footer(block_text, top, bottom, page_h):
                continue
                
            heading = is_heading(block_text, block_h, median_h)
            footnote = is_footnote(block_text, top, page_h)
            page_paras.append({
                'page': page_num,
                'text': block_text,
                'is_heading': heading,
                'is_footnote': footnote
            })
            
        all_paragraphs.extend(page_paras)
        
    # Smart paragraph continuation stitching (both intra-page and cross-page)
    def is_list_bullet(text: str) -> bool:
        return bool(re.match(r'^\s*(\d+[\.\)]|[•\-*■▶▷※]|\(\d+\))\s+', text))
        
    def ends_with_terminator(text: str) -> bool:
        return bool(re.search(r'[.?!][\'"”’\)]*\s*$', text))

    common_single_words = {'그', '이', '저', '또', '더', '덜', '잘', '못', '수', '것', '줄', '때', '길', '집', '손', '발', '눈', '귀', '책', '차', '물', '불', '전', '후', '내', '외', '상', '하'}

    stitched_paragraphs = []
    for p in all_paragraphs:
        if not stitched_paragraphs:
            stitched_paragraphs.append(p)
            continue
            
        prev = stitched_paragraphs[-1]
        prev_text = prev['text']
        curr_text = p['text']
        
        # Check if we should merge with previous paragraph
        should_merge = False
        if not prev['is_heading'] and not p['is_heading']:
            if not prev.get('is_footnote') and not p.get('is_footnote'):
                if not is_list_bullet(curr_text):
                    # Don't let a completed list item absorb regular following body
                    if is_list_bullet(prev_text) and (ends_with_terminator(prev_text) or len(curr_text) > 40):
                        should_merge = False
                    elif not ends_with_terminator(prev_text):
                        should_merge = True
                
        if should_merge:
            last_word = prev_text.split()[-1] if prev_text.split() else ''
            if prev_text.endswith('-'):
                prev['text'] = clean_text(prev_text[:-1] + curr_text)
            elif len(last_word) == 1 and re.match(r'^[가-힣]$', last_word) and last_word not in common_single_words:
                prev['text'] = clean_text(prev_text + curr_text)
            else:
                prev['text'] = clean_text(prev_text + ' ' + curr_text)
        else:
            stitched_paragraphs.append(p)
            
    print(f"Total clean paragraphs generated: {len(stitched_paragraphs)}")
    
    # Write to book_converted.txt
    out_paths = [
        r'C:\Users\lmo03\Downloads\book_converted.txt',
        r'D:\work\dev\ebook\book_converted.txt'
    ]
    
    for path in out_paths:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f"도서명: {title}\n")
            f.write("=" * 40 + "\n\n")
            
            current_page = 0
            for p in stitched_paragraphs:
                if p['page'] != current_page:
                    current_page = p['page']
                    # Optional page marker
                    f.write(f"\n[Page {current_page}]\n\n")
                    
                if p['is_heading']:
                    f.write(f"\n### {p['text']}\n\n")
                else:
                    f.write(f"{p['text']}\n\n")
                    
        print(f"Saved to {path}")

if __name__ == '__main__':
    convert_book()
