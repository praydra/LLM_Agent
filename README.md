# 제조 시스템 연계형 RAG-Agent (MVP)

제조 업무 질문을 **문서형 / DB형 / 복합형**으로 분류합니다. 그다음 작업표준서 검색(RAG)과 사전 정의된 DB Tool 호출을 조합해 답변하는 Python MVP입니다.
일반 LLM은 내부 데이터가 없어 환각 위험이 있고, 단순 RAG는 생산·LOT·품질 같은 정형 데이터를 조회하기 어렵습니다. 이 MVP는 이 두 한계를 보완하는 구조입니다.

## 데이터셋

| 경로 | 내용 |
| --- | --- |
| `sample_data/knowledge_base/` | 샘플 문서 6종: 알람 조치 SOP, 설비 보전 매뉴얼, LOT 추적 기준, MES/ERP 데이터 정책, 생산·품질 지표 기준, QMS 불량 처리 기준 |
| `sample_data/manufacturing_sample.db` | 샘플 SQLite DB(`daily_production`, `lot_history`, `equipment_alarm`, `inventory_status`) |
| `sample_data/schema.sql` | 샘플 DB 스키마 |
| `sample_data/test_questions.json` | 평가 질의 17개(문서형 3, DB형 6, 복합형 5, 한계확인형 3) |

## 소스 구성

```text
manufacturing_rag_agent/
  agent.py         # RAG 검색, DB Tool 호출, 응답 생성을 조합하는 실행 Agent
  router.py        # 키워드·식별자 기반 문서형/DB형/복합형 질문 분류
  documents.py     # 문서 로딩 및 청킹
  vector_store.py  # 표준 라이브러리 기반 TF-IDF 검색기
  tools.py         # 제조 업무 DB Tool(Tool Registry)
  llm.py           # 템플릿 / 로컬 Ollama / OpenAI 응답 생성기
  config.py        # 경로 및 검색 설정
  schema.py        # 공통 데이터 모델
  cli.py           # 명령행 실행 진입점
examples/
  run_demo.py          # 통합 데모
  run_question_set.py  # 평가 질의 세트 실행
```

## 분석 내용

- **질문 라우팅**: 키워드와 식별자(LOT ID, 일자, 라인, 알람 코드 등)로 질문 유형을 분류합니다.
- **RAG 검색**: 외부 패키지 없이 TF-IDF로 관련 문서 청크를 검색합니다(기본 top-k 4).
- **안전한 DB 조회**: 자연어를 SQL로 직접 바꾸지 않습니다. 대신 사전 정의된 Tool만 호출합니다.
  - `get_lot_history`, `get_daily_production`, `get_quality_summary`, `get_equipment_alarms`, `get_inventory_status`
- **응답 생성**: 답변에 문서 근거, 조회 조건, 조회 결과, 한계 사항을 함께 표시합니다. 생성기는 템플릿, Ollama, OpenAI 중에서 고를 수 있습니다.

## 결과

| 질의 유형 | 동작 |
| --- | --- |
| 문서형 | 알람 조치 표준서, 생산·품질 기준 문서를 검색해 근거와 함께 답변 |
| DB형 | 일자·라인·LOT ID 등 조회 조건을 추출해 해당 Tool을 호출하고 수치로 답변 |
| 복합형 | LOT 공정 이력(DB)과 관련 알람 조치 기준(문서)을 하나의 답변으로 통합 |
| 한계확인형 | 근거가 없는 질문은 한계 사항으로 표시 |

## 실행 방법

샘플 DB가 포함되어 있어 바로 실행할 수 있습니다.

```bash
python -m manufacturing_rag_agent.cli --question "LOT-2026-A001 이력과 알람 조치 기준을 알려줘"
python examples/run_demo.py
python examples/run_question_set.py --show-answer
```

로컬 Ollama로 답변을 생성하려면 아래와 같이 실행합니다.

```bash
ollama pull qwen2.5:7b
python -m manufacturing_rag_agent.cli --use-ollama --ollama-model qwen2.5:7b --question "ALM-307 알람 조치 기준을 알려줘"
```

OpenAI를 사용하려면 환경변수 `OPENAI_API_KEY`를 설정합니다.
