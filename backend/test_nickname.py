"""생성자 닉네임 + 익명 기능 테스트."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import httpx

BASE = "http://localhost:8000"

# 1. 로그인
r = httpx.post(f"{BASE}/api/auth/login", json={"nickname": "user1", "password": "Test1234"}, timeout=10)
assert r.status_code == 200, f"Login failed: {r.text}"
token = r.json()["access_token"]
h = {"Authorization": f"Bearer {token}"}
print("[1] 로그인 성공")

# 2. 페르소나 목록 조회 — creator_nickname 필드 확인
personas = httpx.get(f"{BASE}/api/personas", headers=h, timeout=10).json()
print(f"[2] 페르소나 {personas['total']}개")
for p in personas["items"]:
    print(f"  - {p['display_name']} | creator_nickname={p.get('creator_nickname')} | is_anonymous={p.get('is_anonymous')}")

print("\nOK")
