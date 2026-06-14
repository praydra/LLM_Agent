# Manufacturing RAG-Agent MVP

LLM 기반 제조 기업 시스템 연계형 RAG-Agent 프레임워크의 MVP Python 구현입니다.

이 프로젝트는 충북대학교 산업인공지능학과 지능화 캡스톤 #2 프로젝트 자료입니다.

- 일반 LLM의 내부 데이터 부재와 환각 위험을 줄이기 위한 RAG 문서 검색
- 단순 RAG가 처리하기 어려운 생산, LOT, 품질, 설비 이력 질의를 위한 안전한 DB Tool
- 임의 SQL 생성을 피하고 사전 정의된 업무 단위 Tool만 호출하는 Agent 구조
- 질문 유형에 따라 문서형, DB형, 복합형으로 라우팅하는 MVP 라우터

## 폴더 구조

```text
manufacturing_rag_agent/
  agent.py              # RAG 검색, DB Tool 호출, 응답 생성을 조합하는 실행 Agent
  cli.py                # 명령행 데모 실행 진입점
  config.py             # 경로 및 검색 설정
  documents.py          # 문서 로딩 및 청킹
  llm.py                # 템플릿, 로컬 Ollama, 선택적 OpenAI 응답 생성기
  router.py             # 문서형/DB형/복합형 질문 분류
  schema.py             # 공통 데이터 모델
  tools.py              # 제조 업무 DB Tool
  vector_store.py       # 외부 의존성 없는 TF-IDF 기반 MVP 검색기

sample_data/
  knowledge_base/       # 작업표준서, 매뉴얼, 알람 조치 문서 샘플
  schema.sql            # 샘플 제조 DB 스키마
  test_questions.json   # 평가용 질의 세트

scripts/
  build_sample_db.py    # 샘플 SQLite DB 생성

examples/
  run_demo.py           # 통합 데모 실행
  run_question_set.py   # 평가 질의 세트 실행

docs/
  week13_ppt_summary.md # 13주차 PPT 작성용 결과 정리
  week13_ppt_material.md # 슬라이드별 발표 자료 상세본
```

## 빠른 실행

```powershell
python scripts/build_sample_db.py
python -m manufacturing_rag_agent.cli --question "LOT-2026-A001 이력과 알람 조치 기준을 알려줘"
python examples/run_demo.py
python examples/run_question_set.py --show-answer
```

로컬 Ollama를 사용할 경우:

```powershell
ollama serve
ollama pull qwen2.5:7b
python -m manufacturing_rag_agent.cli --use-ollama --ollama-model qwen2.5:7b --question "LOT-2026-A001 이력과 알람 조치 기준을 알려줘"
```

이미 다른 모델을 받아두었다면 `--ollama-model`에 설치된 모델명을 넣으면 됩니다. 예를 들어:

```powershell
python -m manufacturing_rag_agent.cli --use-ollama --ollama-model llama3.1:8b --question "ALM-307 알람 조치 기준을 알려줘"
```

Ollama 서버 주소가 기본값이 아닐 경우:

```powershell
python -m manufacturing_rag_agent.cli --use-ollama --ollama-url http://localhost:11434 --ollama-model qwen2.5:7b --question "MAT-RESIN-A WH-RAW 재고는?"
```

번들 Python을 사용할 경우:

```powershell
& 'C:\Users\jhs40\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts/build_sample_db.py
& 'C:\Users\jhs40\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m manufacturing_rag_agent.cli --question "2026-06-03 LINE-A 생산 현황과 불량률을 알려줘"
```

## 다른 프로그램에 이식하는 방법

1. `manufacturing_rag_agent/` 폴더를 대상 프로젝트로 복사합니다.
2. `sample_data/knowledge_base` 대신 실제 작업표준서, 설비 매뉴얼, 알람 조치 문서를 넣습니다.
3. `tools.py`의 `ManufacturingDatabase`를 실제 MES, ERP, QMS API 또는 사내 DB 조회 코드로 교체합니다.
4. 운영 환경에서는 `router.py`의 키워드 규칙과 식별자 추출 규칙을 현장 용어에 맞게 확장합니다.
5. 로컬 LLM을 붙일 경우 Ollama를 실행하고 `OllamaAnswerGenerator` 또는 CLI의 `--use-ollama` 옵션을 사용합니다.
6. OpenAI API를 사용할 경우 `OPENAI_API_KEY`를 설정하고 `OpenAIAnswerGenerator`를 사용합니다.
7. 사내 LLM을 붙일 경우 `AnswerGenerator` 인터페이스에 맞춰 별도 클래스를 구현하면 됩니다.
8. 권한, 마스킹, 감사 로그는 실제 운영 적용 전에 Tool Registry 앞단 또는 API Gateway에서 반드시 추가해야 합니다.

## MVP 설계 원칙

- 운영 DB 안전성을 위해 자연어를 SQL로 직접 변환하지 않습니다.
- DB 조회는 `get_lot_history`, `get_daily_production`, `get_quality_summary`, `get_equipment_alarms`, `get_inventory_status`처럼 사전에 정의된 Tool만 사용합니다.
- 답변에는 문서 근거, 조회 조건, 조회 결과, 한계 사항을 함께 포함합니다.
- 외부 패키지 없이도 실행되도록 기본 RAG 검색은 표준 라이브러리 기반 TF-IDF로 구현했습니다.
- 실제 답변 생성은 템플릿, 로컬 Ollama, OpenAI 중 선택할 수 있도록 어댑터를 분리했습니다.

## 확장된 샘플 시나리오

- MES: 라인/품목/일자별 생산 실적과 불량률
- QMS: 불량 코드, LOT 보류, 재작업 기준
- 설비: 알람 코드, 조치 이력, 비가동 시간
- ERP: 자재/창고별 재고와 할당 가능 수량
- 평가 질의: 문서형, DB형, 복합형, 한계확인형으로 구성
