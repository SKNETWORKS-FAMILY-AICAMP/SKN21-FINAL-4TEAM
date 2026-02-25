#!/bin/sh
set -e

# Docker named volume은 기본적으로 root 소유로 마운트됨.
# appuser 가 /app/uploads 에 쓸 수 있도록 권한을 수정한 뒤 권한 강등.
mkdir -p /app/uploads
chown -R appuser:appgroup /app/uploads

exec gosu appuser uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
