# 이미지 PDF OCR 리더 Android 앱 개발 명세서

- 문서 버전: v1.0
- 대상 플랫폼: Android
- 개발 언어: Kotlin
- UI: Jetpack Compose
- 기본 동작 방식: 완전 오프라인
- LLM 사용: 사용하지 않음
- 핵심 목적: 이미지 기반 PDF를 OCR로 텍스트화하여 휴대폰에서 글꼴, 글자 크기, 줄간격, 여백 등을 자유롭게 변경하며 읽을 수 있도록 제공

---

## 1. 프로젝트 개요

### 1.1 프로젝트명

가칭: **OCR Reflow Reader**

### 1.2 개발 목적

스캔본 또는 이미지로 구성된 PDF는 일반 PDF 리더에서 확대/축소를 반복해야 하므로 휴대폰에서 읽기 불편하다.

본 앱은 이미지 PDF를 페이지 단위로 분석하고 OCR을 수행한 뒤, 인식된 텍스트를 화면 크기에 맞게 다시 배치(Reflow)하여 전자책처럼 읽을 수 있도록 한다.

사용자는 원본 PDF의 글자 크기나 페이지 레이아웃과 관계없이 다음 항목을 자유롭게 변경할 수 있어야 한다.

- 글자 크기
- 글꼴
- 줄간격
- 문단 간격
- 좌우 여백
- 배경색
- 글자색
- 화면 밝기
- 스크롤 방식
- 원본 이미지 / OCR 텍스트 전환

앱의 핵심 가치는 **"스캔 PDF를 휴대폰용 전자책처럼 읽게 해주는 것"**이다.

---

## 2. 핵심 원칙

### 2.1 LLM 미사용

본 앱의 기본 버전은 OpenAI, Gemini, Claude 등 외부 LLM API를 사용하지 않는다.

텍스트 추출과 문서 구조 복원은 다음 요소만으로 구현한다.

1. PDF 페이지 렌더링
2. OCR
3. OCR Bounding Box 좌표
4. 규칙 기반 Reading Order 분석
5. 문단 병합 알고리즘
6. 페이지 헤더/푸터 제거 규칙
7. HTML 또는 구조화 텍스트 기반 Reflow

### 2.2 완전 오프라인

PDF 파일 및 OCR 결과가 외부 서버로 전송되지 않아야 한다.

다음 작업은 모두 기기 내부에서 처리한다.

- PDF 열기
- 페이지 이미지 렌더링
- OCR
- 문단 분석
- OCR 결과 저장
- 검색
- 독서 위치 저장

### 2.3 원본 보존

원본 PDF 파일은 수정하지 않는다.

OCR 결과는 별도의 앱 내부 데이터로 관리한다.

---

# 3. 주요 사용 시나리오

## 3.1 최초 PDF 등록

사용자 흐름:

```text
앱 실행
↓
PDF 추가
↓
Android 파일 선택기 실행
↓
이미지 PDF 선택
↓
책 정보 생성
↓
OCR 시작
↓
OCR 진행률 표시
↓
일부 페이지 OCR 완료 시 즉시 읽기 가능
↓
백그라운드 OCR 계속 진행
```

주의:

Android OS 정책상 장시간 백그라운드 처리는 WorkManager 또는 Foreground Service 정책을 고려하여 구현한다.

---

## 3.2 OCR 텍스트 읽기

```text
라이브러리
↓
책 선택
↓
마지막 읽던 위치로 이동
↓
OCR 텍스트 모드 표시
↓
세로 스크롤
```

텍스트는 화면 너비에 맞게 자동 줄바꿈된다.

---

## 3.3 원본 확인

OCR 오류가 의심되는 경우 사용자는 해당 문단 또는 페이지에서 원본 스캔 이미지를 즉시 확인할 수 있어야 한다.

```text
OCR 텍스트 읽기
↓
문단 길게 누르기
↓
"원본 보기"
↓
해당 문단이 위치한 원본 페이지 표시
```

가능하면 OCR Bounding Box 정보를 이용해 원본 이미지의 해당 영역을 강조한다.

---

# 4. 기능 요구사항

## FR-001 PDF 불러오기

Android Storage Access Framework(SAF)를 사용한다.

지원 확장자:

```text
.pdf
```

필수 기능:

- 파일 선택
- URI 권한 유지
- PDF 페이지 수 확인
- 파일명 저장
- 파일 크기 확인
- 중복 파일 감지

중복 판정 후보:

- URI
- 파일명 + 파일 크기
- SHA-256 해시

초기 버전에서는 파일 크기가 매우 큰 경우 전체 SHA-256 계산을 생략할 수 있다.

---

## FR-002 PDF 페이지 렌더링

Android `PdfRenderer`를 기본 렌더러로 사용한다.

처리 흐름:

```text
PDF
↓
PdfRenderer
↓
Page
↓
Bitmap
↓
전처리
↓
OCR
```

OCR 정확도를 위해 화면 표시용보다 높은 해상도로 렌더링한다.

권장 기준:

- 긴 변 기준 약 1800~3000 px
- 기기 메모리에 따라 동적 조절

한 번에 전체 책을 Bitmap으로 만들지 않는다.

페이지 단위 처리 후 즉시 메모리를 해제한다.

---

# 5. OCR

## FR-003 OCR 엔진

초기 구현 우선순위:

### Option A

Google ML Kit Text Recognition

장점:

- Android 통합이 쉬움
- Bounding Box 제공
- 성능 양호

### Option B

Tesseract

장점:

- 완전 오픈소스
- 다양한 언어 학습 데이터 활용 가능

### Option C

PaddleOCR 계열 로컬 모델

장점:

- 복잡한 OCR에 강한 편
- 향후 고급 버전에서 검토

MVP에서는 Android 개발 난이도를 고려하여 **ML Kit 또는 Tesseract 중 하나**를 우선 적용한다.

OCR 엔진 인터페이스는 교체 가능하도록 추상화한다.

예:

```kotlin
interface OcrEngine {
    suspend fun recognize(bitmap: Bitmap): OcrPageResult
}
```

---

## FR-004 OCR 결과 데이터

OCR 결과는 단순 문자열만 저장하면 안 된다.

최소 저장 정보:

```text
Page
 ├─ TextBlock
 │   ├─ text
 │   ├─ boundingBox
 │   ├─ confidence(optional)
 │   └─ lines
 │
 └─ Line
     ├─ text
     ├─ boundingBox
     └─ elements(optional)
```

Bounding Box 좌표는 원본 OCR Bitmap의 크기와 함께 저장한다.

예:

```json
{
  "page": 15,
  "imageWidth": 2200,
  "imageHeight": 3200,
  "blocks": [
    {
      "text": "예제 문장입니다.",
      "left": 120,
      "top": 340,
      "right": 1950,
      "bottom": 415
    }
  ]
}
```

---

# 6. 이미지 전처리

## FR-005 페이지 전처리

OCR 전에 필요한 경우 다음 처리를 수행한다.

MVP 필수:

- 회전 감지 또는 사용자 수동 회전
- 지나치게 큰 이미지 다운스케일
- 알파 채널 제거

선택 기능:

- grayscale
- contrast enhancement
- threshold
- deskew
- denoise
- margin crop

OpenCV 도입은 MVP 이후 선택 사항으로 둔다.

---

# 7. 문서 레이아웃 분석

## FR-006 Reading Order

OCR 결과를 페이지의 읽기 순서대로 재정렬해야 한다.

단순히 OCR API가 반환한 순서를 신뢰하지 않는다.

기본 알고리즘:

### 1단 문서

Bounding Box의 중심점을 기준으로 정렬:

```text
1. y좌표
2. 같은 줄이면 x좌표
```

### 2단 문서

페이지를 좌우 영역으로 나눈 후:

```text
왼쪽 단 위 → 아래
↓
오른쪽 단 위 → 아래
```

---

## FR-007 단(Column) 자동 감지

Bounding Box들의 x축 분포를 분석한다.

예:

```text
왼쪽 단:
x = 100~950

오른쪽 단:
x = 1200~2050
```

중앙에 일정 폭 이상의 빈 영역이 존재하면 2단 문서로 판단할 수 있다.

MVP:

- 1단
- 2단

지원.

3단 이상은 추후 기능으로 둔다.

---

# 8. 문단 복원

## FR-008 Line → Paragraph 병합

OCR 결과의 줄(Line)을 문단(Paragraph)으로 병합한다.

판정 기준 후보:

- 줄 사이 세로 간격
- 왼쪽 시작 위치 차이
- 오른쪽 끝 위치
- 글자 크기 추정
- 마지막 문자
- 다음 줄 첫 글자
- 들여쓰기

예:

```text
줄1: 이것은 하나의 문단으로
줄2: 이어지는 문장입니다.
```

결과:

```text
이것은 하나의 문단으로 이어지는 문장입니다.
```

---

## FR-009 한국어 줄바꿈 처리

스캔 책 OCR은 실제 문단 중간에서 줄바꿈된다.

따라서 일반 줄바꿈은 공백으로 병합한다.

예:

OCR:

```text
우리는 책을 읽으면서 많은 것을
배울 수 있다.
```

변환:

```text
우리는 책을 읽으면서 많은 것을 배울 수 있다.
```

단, 다음 경우 문단 유지 가능:

- 줄 사이 간격이 큼
- 들여쓰기 존재
- 제목으로 판단됨
- 빈 줄 존재

---

# 9. Header / Footer 제거

## FR-010 반복 영역 감지

페이지 번호, 책 제목, 장 제목 등이 매 페이지 OCR 결과에 들어오는 문제를 방지한다.

페이지 상단/하단 일정 영역을 별도 분석한다.

예:

```text
상위 8%
하위 8%
```

여러 페이지에서 반복적으로 등장하는 짧은 텍스트는 헤더/푸터 후보로 판단한다.

예:

```text
제3장 인간과 사회
127
```

MVP에서는 다음 방식 사용 가능:

- 페이지 상단/하단 영역의 짧은 블록 제거
- 숫자 단독 블록 제거 옵션

사용자가 설정에서:

```text
페이지 번호 제거
헤더 제거
푸터 제거
```

를 켜거나 끌 수 있도록 한다.

---

# 10. OCR 데이터 저장

## FR-011 로컬 DB

Room Database 사용.

주요 Entity:

```text
BookEntity
PageEntity
BlockEntity
ParagraphEntity
ReadingPositionEntity
BookmarkEntity
```

---

## BookEntity

예시 필드:

```text
id
title
fileUri
fileName
fileSize
pageCount
createdAt
lastOpenedAt
ocrStatus
ocrCompletedPages
coverPage
```

---

## PageEntity

```text
id
bookId
pageNumber
width
height
ocrStatus
rotation
```

---

## ParagraphEntity

```text
id
bookId
pageNumber
orderIndex
text
left
top
right
bottom
paragraphType
```

`paragraphType` 후보:

```text
BODY
TITLE
SUBTITLE
CAPTION
FOOTNOTE
UNKNOWN
```

초기 버전에서는 `BODY`, `TITLE`, `UNKNOWN` 정도만 지원해도 된다.

---

# 11. OCR 처리 Queue

## FR-012 페이지 단위 OCR

전체 PDF를 한 번에 처리하지 않는다.

작업 단위:

```text
1 page
```

처리 우선순위:

```text
현재 읽는 페이지
↓
현재 페이지 이후
↓
현재 페이지 이전
↓
나머지 페이지
```

최초 OCR에서는 기본적으로 앞 페이지부터 순차 처리한다.

---

## FR-013 OCR 진행 상태

책별 상태:

```text
NOT_STARTED
PROCESSING
PAUSED
COMPLETED
ERROR
```

UI 예:

```text
OCR 처리 중
142 / 380 페이지
37%
```

---

## FR-014 OCR 중 독서

전체 OCR이 끝날 때까지 기다리지 않고 완료된 페이지부터 읽을 수 있어야 한다.

예:

```text
1~28페이지 OCR 완료
29페이지 OCR 처리 중
```

사용자는 1~28페이지를 즉시 읽을 수 있다.

---

# 12. Reader 화면

## FR-015 Reflow Reader

OCR 텍스트를 PDF 좌표 그대로 배치하지 않는다.

Compose 기반의 세로 흐름형 레이아웃으로 출력한다.

예:

```text
LazyColumn

Paragraph
Paragraph
Paragraph
...
```

본문은 화면 폭에 맞춰 자동 줄바꿈된다.

---

# 13. 독서 설정

## FR-016 글자 크기

범위 예:

```text
12sp ~ 40sp
```

권장 기본:

```text
20sp
```

핀치 제스처를 지원할 수 있다.

예:

```text
Pinch Out → 글자 확대
Pinch In → 글자 축소
```

---

## FR-017 글꼴

초기 제공:

- 시스템 Sans
- 시스템 Serif

추후:

- 사용자 TTF/OTF 추가
- Android 내장 폰트 선택

사용자 폰트를 앱 밖으로 재배포하지 않는다.

---

## FR-018 줄간격

범위 예:

```text
1.0 ~ 2.2
```

기본:

```text
1.5
```

---

## FR-019 문단 간격

예:

```text
0dp ~ 32dp
```

---

## FR-020 좌우 여백

예:

```text
8dp ~ 48dp
```

---

## FR-021 색상 테마

기본 제공:

```text
Light
Dark
Sepia
```

사용자 설정:

- Background Color
- Text Color

---

# 14. 페이지 탐색

## FR-022 페이지 이동

다음 방식 지원:

- 페이지 번호 입력
- 슬라이더
- 목차
- 검색 결과 이동
- 책갈피 이동

OCR 텍스트 기반 Reader에서도 현재 텍스트가 원본 PDF 몇 페이지에서 왔는지 확인할 수 있어야 한다.

---

# 15. 원본 이미지 모드

## FR-023 OCR / 원본 전환

Reader 상단 메뉴:

```text
텍스트
원본
```

텍스트:

```text
OCR Reflow Mode
```

원본:

```text
PDF Page Image Mode
```

원본 모드에서는:

- 확대/축소
- 화면 폭 맞춤
- 페이지 넘김

제공.

---

## FR-024 문단 원본 보기

OCR 문단을 길게 누르면:

```text
원본 보기
복사
검색
책갈피
```

메뉴 표시.

원본 보기를 누르면:

```text
pageNumber
boundingBox
```

정보를 사용해 해당 영역으로 이동한다.

가능하면 해당 Bounding Box를 사각형으로 강조한다.

---

# 16. 검색

## FR-025 전체 텍스트 검색

OCR 완료된 내용을 대상으로 검색한다.

검색 대상:

```text
ParagraphEntity.text
```

Room FTS 사용 권장.

결과:

```text
검색어가 포함된 문장
페이지 번호
```

결과 클릭:

```text
해당 문단으로 이동
```

---

# 17. 책갈피

## FR-026 Bookmark

저장 정보:

```text
bookId
pageNumber
paragraphId
scrollOffset
memo(optional)
createdAt
```

---

# 18. 읽던 위치 저장

## FR-027 Reading Position

자동 저장.

저장 주기:

- 페이지 또는 문단 변경
- 앱 Background 진입
- Reader 종료

저장:

```text
bookId
paragraphId
pageNumber
scrollIndex
scrollOffset
```

재실행 시:

```text
마지막 읽던 위치로 이동
```

---

# 19. 라이브러리 화면

## FR-028 Library

표시:

```text
표지
책 제목
OCR 진행률
마지막 읽은 페이지
마지막 읽은 시간
```

정렬:

```text
최근 읽은 순
추가한 순
제목 순
```

---

# 20. 표지 생성

## FR-029 Cover

PDF 첫 페이지를 저해상도 Bitmap으로 렌더링하여 썸네일 저장.

권장:

```text
WebP / JPEG
```

---

# 21. 책 정보 편집

## FR-030 Metadata

사용자가 변경 가능:

```text
책 제목
저자
메모
```

자동 Metadata 추출은 선택 사항.

---

# 22. OCR 오류 수정

## FR-031 사용자 수정

OCR 텍스트 문단을 편집할 수 있도록 한다.

원본 OCR 결과를 직접 덮어쓰기보다:

```text
originalText
editedText
```

형태로 관리하는 것을 권장.

표시 우선순위:

```text
editedText ?? originalText
```

---

# 23. 내보내기

## FR-032 TXT Export

OCR 결과를 `.txt`로 내보내기.

---

## FR-033 HTML Export

OCR 결과를 HTML로 내보내기.

예:

```html
<h1>제목</h1>

<p>첫 번째 문단...</p>

<p>두 번째 문단...</p>
```

---

## FR-034 EPUB Export

MVP 이후 기능.

내부 OCR 문단 구조를 EPUB으로 변환한다.

장점:

- 다른 전자책 리더에서도 읽기 가능
- 글꼴 크기 변경 가능
- Reflow 가능

---

# 24. 화면 구조

## 24.1 Main Navigation

```text
Library
 ├─ Book Detail
 │   ├─ Read
 │   ├─ OCR Status
 │   └─ Book Settings
 │
 ├─ Search
 └─ Settings
```

---

## 24.2 Library Screen

```text
┌──────────────────────┐
│ 내 책             +  │
├──────────────────────┤
│ [표지] 책 제목 A      │
│        35% 읽음       │
│        OCR 완료       │
├──────────────────────┤
│ [표지] 책 제목 B      │
│        OCR 58%        │
└──────────────────────┘
```

---

## 24.3 Reader Screen

```text
┌──────────────────────┐
│ ← 책 제목      ⋮      │
├──────────────────────┤
│                      │
│  OCR로 변환된         │
│  텍스트가 화면 폭에    │
│  맞춰 자동으로         │
│  표시된다.             │
│                      │
│  사용자가 글자 크기를   │
│  크게 변경해도          │
│  자동 줄바꿈된다.       │
│                      │
└──────────────────────┘
```

---

## 24.4 Reader Settings Bottom Sheet

```text
글자 크기
A-  ─────●─────  A+

글꼴
[Sans] [Serif]

줄간격
좁게 ───●──── 넓게

여백
좁게 ───●──── 넓게

테마
○ Light
○ Sepia
○ Dark
```

---

# 25. 앱 아키텍처

권장:

```text
Clean Architecture
+
MVVM
```

구조 예:

```text
app
├─ presentation
│   ├─ library
│   ├─ reader
│   ├─ search
│   └─ settings
│
├─ domain
│   ├─ model
│   ├─ repository
│   └─ usecase
│
├─ data
│   ├─ db
│   ├─ repository
│   ├─ pdf
│   └─ ocr
│
└─ core
    ├─ image
    ├─ layout
    └─ util
```

---

# 26. 주요 UseCase

예:

```text
ImportPdfUseCase
CreateBookUseCase
RenderPdfPageUseCase
RunOcrUseCase
AnalyzeLayoutUseCase
BuildParagraphsUseCase
RemoveHeaderFooterUseCase
SaveOcrResultUseCase
SearchBookUseCase
UpdateReadingPositionUseCase
ExportTextUseCase
```

---

# 27. OCR Pipeline

전체 Pipeline:

```text
PDF
 ↓
PdfRenderer
 ↓
Bitmap
 ↓
Image Preprocessing
 ↓
OCR
 ↓
OCR Blocks
 ↓
Bounding Box Normalization
 ↓
Column Detection
 ↓
Reading Order
 ↓
Header / Footer Filtering
 ↓
Line Merge
 ↓
Paragraph Detection
 ↓
Text Normalization
 ↓
Room DB
 ↓
Reflow Reader
```

---

# 28. 좌표 정규화

다양한 OCR 해상도를 지원하기 위해 Bounding Box는 정규화 좌표도 저장할 수 있다.

예:

```text
normalizedX = x / imageWidth
normalizedY = y / imageHeight
```

범위:

```text
0.0 ~ 1.0
```

장점:

다른 해상도로 원본 페이지를 표시해도 동일 위치를 쉽게 복원할 수 있다.

---

# 29. Reading Order 알고리즘 예시

## Step 1

Bounding Box 목록 획득.

## Step 2

너무 작은 요소 제거.

예:

```text
높이 < 페이지 높이의 0.3%
```

등은 노이즈 후보.

## Step 3

페이지 Column 분석.

## Step 4

각 Column 내부에서:

```text
top
↓
left
```

순으로 정렬.

## Step 5

유사한 y좌표의 Line 병합.

## Step 6

줄 간격으로 Paragraph 생성.

---

# 30. 제목 감지

MVP에서는 규칙 기반.

조건 예:

- 주변 본문보다 글자 Bounding Box 높이가 큼
- 한 줄 길이가 짧음
- 위/아래 여백이 큼
- 페이지 중앙 정렬

여러 조건을 점수화할 수 있다.

예:

```text
TitleScore

largeFont      +2
centerAligned  +2
shortLine      +1
largeMargin    +2
```

일정 점수 이상:

```text
TITLE
```

---

# 31. Text Normalization

OCR 결과 후처리.

예:

```text
연속 공백 → 한 칸
불필요한 줄바꿈 제거
앞뒤 공백 제거
Unicode 정규화
```

주의:

OCR 텍스트를 임의로 문법 교정하지 않는다.

LLM을 사용하지 않기 때문에 원문을 최대한 보존한다.

---

# 32. 하이픈 처리

영어 책:

```text
inter-
national
```

을

```text
international
```

로 병합하는 규칙을 선택적으로 제공할 수 있다.

한국어에서는 기본적으로 사용하지 않는다.

---

# 33. 이미지 포함 페이지

페이지에 사진/삽화가 포함된 경우:

MVP:

```text
이미지 무시
+
OCR 텍스트만 표시
```

향후:

문단 사이에 원본 이미지 영역을 잘라 삽입.

예:

```text
Paragraph
Paragraph
ImageCrop
Paragraph
```

---

# 34. 표

MVP에서는 표 구조 복원을 지원하지 않는다.

표가 감지되면:

```text
[원본 페이지에서 표 보기]
```

형태의 Placeholder를 제공하는 방식 검토.

고급 버전에서는 Table Recognition 모듈 추가.

---

# 35. 수식

MVP에서는 수식 OCR을 별도로 지원하지 않는다.

수식이 많은 문서는 원본 모드 사용을 권장한다.

향후:

- Math OCR
- LaTeX 변환

등을 별도 모듈로 확장할 수 있다.

---

# 36. 성능 요구사항

## NFR-001 메모리

한 번에 다수 페이지 Bitmap을 메모리에 유지하지 않는다.

권장:

```text
현재 처리 페이지
+
필요한 임시 Bitmap 1~2개
```

처리 완료 후 즉시 recycle 대상 해제.

---

## NFR-002 OCR 처리

OCR은 UI Thread에서 실행하지 않는다.

사용:

```text
Coroutines
Dispatchers.Default
Dispatchers.IO
WorkManager
```

OCR 엔진의 Thread 요구사항에 따라 별도 Dispatcher를 구성할 수 있다.

---

## NFR-003 Reader 성능

책 전체 Paragraph를 한 번에 Compose에 렌더링하지 않는다.

`LazyColumn` 사용.

---

## NFR-004 DB Pagination

대용량 책의 경우:

```text
Paging 3
```

사용을 검토한다.

---

# 37. 저장 공간 관리

OCR 결과가 큰 경우 다음 항목을 분리 관리한다.

```text
원본 PDF
OCR DB
표지
페이지 Cache
```

페이지 렌더링 Bitmap은 영구 저장하지 않는 것을 기본으로 한다.

필요 시 LRU Cache 사용.

---

# 38. 권한

Storage Access Framework 사용을 우선한다.

가능하면 광범위한 저장소 권한을 요청하지 않는다.

---

# 39. 개인정보 / 보안

앱 기본 원칙:

```text
PDF 외부 전송 없음
OCR 결과 외부 전송 없음
사용자 문서 분석 서버 없음
광고 SDK 최소화 또는 미사용
```

설정 화면에 명확히 표시:

> 모든 OCR 처리는 기기에서 수행됩니다.

---

# 40. 오류 처리

## PDF Open Error

```text
PDF를 열 수 없습니다.
파일이 손상되었거나 지원되지 않는 형식일 수 있습니다.
```

---

## OCR Error

특정 페이지 OCR 실패 시 전체 책 처리를 중단하지 않는다.

예:

```text
155페이지 OCR 실패
[다시 시도]
```

상태:

```text
PageOcrStatus.ERROR
```

---

## Out Of Memory

해상도를 낮춰 자동 재시도.

예:

```text
3000px
↓ 실패
2200px
↓ 실패
1600px
```

---

# 41. 설정

Global Settings:

```text
기본 글꼴
기본 글자 크기
기본 줄간격
기본 좌우 여백
테마
화면 켜짐 유지
볼륨키 페이지 이동
OCR 언어
OCR 품질
```

---

# 42. OCR 품질 옵션

예:

### 빠르게

```text
Bitmap 긴 변 1600px
```

### 일반

```text
Bitmap 긴 변 2200px
```

### 고품질

```text
Bitmap 긴 변 3000px
```

기기 RAM에 따라 최대값 제한.

---

# 43. 언어

초기:

```text
한국어
영어
```

향후 OCR 엔진 지원 범위에 따라 추가.

---

# 44. 접근성

지원:

- Android 시스템 글자 크기 고려
- TalkBack 기본 호환
- 충분한 Touch Target
- Dark Mode
- 고대비 테마 옵션

---

# 45. 테스트 대상 문서

최소 다음 문서 유형으로 테스트한다.

```text
A. 한국어 소설 1단 편집
B. 한국어 에세이 1단 편집
C. 한국어 책 2단 편집
D. 영어 소설
E. 오래된 스캔본
F. 기울어진 스캔본
G. 페이지 번호가 존재하는 책
H. 헤더가 반복되는 책
I. 이미지가 많은 책
J. 500페이지 이상 대용량 PDF
```

---

# 46. 성공 기준

MVP 성공 기준:

### OCR

깨끗한 한국어 스캔본에서 본문을 실사용 가능한 수준으로 추출.

### Reading Order

일반 1단 책에서 읽기 순서 오류가 거의 없어야 함.

### Reflow

글자 크기를 16sp → 30sp로 변경해도 정상적으로 자동 줄바꿈.

### Position

앱 종료 후 다시 열어도 마지막 위치 복원.

### Offline

비행기 모드에서도 PDF 등록 후 OCR 및 독서 가능.

---

# 47. MVP 범위

## 반드시 구현

- PDF 가져오기
- PdfRenderer
- 페이지 OCR
- OCR 진행률
- OCR 결과 DB 저장
- 1단 Reading Order
- 기본적인 2단 Reading Order
- 문단 병합
- 세로 Reflow Reader
- 글자 크기
- 글꼴
- 줄간격
- 좌우 여백
- Light / Dark / Sepia
- 마지막 독서 위치 저장
- 원본 PDF 페이지 보기
- 텍스트 검색
- 책갈피
- OCR 실패 페이지 재시도

---

# 48. MVP 제외

초기 버전에서 제외:

```text
LLM
Cloud OCR
계정
서버
동기화
AI 문법 교정
표 구조 복원
수식 OCR
EPUB 고급 레이아웃
자동 번역
TTS 고급 기능
```

---

# 49. 2차 개발 후보

우선순위 후보:

1. EPUB Export
2. 사용자 OCR 텍스트 수정
3. OCR 영역 재지정
4. 이미지/삽화 Reflow 삽입
5. 자동 Deskew
6. OpenCV 기반 페이지 보정
7. 세로쓰기
8. 3단 레이아웃
9. 사용자 폰트
10. TTS
11. OPDS / 전자책 라이브러리
12. OCR 엔진 교체 지원

---

# 50. 3차 개발 후보

선택 기능:

```text
선택적 LLM 후처리
```

단, 기본 OCR Reader와 완전히 분리한다.

사용자가 명시적으로 켰을 때만:

```text
OCR 오탈자 교정
문단 구조 분석
제목 탐지
각주 분리
```

등에 활용할 수 있다.

기본 앱은 LLM 없이 정상 동작해야 한다.

---

# 51. 권장 기술 스택

```text
Language
- Kotlin

UI
- Jetpack Compose
- Material 3

Architecture
- MVVM
- Clean Architecture

Async
- Kotlin Coroutines
- Flow

Database
- Room

Background
- WorkManager

PDF
- Android PdfRenderer

OCR
- ML Kit Text Recognition
  또는
- Tesseract

DI
- Hilt

Preferences
- DataStore

Search
- Room FTS

Image
- Android Bitmap API
- 필요 시 OpenCV

Testing
- JUnit
- AndroidX Test
- Compose UI Test
```

라이브러리의 구체 버전은 개발 시작 시점의 안정 버전을 기준으로 확정한다.

---

# 52. 모듈 구조 제안

향후 규모가 커질 경우:

```text
:app
:core:model
:core:database
:core:pdf
:core:ocr
:core:layout
:core:reader

:feature:library
:feature:reader
:feature:search
:feature:settings
```

MVP 초기에는 단일 app module로 시작하고 이후 분리해도 된다.

---

# 53. 핵심 인터페이스 예시

```kotlin
interface PdfPageRenderer {
    suspend fun render(
        uri: Uri,
        pageNumber: Int,
        targetLongSidePx: Int
    ): Bitmap
}
```

```kotlin
interface OcrEngine {
    suspend fun recognize(
        bitmap: Bitmap,
        language: OcrLanguage
    ): OcrPageResult
}
```

```kotlin
interface LayoutAnalyzer {
    fun analyze(
        page: OcrPageResult
    ): PageLayout
}
```

```kotlin
interface ParagraphBuilder {
    fun build(
        layout: PageLayout
    ): List<Paragraph>
}
```

---

# 54. 데이터 흐름

```text
UI
↓
ViewModel
↓
UseCase
↓
Repository
↓
PDF / OCR / DB
```

Reader:

```text
Room
↓
Flow<List<Paragraph>>
↓
ViewModel
↓
Compose LazyColumn
```

---

# 55. 개발 단계

## Phase 1 — PDF Reader 기반

구현:

- PDF 가져오기
- 책 DB 등록
- 원본 페이지 렌더링
- 원본 Reader

목표:

PDF 로딩 인프라 완성.

---

## Phase 2 — OCR

구현:

- Bitmap → OCR
- OCR Block 저장
- 페이지 OCR 상태 관리
- OCR 진행률

목표:

책 전체 텍스트 추출 가능.

---

## Phase 3 — Reflow

구현:

- Reading Order
- Line Merge
- Paragraph Builder
- Reflow Reader

목표:

스캔 PDF를 큰 글씨로 읽을 수 있음.

---

## Phase 4 — Reader UX

구현:

- Font Size
- Font
- Line Height
- Margin
- Theme
- Reading Position

목표:

실사용 가능한 독서 경험 완성.

---

## Phase 5 — 검색 / 책갈피

구현:

- FTS
- 검색 결과 이동
- Bookmark

---

## Phase 6 — OCR 품질 개선

구현:

- Column Detection
- Header/Footer Removal
- Noise Filtering
- Deskew(optional)

---

# 56. MVP 화면 목록

```text
Splash(optional)

LibraryScreen
PdfImportScreen/System Picker
BookDetailScreen
OcrProgressScreen
ReaderScreen
OriginalPageScreen
SearchScreen
BookmarkScreen
ReaderSettingsSheet
AppSettingsScreen
```

---

# 57. 상태 모델

예:

```kotlin
sealed interface OcrState {

    data object NotStarted : OcrState

    data class Processing(
        val completed: Int,
        val total: Int
    ) : OcrState

    data object Paused : OcrState

    data object Completed : OcrState

    data class Error(
        val message: String
    ) : OcrState
}
```

---

# 58. Reader UX 세부 규칙

Reader를 열면:

1. 저장된 마지막 위치 확인
2. 해당 Paragraph 로드
3. 근처 문단 우선 표시
4. OCR 미완료 영역 진입 시 상태 표시

예:

```text
이 페이지는 아직 OCR 처리 중입니다.

[원본으로 보기]
```

---

# 59. 문단과 원본 연결

모든 Paragraph는 다음 정보를 유지한다.

```text
pageNumber
sourceBoundingBox
```

여러 OCR Line이 합쳐진 경우:

```text
Bounding Box Union
```

계산.

따라서 Paragraph → 원본 위치 이동이 가능해야 한다.

---

# 60. 자동 OCR 전략

책 등록 후 기본 설정:

```text
OCR 자동 시작 = ON
```

사용자 옵션:

```text
전체 OCR
읽는 부분부터 OCR
Wi-Fi 여부 무관
충전 중에만 대량 OCR
```

단, OCR 자체는 네트워크를 사용하지 않는다.

"충전 중" 옵션은 배터리 소모 관리를 위한 것이다.

---

# 61. 배터리 관리

수백 페이지 OCR은 CPU 사용량이 높을 수 있다.

따라서:

- 화면 OFF 상태에서 과도한 병렬 OCR 금지
- 동시 OCR 페이지 수 제한
- 기본 1 page sequential 권장

고성능 기기에서만 제한적 병렬 처리 고려.

---

# 62. 로그

개발 로그:

```text
PDF_OPEN
PDF_RENDER
OCR_START
OCR_SUCCESS
OCR_ERROR
LAYOUT_ANALYZE
PARAGRAPH_BUILD
DB_SAVE
```

Release에서는 사용자 문서의 실제 OCR 텍스트를 로그에 기록하지 않는다.

---

# 63. Crash / Analytics 정책

사용자 문서 내용이 외부 Analytics에 포함되지 않아야 한다.

수집 가능 예:

```text
Android Version
Device Model
Crash Stacktrace
Feature Usage Count
```

수집 금지:

```text
PDF 내용
OCR 텍스트
파일명
페이지 이미지
```

---

# 64. 단위 테스트

필수 테스트:

### ReadingOrderTest

```text
1단 레이아웃 정렬
2단 레이아웃 정렬
```

### ParagraphBuilderTest

```text
연속 줄 병합
빈 줄 문단 분리
들여쓰기 문단 감지
```

### HeaderFooterFilterTest

```text
페이지 번호 제거
반복 Header 제거
```

### TextNormalizerTest

```text
연속 공백
줄바꿈
Unicode
```

---

# 65. 통합 테스트

```text
PDF 선택
→ 1페이지 렌더링
→ OCR
→ DB 저장
→ Reader 출력
```

전체 Pipeline 검증.

---

# 66. 성능 테스트

대상:

```text
100페이지
300페이지
500페이지
1000페이지
```

측정:

```text
OCR 시간
최대 메모리
DB 크기
Reader 스크롤 FPS
앱 시작 속도
검색 속도
```

---

# 67. 주요 리스크

## Risk 1

OCR 정확도.

대응:

- 렌더링 해상도 옵션
- 이미지 전처리
- OCR 엔진 교체 구조

---

## Risk 2

복잡한 페이지 레이아웃.

대응:

- 1단/2단부터 지원
- 원본 보기 제공
- 사용자 수동 Column 설정을 추후 추가

---

## Risk 3

대용량 PDF 메모리.

대응:

- 페이지 단위 렌더링
- Bitmap 즉시 해제
- Cache 제한

---

## Risk 4

OCR 시간이 오래 걸림.

대응:

- 완료 페이지 즉시 읽기
- 진행률 표시
- 중단/재개
- WorkManager 활용

---

# 68. 제품 핵심 차별점

일반 PDF Reader:

```text
PDF 페이지 자체를 확대
```

본 앱:

```text
PDF
↓
OCR
↓
본문 구조 재구성
↓
휴대폰 화면에 맞게 Reflow
```

따라서 사용자는 원본 PDF 글자 크기에 구애받지 않는다.

예:

```text
원본 글자 7pt
```

이어도 Reader에서는:

```text
20sp
24sp
30sp
```

등 원하는 크기로 읽을 수 있다.

---

# 69. 최종 MVP 정의

다음 시나리오가 정상 동작하면 MVP 완료로 본다.

```text
사용자가 스캔 PDF를 선택한다.

↓
앱이 페이지 이미지를 OCR한다.

↓
OCR 결과의 줄과 문단을 정리한다.

↓
사용자가 PDF를 전자책처럼 세로로 읽는다.

↓
사용자가 글자를 크게 만든다.

↓
문장이 자동 줄바꿈된다.

↓
글꼴/줄간격/여백을 변경한다.

↓
OCR이 이상하면 원본 페이지를 바로 확인한다.

↓
앱을 종료했다가 다시 열어도 읽던 위치에서 계속 읽는다.
```

---

# 70. 구현 우선순위 요약

```text
P0
PDF Import
PDF Render
OCR
Room 저장
Reflow Reader
Font Size
Reading Position

P1
Paragraph Reconstruction
2-Column
Original View
Search
Bookmark
Theme

P2
Header/Footer Removal
OCR Edit
Export TXT/HTML
EPUB Export

P3
OpenCV
Advanced Layout
Table
Image Reflow
Optional LLM Correction
```

---

# 71. 결론

이 앱의 핵심은 "PDF Viewer"를 만드는 것이 아니다.

핵심은:

> **이미지 PDF의 본문을 OCR로 추출하고, 원래 페이지 레이아웃에서 분리하여 휴대폰 화면에 맞는 재배치 가능한 텍스트로 읽게 하는 것**

이다.

따라서 개발의 핵심 기술 우선순위는 다음과 같다.

```text
OCR 정확도
>
Reading Order
>
Paragraph Reconstruction
>
Reader UX
>
고급 PDF 기능
```

초기 버전은 LLM이나 서버 없이 충분히 구현 가능하며, 일반적인 1단/2단 스캔 단행본을 주요 대상으로 설정하는 것이 가장 현실적이다.
