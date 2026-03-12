# 개발/운영 서버 분리 및 배포 자동화 계획

**작성일:** 2026-03-11
**대상 규모:** 프로토타입 (동시 접속 10명 이하)
**목표 비용:** 운영 ~$15/월 유지, 개발 추가 비용 최소화

---

## 현황 요약

| 항목 | 현재 상태 | 문제점 |
|---|---|---|
| 배포 방식 | tar+SSH 파이프 전체 파일 전송 | 느림, 오류 많음 |
| 개발 환경 | 운영 서버에서 직접 테스트 | 운영 장애 위험 |
| EC2 IP | Elastic IP 없음 | 재시작 시 IP 변경 |
| SSH 키 | `~/Downloads/` 에 단일 보관 | 손상 시 접속 불가 |
| 마이그레이션 | 운영 DB 직접 적용 | 검증 단계 없음 |

---

## 1. 개발 서버 구성 방안

### 결론: 로컬 Docker (현재와 동일 방식 유지)

별도 EC2 개발 서버를 만들지 않고, **로컬 PC의 `scripts/setup.sh`가 개발 환경** 역할을 한다.

이미 `docker-compose.yml` (로컬용) + `scripts/setup.sh` (원커맨드 기동)이 갖추어져 있으므로 별도 인프라 비용 없이 운용 가능하다.

**추가로 필요한 것:**

```
로컬 개발 흐름:
  bash scripts/setup.sh          ← 로컬 DB+Redis+uvicorn+Next.js
  → 코드 수정/테스트
  → git commit & push main
  → EC2에서 git pull & docker build (아래 2번 참조)
```

별도 EC2 개발 서버가 필요한 시점: 팀원이 2명 이상 동시 작업하거나, GPU 추론 테스트가 로컬 불가능할 때. 현재는 불필요.

---

## 2. 운영 서버 git 배포 자동화

### 2-1. EC2에 git 설치 및 GitHub 연결

EC2 접속 후 1회 실행:

```bash
# EC2 접속
ssh -i ~/Downloads/chatbot-key.pem ubuntu@<EC2_IP>

# git 설치
sudo apt-get update && sudo apt-get install -y git

# /opt/chatbot을 git 저장소로 전환
cd /opt/chatbot
git init
git remote add origin https://github.com/sbpark2930-ui/Project_New.git

# 현재 파일들을 git이 추적하게 연결 (초기 1회)
git fetch origin main
git checkout -b main --track origin/main
# 이미 파일이 있으므로 force checkout
git checkout -f main
```

이후부터 배포는 git pull + docker build 조합으로 동작.

### 2-2. GitHub 인증 (Personal Access Token 방식)

EC2에서는 SSH 키 대신 PAT(Personal Access Token)을 쓰는 것이 관리가 단순하다.

```bash
# EC2에서 한 번만 실행
git config --global credential.helper store
# 최초 git pull 시 username + PAT 입력 → ~/.git-credentials에 저장됨

# PAT 발급: GitHub → Settings → Developer settings → Personal access tokens (Fine-grained)
# 권한: Contents(read), Metadata(read) 만 부여
```

### 2-3. 개선된 배포 스크립트 (로컬에서 실행)

현재 `deploy.sh`는 EC2 내부에서 실행하는 구조. 로컬 Windows에서 SSH로 원격 실행하는 래퍼를 추가한다.

**`scripts/remote-deploy.sh` (로컬에서 실행):**

```bash
#!/bin/bash
# 로컬에서 실행: bash scripts/remote-deploy.sh [prod|dev]
# 전제: EC2에 git이 설치되고 /opt/chatbot이 git repo로 설정된 상태

set -e
ENV="${1:-prod}"
EC2_USER="ubuntu"
EC2_KEY="$HOME/Downloads/chatbot-key.pem"
DEPLOY_PATH="/opt/chatbot"

# EC2 IP를 스크립트 인자 또는 환경변수로 받음
EC2_IP="${EC2_IP:-}"
[ -z "$EC2_IP" ] && { echo "EC2_IP 환경변수를 설정하세요: export EC2_IP=1.2.3.4"; exit 1; }

SSH="ssh -i $EC2_KEY -o StrictHostKeyChecking=no $EC2_USER@$EC2_IP"

echo "[DEPLOY] git pull 중..."
$SSH "cd $DEPLOY_PATH && git pull origin main"

echo "[DEPLOY] 이미지 빌드 및 서비스 재시작..."
$SSH "cd $DEPLOY_PATH && sudo bash deploy.sh update $ENV"

echo "[DEPLOY] 완료. 로그 확인:"
echo "  $SSH 'cd $DEPLOY_PATH && docker compose -f docker-compose.prod.yml logs -f backend'"
```

**사용법:**
```bash
export EC2_IP=43.202.215.18
bash scripts/remote-deploy.sh prod
```

---

## 3. EC2 IP 고정 (Elastic IP 할당)

### 비용: $0/월 (EC2가 실행 중인 동안은 무료)

### 절차 (AWS 콘솔 기준)

1. AWS 콘솔 → EC2 → 좌측 메뉴 **Elastic IPs**
2. **Allocate Elastic IP address** 클릭
3. 리전: ap-northeast-2 (서울) 확인 후 **Allocate**
4. 생성된 EIP 선택 → **Actions → Associate Elastic IP address**
5. Instance: 운영 EC2 선택 → **Associate**

이후 IP는 EC2 재시작과 무관하게 고정된다.

### 로컬 설정 추가

```bash
# ~/.ssh/config 에 추가 (Windows: C:\Users\ParkHue\.ssh\config)
Host chatbot-prod
  HostName <Elastic_IP>
  User ubuntu
  IdentityFile ~/Downloads/chatbot-key.pem
  ServerAliveInterval 60

# 이후 접속:
ssh chatbot-prod
```

---

## 4. SSH 키 안전 관리

### 현재 문제: 단일 파일, 임시 위치

### 개선 방안

**키 백업 (즉시 실행):**

```bash
# 1. 영구 위치로 복사
mkdir -p ~/.ssh
cp ~/Downloads/chatbot-key.pem ~/.ssh/chatbot-prod.pem
chmod 600 ~/.ssh/chatbot-prod.pem

# 2. 외부 백업 (둘 중 하나)
#   a) AWS Systems Manager Parameter Store에 저장 (무료)
#   b) 로컬 암호화 백업
openssl enc -aes-256-cbc -pbkdf2 -in ~/.ssh/chatbot-prod.pem \
  -out ~/OneDrive/backups/chatbot-prod.pem.enc
# 복호화: openssl enc -d -aes-256-cbc -pbkdf2 -in chatbot-prod.pem.enc -out chatbot-prod.pem
```

**EC2에서 추가 키 페어 등록 (현재 키 손상 방지):**

```bash
# 로컬에서 새 키 생성
ssh-keygen -t ed25519 -f ~/.ssh/chatbot-prod-backup -C "chatbot-prod-backup-2026"

# 현재 키로 EC2 접속 후 authorized_keys에 추가
ssh chatbot-prod "echo '$(cat ~/.ssh/chatbot-prod-backup.pub)' >> ~/.ssh/authorized_keys"
```

**접속 불능 시 긴급 복구:**
- AWS 콘솔 → EC2 → 인스턴스 → Connect → **EC2 Instance Connect** (브라우저 기반) 사용
- 또는 AWS Systems Manager Session Manager (IAM 역할 필요)

---

## 5. 개발 → 운영 배포 파이프라인

### 브랜치 전략 (최소화)

```
main           ← 운영 배포 브랜치 (현재와 동일)
feature/xxx    ← 기능 개발 브랜치
fix/xxx        ← 버그 수정 브랜치
```

팀 1인이므로 develop 브랜치는 생략. feature 브랜치에서 개발 → 로컬 테스트 → main merge → EC2 배포.

### 마이그레이션 검증 단계

현재 `deploy.sh`의 `run_migrations()` 함수가 `alembic upgrade head`를 바로 실행한다. 여기에 검증 단계를 추가해야 한다.

**개선된 마이그레이션 흐름:**

```bash
# 배포 전 로컬에서 실행 (필수)
# 1. 현재 운영 DB head 확인
ssh chatbot-prod "cd /opt/chatbot && docker compose -f docker-compose.prod.yml exec -T db \
  psql -U chatbot -c 'SELECT version_num FROM alembic_version;'"

# 2. 적용될 마이그레이션 목록 미리 확인
cd backend && .venv/Scripts/python.exe -m alembic --config alembic.ini history -r current:head

# 3. 운영 DB 스냅샷 (배포 전)
ssh chatbot-prod "docker exec chatbot-db pg_dump -U chatbot chatbot | gzip > /opt/chatbot/backups/pre-deploy-$(date +%Y%m%d-%H%M%S).sql.gz"

# 4. 배포 및 마이그레이션 적용
bash scripts/remote-deploy.sh prod
```

**`deploy.sh`의 `run_migrations()` 개선 포인트 (deploy.sh 내부):**

마이그레이션 실행 전후로 revision 로그를 남기도록 개선:

```bash
run_migrations() {
  log "마이그레이션 전 버전: $($COMPOSE_CMD exec -T db psql -U chatbot -t -c 'SELECT version_num FROM alembic_version;' 2>/dev/null || echo 'none')"
  log "Alembic 마이그레이션 실행 중..."
  $COMPOSE_CMD run --rm backend sh -c "PYTHONPATH=/app alembic upgrade head"
  log "마이그레이션 후 버전: $($COMPOSE_CMD exec -T db psql -U chatbot -t -c 'SELECT version_num FROM alembic_version;' 2>/dev/null)"
  log "마이그레이션 완료"
}
```

### 전체 배포 순서 체크리스트

```
[ ] 1. 로컬 테스트 통과 확인
        bash scripts/run-tests.sh --backend-only

[ ] 2. 마이그레이션 변경사항 있으면 로컬에서 미리 검토
        cd backend && .venv/Scripts/python.exe -m alembic history -r current:head

[ ] 3. git commit & push
        git push origin main

[ ] 4. 운영 DB 백업 (마이그레이션 있을 때만)
        ssh chatbot-prod "docker exec chatbot-db pg_dump ..."

[ ] 5. 원격 배포 실행
        export EC2_IP=<Elastic_IP>
        bash scripts/remote-deploy.sh prod

[ ] 6. 배포 후 헬스체크
        curl http://<EC2_IP>/health
        curl http://<EC2_IP>/api/health
```

---

## 6. 장애 대응 (롤백 및 백업)

### 롤백 전략

**코드 롤백:**
```bash
# EC2에서 직접 실행
ssh chatbot-prod
cd /opt/chatbot

# 이전 커밋으로 복구
git log --oneline -5   # 롤백 대상 커밋 해시 확인
git checkout <이전_커밋_해시>

# 이미지 재빌드 및 재시작
sudo bash deploy.sh update prod
```

**DB 롤백 (마이그레이션 되돌리기):**
```bash
# 특정 revision으로 다운그레이드
ssh chatbot-prod "cd /opt/chatbot && docker compose -f docker-compose.prod.yml run --rm backend \
  sh -c 'PYTHONPATH=/app alembic downgrade -1'"

# 또는 백업 복구
ssh chatbot-prod "cd /opt/chatbot && \
  docker exec chatbot-db psql -U chatbot -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;' && \
  zcat backups/pre-deploy-YYYYMMDD-HHMMSS.sql.gz | docker exec -i chatbot-db psql -U chatbot chatbot"
```

### 백업 전략

**자동 일일 백업 (EC2 crontab):**

```bash
# EC2에서 crontab 설정
ssh chatbot-prod
crontab -e

# 매일 새벽 3시 DB 백업 (최근 7일분 보관)
0 3 * * * mkdir -p /opt/chatbot/backups && \
  docker exec chatbot-db pg_dump -U chatbot chatbot | \
  gzip > /opt/chatbot/backups/daily-$(date +\%Y\%m\%d).sql.gz && \
  find /opt/chatbot/backups -name "daily-*.sql.gz" -mtime +7 -delete
```

**백업 외부 저장 (S3 선택사항):**
- S3 버킷 + `aws s3 cp` 명령으로 EC2 백업을 외부로 복사
- 비용: S3 Standard 1GB 이하 시 거의 무료

---

## 실행 우선순위

현재 상황에서 당장 해결이 급한 순서:

### 즉시 (오늘)
1. SSH 키를 `~/.ssh/chatbot-prod.pem`으로 복사하고 권한 600 설정
2. 백업 키 생성 (`ssh-keygen -t ed25519`) 및 EC2 authorized_keys 등록

### 이번 주
3. AWS 콘솔에서 Elastic IP 할당 및 연결
4. EC2에 git 설치 + GitHub PAT 설정 + `/opt/chatbot` git init

### 다음 배포 전
5. `scripts/remote-deploy.sh` 작성 및 테스트
6. 배포 전 DB 백업 스크립트 검증
7. EC2 crontab 일일 백업 설정

---

## 비용 영향

| 항목 | 비용 |
|---|---|
| Elastic IP (EC2 실행 중) | $0/월 |
| EC2 t4g.small (현재) | ~$15/월 |
| 개발 서버 (로컬 Docker) | $0/월 추가 |
| S3 백업 (1GB 미만) | ~$0.03/월 |
| **총계** | **~$15/월 (현재와 동일)** |
