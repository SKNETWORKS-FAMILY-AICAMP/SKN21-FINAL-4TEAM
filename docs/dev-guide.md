# 개발자 가이드

> AI 에이전트 토론 플랫폼 — 팀 온보딩 & 워크플로우 가이드
>
> 작성일: 2026-03-11
> 대상: 신규 합류 팀원 (4인 팀)

---

## 목차

1. [빠른 시작](#1-빠른-시작)
2. [브랜치 & 워크플로우](#2-브랜치--워크플로우)
3. [테스트](#3-테스트)
4. [스테이징 & 배포](#4-스테이징--배포)
5. [GitHub 설정](#5-github-설정-리더용)
6. [커밋 컨벤션](#6-커밋-컨벤션)
7. [역할별 개발 가이드](#7-역할별-개발-가이드)
8. [FAQ](#8-faq)

---

## 1. 빠른 시작

### 전제 조건

| 도구 | 버전 | 확인 방법 |
|---|---|---|
| Python | 3.12 이상 | `python --version` |
| Node.js | 18 이상 | `node --version` |
| Docker Desktop | 최신 | `docker --version` |
| Git | 최신 | `git --version` |

### 최초 세팅 (1회만)

```bash
# 1. 저장소 클론
git clone <repo-url>
cd Project_New

# 2. 환경 변수 파일 생성
cp .env.development.example .env.development
```

`.env.development` 파일을 열어 다음 값을 채운다. 나머지는 기본값으로 동작한다.

```ini
# 필수로 채워야 하는 값
OPENAI_API_KEY=sk-...          # 검토/판정 LLM 호출용 (팀 공용 키를 리더에게 받을 것)
SECRET_KEY=<임의 문자열>       # JWT 서명 키 (python -c 'import secrets; print(secrets.token_urlsafe(32))')
DEBATE_ENABLED=true
```

```bash
# 3. 원커맨드 실행 (DB, Redis, 백엔드, 프론트엔드 전부 자동 실행)
bash scripts/setup.sh
```

스크립트가 완료되면 아래 주소로 접근할 수 있다.

| 접속 주소 | 설명 |
|---|---|
| http://localhost | nginx 통합 (프론트 + API 프록시) |
| http://localhost:3000 | Next.js 직접 |
| http://localhost:8000 | FastAPI 직접 (Swagger UI: `/docs`) |

### 일상적인 기동/종료

```bash
# 기동 (이미 venv와 node_modules가 있으면 빠르게 재기동)
bash scripts/setup.sh

# 종료
bash scripts/setup.sh --stop

# 의존성이 바뀐 경우 (requirements.txt, package.json 변경 후)
bash scripts/setup.sh --update-deps
```

### 로컬 관리자 계정 생성

DB 초기화 후 관리자 계정이 필요하면:

```bash
cd backend
.venv/Scripts/python.exe ../scripts/create_test_admin.py   # Windows
# 또는
.venv/bin/python ../scripts/create_test_admin.py            # macOS/Linux
```

---

## 2. 브랜치 & 워크플로우

### 브랜치 구조

```
feature/xxx ─┐
feature/yyy ─┼──→  develop  ──→  main  (운영 배포, 포트 80)
fix/zzz ─────┘
                ↑
           스테이징 자동 배포 (포트 8080)
```

### 일반 개발 흐름

```bash
# 1. develop 최신화
git switch develop
git pull origin develop

# 2. 작업 브랜치 생성
git switch -c feature/토론-검색-필터

# 3. 작업 후 커밋 (컨벤션은 6절 참고)
git add backend/app/...
git commit -m "feat: 토론 토픽 검색 필터 추가"

# 4. push 후 PR 생성
git push origin feature/토론-검색-필터
# GitHub에서 base: develop 으로 PR 작성

# 5. 리뷰어 1명 지정 → 승인 → Squash and Merge
```

### PR 규칙 요약

| 상황 | base 브랜치 | 승인 필요 | CI |
|---|---|---|---|
| 기능/버그 수정 | `develop` | 리뷰어 1명 | pytest + vitest + 린트 통과 필수 |
| 스테이징 → 운영 | `main` | 리더 승인 | 동일 |
| 긴급 핫픽스 | `main` | 리더 승인 | 동일 |

### 긴급 핫픽스

운영 장애 시 `develop`을 기다릴 수 없을 때:

```bash
git switch main
git pull origin main
git switch -c hotfix/결제-오류

# 수정 후
git push origin hotfix/결제-오류
# GitHub에서 base: main PR → 리더 승인 → 머지

# main 머지 후 반드시 develop에도 백머지
git switch develop
git merge main
git push origin develop
```

### 금지 사항

- `main`, `develop` 브랜치에 직접 push 금지 (브랜치 보호로 막혀 있음)
- 리뷰어 없이 자기 PR을 직접 승인 및 머지 금지

---

## 3. 테스트

### 테스트 종류

| 종류 | 위치 | 실행 시간 | 인프라 필요 |
|---|---|---|---|
| 백엔드 단위 | `backend/tests/unit/` | ~30초 | 불필요 (mock) |
| 프론트엔드 단위 | `frontend/src/**/*.test.tsx` | ~20초 | 불필요 |
| 백엔드 통합 | `backend/tests/integration/` | ~2분 | DB + Redis 필요 |
| E2E | `frontend/e2e/*.spec.ts` | ~5분 | 서버 실행 필요 |

### 빠른 테스트 (단위 테스트만)

```bash
# 백엔드 단위 테스트 (252개)
cd backend
.venv/Scripts/python.exe -m pytest tests/unit/ -v          # Windows
.venv/bin/python -m pytest tests/unit/ -v                  # macOS/Linux

# 특정 파일만 실행
.venv/Scripts/python.exe -m pytest tests/unit/services/test_debate_engine.py -v

# 프론트엔드 단위 테스트 (36개)
cd frontend
npm run test
```

### 통합 테스트 (DB/Redis 필요)

```bash
# 테스트용 인프라 시작 (포트 5433, 6380 — 로컬 개발 DB와 충돌 없음)
docker compose -f docker-compose.test.yml up -d

# 통합 테스트 실행
cd backend
.venv/Scripts/python.exe -m pytest tests/integration/ -v   # Windows

# 종료
docker compose -f docker-compose.test.yml down
```

### 전체 테스트 한번에 (run-tests.sh)

```bash
# 백엔드 단위 + 통합 테스트
bash scripts/run-tests.sh --backend-only

# 프론트엔드 단위 테스트
bash scripts/run-tests.sh --frontend-only

# E2E 포함 전체
bash scripts/run-tests.sh --all
```

### E2E 테스트

```bash
cd frontend

# 전체 실행
npx playwright test

# 특정 파일만
npx playwright test e2e/debate-list.spec.ts

# 브라우저 화면 보면서 실행
npx playwright test --headed

# 마지막 실패 테스트만 재실행
npx playwright test --last-failed
```

### PR 올리기 전 로컬 체크리스트

```bash
# 백엔드
cd backend && .venv/Scripts/python.exe -m pytest tests/unit/ -v && .venv/Scripts/python.exe -m ruff check .

# 프론트엔드
cd frontend && npx eslint . && npx prettier --check . && npm run test
```

CI에서 실패하면 머지가 차단된다. 로컬에서 먼저 통과시키고 push하는 것이 효율적이다.

---

## 4. 스테이징 & 배포

### 환경 구성

| 환경 | 접속 주소 | 브랜치 | DB |
|---|---|---|---|
| 로컬 | http://localhost | — | 로컬 Docker |
| 스테이징 | http://EC2_IP:8080 | `develop` | chatbot_staging 볼륨 |
| 운영 | http://EC2_IP | `main` | chatbot_prod 볼륨 |

스테이징과 운영은 같은 EC2에서 Docker 컨테이너로 분리되어 실행된다. DB 볼륨이 완전히 분리되어 있으므로 스테이징 테스트가 운영 데이터에 영향을 주지 않는다.

### 스테이징 배포 (자동)

`develop` 브랜치에 push(또는 PR 머지)하면 GitHub Actions CI가 자동으로 실행된다.

```
develop push
  → GitHub Actions CI
      → pytest (단위) + vitest + 린트
      → 통과 시 EC2 ssh → git pull → docker compose build + up (포트 8080)
  → 약 5~10분 소요
```

브라우저에서 `http://EC2_IP:8080`으로 접속해 시각적 검증을 한다.

### 운영 배포 (반자동)

```
develop → main PR 생성
  → 리더 코드 리뷰 + 승인
  → Squash and Merge
      → GitHub Actions CI
          → 통과 시 EC2 ssh → docker compose build + up (포트 80)
  → 약 5~10분 소요
```

운영 배포는 리더 승인 없이 진행할 수 없다.

### EC2 상태 확인 (팀원 공통)

EC2 IP를 리더에게 확인한 후 (Elastic IP 없음, 재시작 시 변경):

```bash
# 운영 컨테이너 상태
ssh -i ~/Downloads/chatbot-key.pem ubuntu@<EC2_IP> \
  "cd /opt/chatbot && docker compose -f docker-compose.prod.yml ps"

# 운영 백엔드 로그
ssh -i ~/Downloads/chatbot-key.pem ubuntu@<EC2_IP> \
  "cd /opt/chatbot && docker compose -f docker-compose.prod.yml logs --tail=100 backend"

# 스테이징 로그
ssh -i ~/Downloads/chatbot-key.pem ubuntu@<EC2_IP> \
  "cd /opt/chatbot && docker compose -f docker-compose.staging.yml logs --tail=100 backend"
```

SSH 키 파일은 리더에게 받아서 `~/Downloads/chatbot-key.pem`에 저장하고 권한을 조정한다.

```bash
chmod 400 ~/Downloads/chatbot-key.pem
```

### 배포 시 주의사항

Docker 이미지 빌드 방식으로 배포된다. 소스코드는 이미지에 직접 복사(`COPY`)되므로, **파일만 scp로 올리고 컨테이너를 재시작하는 방식은 반영되지 않는다.** GitHub Actions가 자동으로 올바른 방법(`build + up`)으로 처리한다.

---

## 5. GitHub 설정 (리더용)

이 절은 최초 한 번만 진행한다. 팀원은 읽기만 하면 된다.

### EC2 초기 세팅

```bash
# EC2 SSH 접속
ssh -i ~/Downloads/chatbot-key.pem ubuntu@<EC2_IP>

# 저장소 클론
sudo mkdir -p /opt/chatbot
sudo chown ubuntu:ubuntu /opt/chatbot
git clone <repo-url> /opt/chatbot
cd /opt/chatbot

# 스테이징 환경 변수 설정
cp .env.staging.example .env.staging
# 아래 항목 필수 입력
# POSTGRES_PASSWORD, REDIS_PASSWORD, SECRET_KEY, OPENAI_API_KEY
# CORS_ORIGINS=["http://EC2_IP:8080"]

# 운영 환경 변수 설정
cp .env.production.example .env.production
# CORS_ORIGINS=["http://EC2_IP", "https://도메인"]

# 최초 배포
sudo bash deploy.sh fresh staging
sudo bash deploy.sh fresh production
```

### GitHub Secrets 설정

GitHub 저장소 → Settings → Secrets and variables → Actions → New repository secret:

| Secret 이름 | 값 |
|---|---|
| `PROD_EC2_IP` | EC2 퍼블릭 IP |
| `PROD_SSH_PRIVATE_KEY` | `~/.ssh/chatbot-prod.pem` 파일 내용 전체 (`cat ~/.ssh/chatbot-prod.pem`) |

### GitHub 브랜치 보호 설정

Settings → Branches → Add branch protection rule:

**main 브랜치:**
- Require a pull request before merging: 체크
- Required approvals: 1
- Require status checks to pass before merging: 체크
  - 필수 체크: `backend-unit-test`, `frontend-test`, `lint`
- Block force pushes: 체크
- Include administrators: 체크 (리더도 직접 push 불가)

**develop 브랜치:**
- Require a pull request before merging: 체크
- Required approvals: 1 (Self-approval 허용 여부는 팀 합의에 따름)
- Require status checks to pass before merging: 체크
  - 필수 체크: `backend-unit-test`, `frontend-test`, `lint`
- Block force pushes: 체크

---

## 6. 커밋 컨벤션

[Conventional Commits](https://www.conventionalcommits.org/) 규칙을 따른다.

### 형식

```
<type>: <설명>

[본문 — 선택]
[푸터 — 선택, 이슈 참조]
```

### 타입 목록

| 타입 | 사용 시점 |
|---|---|
| `feat` | 새로운 기능 추가 |
| `fix` | 버그 수정 |
| `refactor` | 기능 변경 없는 코드 구조 개선 |
| `docs` | 문서 변경 |
| `test` | 테스트 추가/수정 |
| `chore` | 빌드, 설정, 패키지 변경 |
| `perf` | 성능 개선 |

### 예시

```
feat: 토론 매치 예측투표 API 추가
fix: 토픽 큐 등록 시 중복 에이전트 허용 버그 수정
refactor: debate_engine 턴 루프 asyncio.gather로 병렬화
docs: 백엔드 개발자 가이드 LLM 호출 규칙 추가
test: DebatePromotionService 승급전 시리즈 엣지 케이스 테스트 추가
chore: requirements.txt httpx 버전 업데이트
```

### PR 제목

커밋 메시지와 동일한 형식을 사용한다. Squash and Merge 시 PR 제목이 커밋 메시지가 된다.

---

## 7. 역할별 개발 가이드

### 백엔드 개발자

**비즈니스 로직 위치:** `backend/app/services/debate/`

라우터(`api/`)는 입력 검증과 HTTP 응답 직렬화만 담당한다. DB 쿼리와 비즈니스 로직은 서비스 계층에 작성한다.

```python
# 올바른 라우터 패턴
@router.post("/{id}/queue")
async def join_queue(id: str, body: QueueJoinRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await DebateMatchingService(db).join_queue(user, id, body.agent_id)

# 금지 패턴 — 라우터에서 직접 DB 쿼리
@router.post("/{id}/queue")
async def join_queue(id: str, db: AsyncSession = Depends(get_db)):
    entry = await db.execute(select(DebateMatchQueue).where(...))  # 금지
```

**LLM 호출:** 반드시 `services/llm/inference_client.py`의 `InferenceClient`를 통한다. `openai.AsyncOpenAI()` 등 provider SDK를 서비스에서 직접 인스턴스화하지 않는다.

**환경 변수:** `os.getenv()` 직접 호출 금지. `from app.core.config import settings`로만 접근한다.

**에러 처리:** `core/exceptions.py`의 `NotFoundError`, `ForbiddenError`, `ConflictError`를 사용한다. FastAPI 전역 핸들러가 자동으로 HTTP 응답으로 변환한다.

**DB 마이그레이션:** 모델 변경 후 반드시 Alembic 마이그레이션을 생성하고 PR에 포함한다.

```bash
cd backend
alembic revision --autogenerate -m "add_새기능_설명"
alembic upgrade head
```

더 자세한 내용은 [백엔드 개발자 가이드](dev-guide/backend.md)를 참고한다.

---

### 프론트엔드 개발자

**API 호출:** `fetch`를 컴포넌트에서 직접 호출하지 않는다. 반드시 `lib/api.ts`의 래퍼를 사용한다.

```typescript
import { api, ApiError } from '@/lib/api';

// GET
const data = await api.get<ResponseType>('/endpoint');

// POST
const result = await api.post<ResponseType>('/endpoint', { field: 'value' });
```

**상태 관리:** `stores/` 디렉토리의 Zustand 스토어를 사용한다. 컴포넌트 내부에서 `create()`로 로컬 스토어를 만들지 않는다.

```typescript
// 올바른 방법 — 최소 슬라이스만 구독
const turns = useDebateMatchStore((s) => s.turns);

// 금지 — 전체 스토어 구독 (고빈도 SSE 업데이트 시 성능 저하)
const store = useDebateStore();
```

**도메인 타입:** `src/types/debate.ts`에 중앙 정의한다. 컴포넌트별로 중복 타입을 정의하지 않는다.

**활성 버튼 스타일:** `bg-primary text-white`. `bg-primary/10 text-primary`는 호버 상태에만 쓴다.

더 자세한 내용은 [프론트엔드 개발자 가이드](dev-guide/frontend.md)를 참고한다.

---

## 8. FAQ

**Q. `setup.sh`를 실행했는데 DB 연결 오류가 난다.**

`.env.development`의 `DATABASE_URL`에 적힌 비밀번호와 `POSTGRES_PASSWORD`가 일치하는지 확인한다. Docker 볼륨이 다른 비밀번호로 초기화된 경우 볼륨을 삭제하고 재시작해야 한다.

```bash
docker compose down -v   # 볼륨 포함 삭제 (데이터 전부 사라짐, 로컬 개발 환경에서만)
bash scripts/setup.sh
```

---

**Q. `DEBATE_ENABLED=true`로 설정했는데 토론 API가 404를 반환한다.**

백엔드 서버를 재시작해야 한다. `debate_enabled` 설정은 앱 시작 시 라우터 등록 여부를 결정하므로, 환경 변수 변경 후 반드시 서버를 재시작한다.

```bash
bash scripts/setup.sh --stop
bash scripts/setup.sh
```

---

**Q. alembic 마이그레이션 충돌이 발생했다.**

두 브랜치에서 동시에 마이그레이션을 생성하면 같은 `down_revision`을 가리키는 파일이 두 개 생긴다. 다음 순서로 해결한다.

```bash
# 현재 상태 확인
alembic heads

# 최신 revision을 내 마이그레이션 파일의 down_revision으로 수정 후
alembic upgrade head
```

충돌 방지를 위해 마이그레이션이 필요한 작업은 팀에 미리 공유하는 것이 좋다.

---

**Q. PR을 올렸는데 CI가 실패했다.**

GitHub Actions 탭에서 실패한 단계를 확인한다. 대부분 아래 중 하나다.

- **pytest 실패:** 로컬에서 `pytest tests/unit/ -v`로 재현 후 수정
- **vitest 실패:** 로컬에서 `cd frontend && npm run test`로 재현 후 수정
- **ruff 린트:** `cd backend && .venv/Scripts/python.exe -m ruff check . --fix`로 자동 수정
- **ESLint:** `cd frontend && npx eslint . --fix`로 자동 수정 가능한 것 수정 후 나머지 수동 수정

---

**Q. 스테이징 배포가 됐는지 어떻게 확인하나.**

GitHub Actions 탭에서 `develop` 브랜치의 워크플로우 실행 결과를 확인한다. 성공 상태면 http://EC2_IP:8080에서 확인한다. EC2 IP는 리더에게 확인한다 (Elastic IP 없음, 재시작 시 변경).

---

**Q. 로컬에서 관리자 기능을 테스트하고 싶다.**

`scripts/create_test_admin.py`로 `admin` 또는 `superadmin` 역할의 계정을 생성할 수 있다. 이미 생성한 일반 계정의 역할을 변경하려면 DB에서 직접 수정한다.

```bash
# docker를 통해 psql 접속
docker compose exec db psql -U chatbot -d chatbot

-- 역할 변경
UPDATE users SET role = 'admin' WHERE login_id = '내아이디';
```

---

**Q. 새로운 LLM 모델을 에이전트에 추가하고 싶다.**

`llm_models` 테이블에 레코드를 INSERT하면 된다. 관리자 대시보드(`/admin/models`)에서 UI로 추가하거나, 백엔드 관리자 API(`POST /api/admin/models`)를 직접 호출한다. `superadmin` 권한이 필요하다.

---

**Q. EC2 IP가 바뀌었다.**

EC2를 재시작하면 퍼블릭 IP가 변경된다. 바뀐 IP를 확인해 다음을 업데이트해야 한다.

1. GitHub Secrets의 `EC2_HOST` 값 수정
2. 운영/스테이징 `.env`의 `CORS_ORIGINS` 값 수정 (EC2에서 직접 편집)
3. 팀원에게 새 IP 공유

---

## 변경 이력

| 날짜 | 내용 |
|---|---|
| 2026-03-11 | 최초 작성 |
