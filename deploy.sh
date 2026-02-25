#!/bin/bash
# ==============================================================
# EC2 배포 스크립트 (Ubuntu 22.04 / Amazon Linux 2023)
# 사용법: bash deploy.sh [update]
#   첫 배포: bash deploy.sh
#   코드 업데이트: bash deploy.sh update
# ==============================================================
set -e

REPO_DIR="/opt/chatbot"
COMPOSE_FILE="docker-compose.prod.yml"

# ────────────────────────────────────────────────────────────
# 함수 정의
# ────────────────────────────────────────────────────────────
log() { echo -e "\033[1;32m[DEPLOY]\033[0m $1"; }
err() { echo -e "\033[1;31m[ERROR]\033[0m $1" >&2; exit 1; }

require_root() {
  [ "$EUID" -eq 0 ] || err "root 권한으로 실행하세요: sudo bash deploy.sh"
}

install_docker() {
  if command -v docker &>/dev/null; then
    log "Docker 이미 설치됨: $(docker --version)"
    return
  fi

  log "Docker 설치 중..."
  # Ubuntu / Debian
  if command -v apt-get &>/dev/null; then
    apt-get update -q
    apt-get install -y ca-certificates curl gnupg lsb-release
    mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
      https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
      > /etc/apt/sources.list.d/docker.list
    apt-get update -q
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  # Amazon Linux
  elif command -v yum &>/dev/null; then
    yum update -y -q
    yum install -y docker
    systemctl enable docker
    systemctl start docker
    # Docker Compose v2 플러그인
    mkdir -p /usr/local/lib/docker/cli-plugins
    curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$(uname -m)" \
      -o /usr/local/lib/docker/cli-plugins/docker-compose
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
  else
    err "지원하지 않는 OS입니다."
  fi

  systemctl enable docker
  systemctl start docker
  log "Docker 설치 완료: $(docker --version)"
}

check_env() {
  [ -f "$REPO_DIR/.env" ] || err ".env 파일이 없습니다. .env.production.example을 복사하여 설정하세요."

  # 필수 변수 확인
  local required_vars=("SECRET_KEY" "POSTGRES_PASSWORD" "REDIS_PASSWORD" "CORS_ORIGINS")
  for var in "${required_vars[@]}"; do
    local val
    val=$(grep -E "^${var}=" "$REPO_DIR/.env" | cut -d= -f2- | tr -d '"' | tr -d "'")
    [ -n "$val" ] || err ".env에 ${var}가 설정되지 않았습니다."
    [[ "$val" == "CHANGE_ME" ]] && err ".env의 ${var}를 실제 값으로 변경하세요."
  done
  log ".env 검증 통과"
}

run_migrations() {
  log "Alembic 마이그레이션 실행 중..."
  docker compose -f "$COMPOSE_FILE" run --rm backend \
    sh -c "PYTHONPATH=/app alembic upgrade head"
  log "마이그레이션 완료"
}

create_superadmin() {
  log "슈퍼어드민 계정 확인..."
  # 이미 있으면 스킵 (UPSERT)
  docker compose -f "$COMPOSE_FILE" run --rm backend python3 -c "
import asyncio, os, sys
sys.path.insert(0, '/app')
from app.core.database import AsyncSessionLocal
from app.core.auth import get_password_hash
from app.models.user import User
from sqlalchemy import select
from datetime import datetime, timezone

async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.role == 'superadmin'))
        if result.scalar_one_or_none():
            print('슈퍼어드민 이미 존재 — 건너뜀')
            return
        import uuid
        admin = User(
            id=uuid.uuid4(),
            nickname='admin',
            password_hash=get_password_hash(os.environ.get('ADMIN_INIT_PASSWORD', 'ChangeMe123!')),
            role='superadmin',
            age_group='adult_verified',
            adult_verified_at=datetime.now(timezone.utc),
        )
        db.add(admin)
        await db.commit()
        print(f'슈퍼어드민 생성: nickname=admin')

asyncio.run(main())
" || true
}

# ────────────────────────────────────────────────────────────
# 메인
# ────────────────────────────────────────────────────────────
MODE="${1:-fresh}"
cd "$REPO_DIR" || err "$REPO_DIR 디렉토리가 없습니다. 코드를 먼저 업로드하세요."

if [ "$MODE" = "update" ]; then
  # ── 코드 업데이트 배포 ──
  log "=== 업데이트 배포 시작 ==="
  check_env
  log "이미지 빌드 중 (레이어 캐시 활용)..."
  # --no-cache 제거: requirements.txt/package.json 미변경 시 pip/npm 레이어 재사용
  # DOCKER_BUILDKIT=1: --mount=type=cache 캐시 마운트 활성화
  DOCKER_BUILDKIT=1 docker compose -f "$COMPOSE_FILE" build backend frontend
  log "서비스 재시작 중..."
  docker compose -f "$COMPOSE_FILE" up -d --no-deps backend frontend nginx
  run_migrations
  log "=== 업데이트 완료 ==="

else
  # ── 최초 배포 ──
  log "=== 최초 배포 시작 ==="
  require_root
  install_docker
  check_env

  log "모든 서비스 빌드 및 시작..."
  docker compose -f "$COMPOSE_FILE" up -d --build

  log "DB 준비 대기 중 (최대 30초)..."
  sleep 15

  run_migrations
  create_superadmin

  log ""
  log "=== 배포 완료 ==="
  log "서버 주소: http://$(curl -s ifconfig.me 2>/dev/null || echo 'YOUR_EC2_IP')"
  log "슈퍼어드민: nickname=admin / PW=ChangeMe123! (즉시 변경하세요)"
  log ""
  log "서비스 상태 확인: docker compose -f $COMPOSE_FILE ps"
  log "백엔드 로그:      docker compose -f $COMPOSE_FILE logs -f backend"
fi
