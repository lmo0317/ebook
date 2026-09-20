# E-Book Studio & Reflow e-Book Reader

> **스캔본 기술 서적을 고화질 도표 수록 정밀 리플로우 전자책으로 변환하고, 로컬 LLM(Gemma 4 12B)으로 오탈자를 교정하여 안드로이드에서 감상하는 전자책 통합 솔루션**

---

## 📱 프로젝트 구성

본 저장소는 크게 **안드로이드 전자책 리더 앱**과 **파이썬 전자책 변환/교정 스튜디오**로 구성되어 있습니다.

```
ebook/
├── app/                        # Android Jetpack Compose e-Book Reader 앱 소스
│   └── src/main/java/...       # Room DB, Reader, Theme, ViewModel, Compose UI
├── build_perfect_ebook.py      # 완벽 전자책 패키지 빌더 (도표 추출 + LLM 교정 + DB 생성)
├── ebook_studio_gui.py         # GUI 전자책 변환 스튜디오 (CustomTkinter 기반)
├── llm_corrector.py            # 로컬 Gemma 4 12B 연동 실시간 문맥 교정 엔진
├── ocr_engine.py               # EasyOCR (ko+en) GPU 가속 텍스트 추출 모듈
├── book_toc.py                 # 표준 정밀 목차 (117개 세부 섹션 트리 매핑)
├── deploy_to_galaxy.py         # 갤럭시 디바이스(ADB) 원클릭 패키지 배포 스크립트
├── verify_pipeline.py          # 파이프라인 자동 무결성 및 회귀 검증 스위트
├── GEMINI.md                   # AI 어시스턴트 영구 프로젝트 규칙
└── LESSONS_LEARNED.md          # 오류 분석 및 재발 방지 교훈 아카이브
```

---

## 🚀 주요 기능

### 1. Android Jetpack Compose Reader (`app/`)
- **정밀 리플로우 뷰어**: 스캔본 텍스트를 모바일 화면에 맞춰 자유롭게 줄바꿈 및 폰트 크기/줄간격 조절.
- **고화질 도표 뷰어**: 본문 내 도표(`Figure`)를 고해상도로 렌더링하며 터치 시 확대 팝업 지원.
- **표준 목차 점프**: 117개 전체 세부 목차 지원, 터치 시 해당 페이지로 즉시 부드럽게 스크롤.
- **Room SQLite 기반 오프라인 캐싱**: 네트워크 없이 초고속 로딩 및 읽던 위치/북마크 자동 복원.
- **다크 모드 / 테마 커스텀**: 시스템 설정 및 사용자 지정 테마 지원.

### 2. Python e-Book Studio & Local LLM Corrector
- **스마트 문단 결합 (Smart Stitching)**: OCR로 인해 잘린 줄바꿈을 문맥에 맞게 자연스러운 한글 문단으로 재결합.
- **고해상도 도표 자동 크롭**: 캡션 및 여백을 계산하여 원본 PDF에서 DPI 200으로 도표를 깔끔하게 추출.
- **로컬 RTX 5080 Gemma 4 12B 정밀 교정**:
  - `탤런 튜껑` → **`앨런 튜링`**
  - `특껑 테스트` → **`튜링 테스트`**
  - `로전불렉 / 퍼센트론` → **`로젠블랫 / 퍼셉트론`**
  - `런되(runpod)` → **`런팟(RunPod)`**
- **원클릭 디바이스 배포**: `python deploy_to_galaxy.py` 실행 시 갤럭시 스마트폰에 새 DB 및 이미지 자동 동기화.

---

## 🛠️ 사용 방법

### 1. 환경 준비
```bash
# 파이썬 의존성 설치
pip install pymupdf easyocr opencv-python pillow customtkinter
```

### 2. 무결성 검증 스위트 실행
```bash
python verify_pipeline.py
```

### 3. 전자책 변환 및 패키징 실행
- **GUI 모드 실행**:
  ```bash
  python ebook_studio_gui.py
  ```
- **CLI 전체 자동 빌드**:
  ```bash
  python build_perfect_ebook.py
  ```

### 4. 갤럭시 디바이스 배포
```bash
python deploy_to_galaxy.py
```

---

## 📜 라이선스 및 주의사항
본 저장소는 전자책 변환 도구 및 리더기 소스 코드를 포함하고 있으며, 저작권이 있는 도서 원본 PDF 파일은 포함하지 않습니다.
