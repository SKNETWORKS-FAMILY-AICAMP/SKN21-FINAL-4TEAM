# Frontend CLAUDE.md

프론트엔드 개발 시 참고하는 규칙. 루트 `CLAUDE.md`의 공통 원칙과 함께 적용.

## TypeScript 코딩 컨벤션

- TypeScript strict 모드
- 함수형 컴포넌트 + React 19 Server Components 우선
- 포매터: Prettier + ESLint (저장 시 자동 실행), 줄 길이 100자
- 네이밍: camelCase (변수/함수), PascalCase (컴포넌트/타입)
- 라우팅: Next.js App Router, route group으로 사용자(`(user)/`)/관리자(`admin/`) 분리

```json
// .prettierrc
{
  "semi": true,
  "singleQuote": true,
  "tabWidth": 2,
  "printWidth": 100,
  "trailingComma": "all"
}
```

### import 순서

react → next → third-party → @/ → ./ (ESLint `import/order` 자동 강제)

### 컴포넌트 규칙

- 한 파일에 한 컴포넌트, 파일명 = 컴포넌트명 (PascalCase)
- Props 타입: 인라인 `type` 정의. `interface`는 외부 공유 시에만

```typescript
// Good — 컴포넌트 로컬
type Props = { personaId: string; onClose: () => void };
export function PersonaForm({ personaId, onClose }: Props) { ... }

// interface는 lib/에서 공유할 때
export interface ChatMessage { id: string; role: 'user' | 'assistant'; content: string; }
```

### 상태 관리

- Zustand 스토어는 `stores/` 디렉토리에 도메인별 분리
- 컴포넌트 내 전역 상태 직접 정의 금지

### API 호출

- `lib/api.ts`의 래퍼 함수를 통해서만 호출
- 컴포넌트에서 `fetch` 직접 호출 금지
- SSE 스트리밍: `app/api/[...path]/route.ts` 프록시를 통해 FastAPI 백엔드로 전달

### 에러 처리

```typescript
// lib/api.ts — 표준 에러 객체
class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}
```

에러 코드 체계: `DOMAIN_ACTION` (예: `AUTH_ADULT_REQUIRED`, `PERSONA_BLOCKED`)

## 주석 규칙

```typescript
// Good — 비직관적인 UX 결정
// SSE 연결이 끊어져도 3초간 재연결 시도 후 에러 표시 (UX 팀 요청)
const RECONNECT_DELAY = 3000;

// Good — 외부 라이브러리 제약
// pixi-live2d-display는 PixiJS v7만 지원, v8 업그레이드 시 호환성 확인 필요
import { Live2DModel } from 'pixi-live2d-display';

// Bad
// 상태를 설정한다
setState(newState);
```

- JSDoc: 공유 유틸(`lib/`)과 커스텀 훅에만 작성. 컴포넌트는 Props 타입이 문서 역할
- TODO: `// TODO(이름): 설명 — #이슈번호`

## Live2D Integration

### 화면 레이아웃 (연애 시뮬레이션 스타일)

```
┌──────────────────────────────────────┐
│  [전체] 또는 [15+] 또는 [18+]  배지   │  ← 연령등급 배지
│          배경 이미지 레이어            │
│  ┌──────────────────────────────┐    │
│  │      Live2D 캐릭터 모델       │    │
│  │    (감정에 따라 모션 변화)     │    │
│  └──────────────────────────────┘    │
│  ┌──────────────────────────────┐    │
│  │   대화 텍스트 오버레이         │    │
│  │   (SSE 스트리밍 + 타자기 효과) │    │
│  └──────────────────────────────┘    │
│  ┌──────────────────────────────┐    │
│  │   사용자 입력 창              │    │
│  └──────────────────────────────┘    │
└──────────────────────────────────────┘
```

### 기술 구성

- **렌더링:** PixiJS + pixi-live2d-display (Cubism SDK 4)
- **모델 포맷:** Cubism 4 (.model3.json, .moc3, .physics3.json)
- **감정→모션 매핑:** `live2d_models.emotion_mappings` JSONB 기반
- **배경:** 페르소나별 `background_image_url`
- **에셋:** `public/assets/live2d/`, 기본 배경: `public/assets/backgrounds/default.jpg`

### 연령등급 배지

- `[전체]` — 초록색
- `[15+]` — 노란색
- `[18+]` — 빨간색 (adult_verified 아니면 흐리게 + 잠금 아이콘)
- 채팅 화면 상단 상시 표시, 18+ 미인증 시 인증 유도 모달

## 테스트

```bash
cd frontend && npx vitest run       # 컴포넌트 테스트
cd frontend && npx playwright test  # E2E 테스트
```

### 규칙

- 컴포넌트 테스트: Vitest + React Testing Library
- E2E: Playwright (크로스 브라우저)
- 위치: `src/__tests__/` 또는 컴포넌트 옆 `*.test.tsx`
- 네이밍: `describe('컴포넌트명')` + `it('should 동작 설명')`
- API 호출 mock: MSW(Mock Service Worker)

## 커밋 전 체크리스트

```bash
cd frontend && npx eslint .          # TS 린트
cd frontend && npx prettier --check . # TS 포맷
cd frontend && npx vitest run         # 컴포넌트 테스트
```
