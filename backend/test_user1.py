"""user1 로그인 테스트."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import httpx

r = httpx.post("http://localhost:8000/api/auth/login", json={"nickname": "user1", "password": "Test1234"}, timeout=10)
print(f"Login: {r.status_code}")
if r.status_code == 200:
    token = r.json()["access_token"]
    me = httpx.get("http://localhost:8000/api/auth/me", headers={"Authorization": f"Bearer {token}"}, timeout=10).json()
    print(f"User: {me['nickname']}, role={me['role']}")
    print("OK")
else:
    print(f"Error: {r.text[:300]}")
