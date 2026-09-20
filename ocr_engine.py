"""
OCR Engine & Cache Manager
NVIDIA RTX GPU 가속 (EasyOCR ko+en) 스캔본 PDF 자동 인식 및 캐싱 시스템
"""
import os
import json
import hashlib
import time
import numpy as np
import cv2
import fitz

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

_ocr_reader_instance = None

def get_ocr_reader(gpu=True):
    global _ocr_reader_instance
    if _ocr_reader_instance is None:
        import easyocr
        _ocr_reader_instance = easyocr.Reader(['ko', 'en'], gpu=gpu)
    return _ocr_reader_instance

def is_scanned_pdf(doc, sample_pages=5):
    """PDF 첫 몇 페이지에 디지털 텍스트가 없는 스캔본인지 감지"""
    total_text = sum(len(doc[p].get_text().strip()) for p in range(min(sample_pages, len(doc))))
    return total_text < 20

def get_cache_path(pdf_path):
    stat = os.stat(pdf_path)
    key = hashlib.md5(f"{pdf_path}_{stat.st_size}_{stat.st_mtime}".encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"ocr_cache_{key}.json")

def load_cache(cache_path):
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cache(cache_path, cache_dict):
    try:
        temp_path = cache_path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(cache_dict, f, ensure_ascii=False)
        if os.path.exists(cache_path):
            os.remove(cache_path)
        os.rename(temp_path, cache_path)
    except Exception as e:
        print(f"Failed to save cache: {e}")

def get_page_blocks(doc, page_idx, ocr_cache=None, reader=None, dpi=135):
    """
    페이지 블록 추출:
    - 텍스트 레이어가 있는 경우 get_text('blocks') 사용
    - 스캔본인 경우 캐시 확인 -> 없으면 GPU OCR 수행 후 캐시 저장
    반환값: list of [bx0, by0, bx1, by1, text, 0, 0, conf] (72 DPI PDF 좌표계)
    """
    page = doc[page_idx]
    raw_blocks = page.get_text("blocks")
    if raw_blocks:
        return raw_blocks, False

    p_key = str(page_idx + 1)
    if ocr_cache is not None and p_key in ocr_cache:
        return ocr_cache[p_key], True

    if reader is None:
        reader = get_ocr_reader(gpu=True)

    # Render for OCR
    pix = page.get_pixmap(dpi=dpi)
    scale = 72.0 / float(dpi)
    results = reader.readtext(pix.tobytes("png"), batch_size=32)

    blocks = []
    for poly, text, conf in results:
        t = text.strip()
        if not t:
            continue
        xs = [p[0] * scale for p in poly]
        ys = [p[1] * scale for p in poly]
        blocks.append([min(xs), min(ys), max(xs), max(ys), t, 0, 0, float(conf)])

    blocks.sort(key=lambda b: b[1])

    if ocr_cache is not None:
        ocr_cache[p_key] = blocks

    return blocks, True

def is_caption_text(text: str) -> bool:
    import re
    t = text.strip().replace('\n', ' ')
    m = re.match(r'^(?:그림|Figure)\s*(\d+)[\.\-_ ]*(\d+)?(.*)', t, re.IGNORECASE)
    if not m:
        return False
    rest = m.group(3).strip()
    # If immediately followed by Korean particle, it is a body text referencing a figure
    if re.match(r'^(?:[은는이가을를과와도]|에서|처럼|과\s*같이|참조)\b', rest):
        return False
    if re.search(r'(습니다|입니다|했다|였다|있다|한다|된다|다|냐|까|요|죠|됨)\s*[.?!]*$', t):
        return False
    if len(t) > 60:
        return False
    return True

def crop_diagram_highres(page, crop_box, save_path, dpi=200):
    """
    PyMuPDF의 clip 기능을 이용하여 crop_box 영역만 200 DPI로 초고속 렌더링 후
    OpenCV를 통해 사방의 불필요한 백색 여백을 정밀 트리밍하여 저장합니다.
    """
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

