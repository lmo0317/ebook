# E-Book Fine-Tuning Studio Project Rules & Learned Lessons

이 문서는 Antigravity AI 어시스턴트가 본 프로젝트(`D:\work\dev\ebook`)에서 작업할 때 항상 최우선으로 준수해야 하는 규칙과 과거 시행착오를 바탕으로 한 필수 지침입니다.

---

## 1. 하드웨어 및 LLM 서버 환경 원칙 (CRITICAL)
- **로컬 컴퓨터 (RTX 5080, 16GB VRAM) 전용**:
  - LLM 모델: `edumaster-gemma-4-12b-vision` (Gemma 4 12B QAT Q4_0)
  - API 엔드포인트: `http://127.0.0.1:8092/v1/chat/completions`
  - **절대 금지**: 192.168.219.112 서버(8GB VRAM RTX 2070, 4B 모델)로 12B 모델을 요청하거나 임의 변경하지 말 것.
- **연결 확인**: LLM 작업 전 `http://127.0.0.1:8092/v1/models` 상태를 반드시 확인.

---

## 2. LLM 검수 및 캐시 무결성 규칙 (CRITICAL)
과거 버그: 구버전 캐시(리스트/숫자 키)의 유령 히트로 실제 12B 모델 호출 없이 2초 만에 스킵되어 오탈자가 미교정됨.
- **캐시 포맷 엄격 검증**:
  - 캐시 키는 반드시 `get_text_hash(text)`로 생성된 16자리 MD5 해시여야 함.
  - 캐시 데이터가 `dict`가 아니거나, 해시 키가 일치하지 않으면 **절대로 `return`하여 조기 반환(Early Return)하지 말고 정상 LLM 추론을 수행**해야 함.
- **실시간 검수 로깅 의무화**:
  - 검수 시 백그라운드에서 조용히 끝내지 말고, 어떤 페이지에서 어떤 문단을 고쳤는지 diff 로그(`"탤런 튜껑" -> "앨런 튜링"`)를 반드시 실시간 출력할 것.
- **캐시 초기화 옵션 상시 제공**:
  - GUI 및 스크립트에 캐시 리셋 옵션을 제공하고, 사용자가 요청하거나 프롬프트/모델이 업그레이드되었을 때는 클린 검수를 수행할 것.

---

## 3. 한글 OCR 및 인코딩 처리 규칙
- **정규식 한글 경계**:
  - 파이썬 `\b`는 ASCII 단어 경계만 인식하므로, 한글 조사/어미 접미사(예: `런되올`, `플렉품인`) 매칭 시 `\b` 대신 문맥 확인이나 부정형 룩어헤드를 사용할 것.
- **Windows UTF-8 인코딩**:
  - 파이썬 콘솔 및 파일 I/O 시 항상 `sys.stdout.reconfigure(encoding="utf-8")` 및 `open(..., encoding="utf-8")`을 명시하여 CP949 깨짐 방지.
  - JSON payload 전송 시 `ensure_ascii=False`와 `Content-Type: application/json; charset=utf-8` 명시.

---

## 4. 안드로이드 전자책 앱 (Room DB) 호환성 규칙
- **Room Identity Hash 불일치 금지**:
  - DB 파일(`reader.db`) 빌드 시 `room_master_table`에 `identity_hash = "d5ff8686cb0182fe692967642ccb9c13"`을 반드시 삽입해야 앱 실행 시 크래시가 발생하지 않음.
- **테이블 스키마 일치**:
  - `books`, `pages`, `paragraphs`, `bookmarks` 테이블의 컬럼명과 타입을 Android 엔티티와 100% 일치시킬 것.

---

## 5. 자동 검증 스크립트 실행
- 배포 전 반드시 `python verify_pipeline.py`를 실행하여 캐시 무결성, 로컬 LLM 통신, 핵심 단어 교정 결과를 확인할 것.
