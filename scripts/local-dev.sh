#!/usr/bin/env bash
# 풀스택 로컬 개발 환경 관리 스크립트
# Usage: bash scripts/local-dev.sh [start|stop|reset|status]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.yml"
BACKEND_DIR="$PROJECT_ROOT/backend"
PYTHON="$BACKEND_DIR/.venv/Scripts/python.exe"

# Windows git-bash fallback
if [ ! -f "$PYTHON" ]; then
    PYTHON="$BACKEND_DIR/.venv/bin/python"
fi

CMD="${1:-start}"

_check_docker() {
    if ! docker info > /dev/null 2>&1; then
        echo "[ERROR] Docker is not running. Please start Docker Desktop."
        exit 1
    fi
}

_wait_healthy() {
    local service="$1"
    local max_wait=60
    local elapsed=0
    echo -n "[INFO] Waiting for $service to be healthy..."
    while [ $elapsed -lt $max_wait ]; do
        status=$(docker inspect --format='{{.State.Health.Status}}' "chatbot-$service" 2>/dev/null || echo "none")
        if [ "$status" = "healthy" ]; then
            echo " OK"
            return 0
        fi
        echo -n "."
        sleep 2
        elapsed=$((elapsed + 2))
    done
    echo " TIMEOUT"
    echo "[ERROR] $service did not become healthy in ${max_wait}s"
    exit 1
}

_run_migrations() {
    echo "[INFO] Running Alembic migrations..."
    cd "$BACKEND_DIR"
    if [ -f ".env" ]; then
        set -a; source .env; set +a
    fi
    "$PYTHON" -m alembic upgrade head
    cd "$PROJECT_ROOT"
}

_run_seed() {
    echo "[INFO] Seeding database..."
    cd "$BACKEND_DIR"
    "$PYTHON" ../scripts/seed_data.py --env-file .env
    cd "$PROJECT_ROOT"
}

cmd_start() {
    _check_docker

    echo "[INFO] Starting dev environment..."
    docker compose -f "$COMPOSE_FILE" up -d db redis

    _wait_healthy db
    _wait_healthy redis

    _run_migrations
    _run_seed

    # backend / frontend은 선택적으로 시작 (Compose 정의에 따름)
    docker compose -f "$COMPOSE_FILE" up -d backend frontend 2>/dev/null || true

    echo ""
    echo "=== Dev environment ready ==="
    echo "Frontend:     http://localhost:3000"
    echo "Backend API:  http://localhost:8000"
    echo "API Docs:     http://localhost:8000/docs"
    echo ""
    echo "Test accounts:"
    echo "  Superadmin:  login_id=admin     / PW=Admin123!"
    echo "  Admin:       login_id=moderator / PW=Mod123!"
    echo "  User1:       login_id=user1     / PW=User123!"
    echo "  User2:       login_id=user2     / PW=User123!"
    echo "  User3(18+):  login_id=user3     / PW=User123!"
}

cmd_stop() {
    _check_docker
    echo "[INFO] Stopping dev environment..."
    docker compose -f "$COMPOSE_FILE" down
    echo "[OK] Stopped."
}

cmd_reset() {
    _check_docker
    echo "[INFO] Resetting dev environment (volumes will be deleted)..."
    docker compose -f "$COMPOSE_FILE" down -v
    echo "[INFO] Volumes removed. Restarting..."
    cmd_start
}

cmd_status() {
    _check_docker
    docker compose -f "$COMPOSE_FILE" ps
}

case "$CMD" in
    start)   cmd_start ;;
    stop)    cmd_stop ;;
    reset)   cmd_reset ;;
    status)  cmd_status ;;
    *)
        echo "Usage: bash scripts/local-dev.sh [start|stop|reset|status]"
        echo ""
        echo "  start   Start dev environment (DB, Redis, backend, frontend)"
        echo "  stop    Stop all services"
        echo "  reset   Delete volumes and restart fresh"
        echo "  status  Show service status"
        exit 1
        ;;
esac
