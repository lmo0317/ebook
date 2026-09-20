import sqlite3
import hashlib
import time
import os
import re
from PIL import Image, ImageDraw, ImageFont

BOOK_ID = "c0000000-0000-0000-0000-000000000001"
TXT_PATH = r"D:\work\dev\ebook\book_converted.txt"
DB_PATH = r"D:\work\dev\ebook\device_reader_live.db"
COVER_PATH = f"{BOOK_ID}.jpg"
TXT_TARGET_PATH = f"{BOOK_ID}.txt"

def make_cover(output_path):
    width, height = 400, 600
    img = Image.new("RGB", (width, height), color="#1E293B")
    draw = ImageDraw.Draw(img)
    
    # Gradient background
    for y in range(height):
        ratio = y / height
        r = int(0x1E * (1 - ratio) + 0x0F * ratio)
        g = int(0x29 * (1 - ratio) + 0x17 * ratio)
        b = int(0x3B * (1 - ratio) + 0x2A * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
        
    # Frame border
    draw.rectangle([20, 20, width - 20, height - 20], outline="#334155", width=3)
    
    # Draw texts using default font or TrueType if available
    font_path = "C:/Windows/Fonts/malgunbd.ttf"
    if not os.path.exists(font_path):
        font_path = "C:/Windows/Fonts/malgun.ttf"
        
    if os.path.exists(font_path):
        badge_font = ImageFont.truetype(font_path, 20)
        title_font = ImageFont.truetype(font_path, 28)
        author_font = ImageFont.truetype(font_path, 18)
    else:
        badge_font = ImageFont.load_default()
        title_font = ImageFont.load_default()
        author_font = ImageFont.load_default()
        
    # Badge
    draw.text((width // 2, 80), "[ TXT e-Book ]", fill="#38BDF8", font=badge_font, anchor="mm")
    
    # Title
    draw.text((width // 2, 230), "한 권으로 끝내는", fill="#FFFFFF", font=title_font, anchor="mm")
    draw.text((width // 2, 280), "실전 LLM 파인튜닝", fill="#60A5FA", font=title_font, anchor="mm")
    
    # Subtitle
    draw.text((width // 2, 350), "(정제 텍스트 전자책)", fill="#94A3B8", font=badge_font, anchor="mm")
    
    # Author
    draw.text((width // 2, 510), "지은이: 강다솔 | 위키북스", fill="#CBD5E1", font=author_font, anchor="mm")
    
    img.save(output_path, "JPEG", quality=90)
    print(f"Cover generated: {output_path}")

def insert_book():
    with open(TXT_PATH, "r", encoding="utf-8") as f:
        content = f.read()
        
    file_bytes = content.encode("utf-8")
    file_size = len(file_bytes)
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    
    # Write copy as {BOOK_ID}.txt
    with open(TXT_TARGET_PATH, "wb") as f:
        f.write(file_bytes)
        
    make_cover(COVER_PATH)
    
    # Parse paragraphs and pages
    paragraphs_data = []
    # Split by [Page X]
    page_blocks = re.split(r'(?m)^\[Page\s+(\d+)\]\s*$', content)
    
    current_page = 1
    order_num = 1
    
    # First chunk before any [Page X]
    if page_blocks and not page_blocks[0].strip().isdigit():
        header_text = page_blocks[0].strip()
        paras = [p.strip() for p in re.split(r'\n\s*\n', header_text) if p.strip()]
        for p in paras:
            if p.startswith("도서명:") or p.startswith("===="):
                continue
            is_heading = p.startswith("### ")
            clean = re.sub(r'^#+\s*', '', p).strip()
            if clean:
                paragraphs_data.append((BOOK_ID, 1, order_num, clean, None, 50, 50, 950, 1450, "TITLE" if is_heading else "BODY", "BODY"))
                order_num += 1
        page_blocks = page_blocks[1:]
        
    i = 0
    while i < len(page_blocks):
        if page_blocks[i].strip().isdigit():
            page_num = int(page_blocks[i].strip())
            body = page_blocks[i+1] if i+1 < len(page_blocks) else ""
            i += 2
        else:
            page_num = current_page
            body = page_blocks[i]
            i += 1
            
        current_page = page_num
        paras = [p.strip() for p in re.split(r'\n\s*\n', body) if p.strip()]
        for p in paras:
            is_heading = p.startswith("### ")
            clean = re.sub(r'^#+\s*', '', p).strip()
            if clean:
                paragraphs_data.append((BOOK_ID, page_num, order_num, clean, None, 50, 50, 950, 1450, "TITLE" if is_heading else "BODY", "BODY"))
                order_num += 1
                
    total_pages = max([p[1] for p in paragraphs_data]) if paragraphs_data else 348
    now = int(time.time() * 1000)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Remove existing if any
    c.execute("DELETE FROM Book WHERE id=?", (BOOK_ID,))
    c.execute("DELETE FROM Page WHERE bookId=?", (BOOK_ID,))
    c.execute("DELETE FROM Paragraph WHERE bookId=?", (BOOK_ID,))
    c.execute("DELETE FROM Position WHERE bookId=?", (BOOK_ID,))
    c.execute("DELETE FROM Bookmark WHERE bookId=?", (BOOK_ID,))
    
    # Insert Book
    book_title = "한 권으로 끝내는 실전 LLM 파인튜닝 (정제 e-Book)"
    c.execute("""
        INSERT INTO Book (id, title, uri, fileName, size, hash, pages, created, opened, status, done, author, memo, error)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        BOOK_ID,
        book_title,
        f"file:///sdcard/Download/book_converted.txt",
        "book_converted.txt",
        file_size,
        file_hash,
        total_pages,
        now,
        now + 100000, # top of recently opened
        "READY",
        total_pages,
        "강다솔",
        "정제 텍스트 전자책 버전",
        ""
    ))
    
    # Insert Pages
    for p_num in range(1, total_pages + 1):
        c.execute("""
            INSERT INTO Page (bookId, number, width, height, rotation, status, error)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (BOOK_ID, p_num, 1000, 1500, 0, "COMPLETED", ""))
        
    # Insert Paragraphs in batches
    c.executemany("""
        INSERT INTO Paragraph (bookId, page, `order`, original, edited, left, top, right, bottom, type, region)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, paragraphs_data)
    
    conn.commit()
    conn.close()
    
    print(f"Successfully inserted book: {book_title}")
    print(f"Pages: {total_pages}, Paragraphs: {len(paragraphs_data)}")

if __name__ == "__main__":
    insert_book()
