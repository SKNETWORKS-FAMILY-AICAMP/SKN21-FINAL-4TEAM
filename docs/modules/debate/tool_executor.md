# tool_executor.py 모듈 명세

**파일 경로:** `backend/app/services/debate/tool_executor.py`
**최종 수정:** 2026-03-11

---

## 모듈 목적

토론 에이전트가 발언 생성 중 호출할 수 있는 4가지 서버 측 툴을 실행한다. 외부 API 호출 없이 EC2 로컬에서만 처리하며 추가 비용이 없다.

---

## 주요 상수

| 상수 | 값 | 설명 |
|---|---|---|
| `AVAILABLE_TOOLS` | `["calculator", "stance_tracker", "opponent_summary", "turn_info"]` | 에이전트가 호출 가능한 툴 목록 |
| `_SAFE_OPS` | dict | 계산기 허용 연산자 화이트리스트 (AST 기반) |
| `_ALLOWED_NODES` | tuple | 계산기 허용 AST 노드 타입 |
| `_CLAIM_PREVIEW_LEN` | `300` | stance_tracker/opponent_summary 주장 미리보기 최대 길이 |

---

## 데이터 클래스

### `ToolContext`
툴 실행에 필요한 현재 턴 문맥.

| 필드 | 타입 | 설명 |
|---|---|---|
| `turn_number` | `int` | 현재 턴 번호 |
| `max_turns` | `int` | 최대 턴 수 |
| `speaker` | `str` | 발언자 (`"agent_a"` / `"agent_b"`) |
| `my_previous_claims` | `list[str]` | 내 이전 주장 목록 |
| `opponent_previous_claims` | `list[str]` | 상대방 이전 주장 목록 |
| `my_penalty_total` | `int` | 내 누적 벌점 |

### `ToolResult`
툴 실행 결과.

| 필드 | 타입 | 설명 |
|---|---|---|
| `result` | `str` | 성공 시 결과 문자열 |
| `error` | `str \| None` | 실패 시 에러 메시지 (성공이면 None) |

---

## DebateToolExecutor

생성자: 없음 (상태 없는 클래스)

| 메서드 | 시그니처 | 설명 |
|---|---|---|
| `execute` | `(tool_name: str, tool_input: str, ctx: ToolContext) -> ToolResult` | 툴 이름으로 디스패치. 알 수 없는 툴은 에러 반환 |
| `_run_calculator` | `(expr: str) -> ToolResult` | AST 화이트리스트 기반 수식 안전 계산. 함수 호출·변수·import 금지 |
| `_eval_node` | `(node: ast.expr) -> float \| int` | 재귀적 AST 노드 평가 |
| `_run_stance_tracker` | `(ctx: ToolContext) -> ToolResult` | 내 이전 주장 목록 반환. 자기 모순 감지·일관성 유지용 |
| `_run_opponent_summary` | `(ctx: ToolContext) -> ToolResult` | 상대방 이전 주장 텍스트 정리 반환 (LLM 호출 없음) |
| `_run_turn_info` | `(ctx: ToolContext) -> ToolResult` | 현재 턴 번호·남은 턴·누적 벌점 등 게임 상태 반환 |

### 계산기 허용/금지 사항

| 허용 | 금지 |
|---|---|
| `+`, `-`, `*`, `/`, `**`, `%`, `//` | 함수 호출 (`abs()`, `int()` 등) |
| 정수/실수 상수, 괄호 | 변수, import, 속성 접근 |
| 단항 연산자 (`-x`, `+x`) | 문자열, 리스트, 딕셔너리 등 |

---

## 의존 모듈

| 모듈 | 용도 |
|---|---|
| `ast` | AST 기반 수식 파싱 및 안전 평가 |
| `operator` | 계산기 연산자 함수 매핑 |

---

## 호출 흐름

```
engine.py (_execute_turn)
  → ToolContext 생성 (turn_number, claims, penalties 등)
  → ws_manager.request_turn(tool_executor=DebateToolExecutor(), tool_context=ctx)

ws_manager.py (_handle_tool_request)
  → DebateToolExecutor.execute(tool_name, tool_input, ctx)
  → ToolResult → WebSocket "tool_result" 응답
```

---

## 에러 처리

| 상황 | 반환 |
|---|---|
| 알 수 없는 툴 이름 | `ToolResult(result="", error="Unknown tool '{name}'...")` |
| 빈 수식 | `ToolResult(result="", error="Expression is empty")` |
| 허용되지 않은 AST 노드 | `ToolResult(result="", error="Unsupported operation...")` |
| ZeroDivisionError | `ToolResult(result="", error="Division by zero")` |
| OverflowError | `ToolResult(result="", error="Result is too large...")` |
| 이전 주장 없음 (stance_tracker) | `ToolResult(result="No previous claims recorded yet.")` |
| 상대 주장 없음 (opponent_summary) | `ToolResult(result="Opponent has not made any claims yet.")` |

## 변경 이력

| 날짜 | 버전 | 변경 내용 | 작성자 |
|---|---|---|---|
| 2026-03-11 | v2.0 | 실제 코드 기반으로 전면 재작성 | Claude |
