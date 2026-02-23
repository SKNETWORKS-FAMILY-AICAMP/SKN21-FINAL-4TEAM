"""프론트엔드 프록시 경유 로그인 테스트."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import httpx

FRONTEND = "http://localhost:3000"
BACKEND = "http://localhost:8000"

# 1. 프론트엔드 프록시 경유 로그인
print("=== Frontend proxy login ===")
r = httpx.post(f"{FRONTEND}/api/auth/login", json={"nickname": "tester", "password": "Test1234"}, timeout=10)
print(f"Status: {r.status_code}")
print(f"Body: {r.text[:300]}")

if r.status_code == 200:
    token = r.json()["access_token"]

    # 2. /auth/me 프록시 경유
    print("\n=== Frontend proxy /auth/me ===")
    me_r = httpx.get(f"{FRONTEND}/api/auth/me", headers={"Authorization": f"Bearer {token}"}, timeout=10)
    print(f"Status: {me_r.status_code}")
    print(f"Body: {me_r.text[:500]}")

# 3. 백엔드 직접 로그인 비교
print("\n=== Backend direct login ===")
r2 = httpx.post(f"{BACKEND}/api/auth/login", json={"nickname": "tester", "password": "Test1234"}, timeout=10)
print(f"Status: {r2.status_code}")
print(f"Body: {r2.text[:300]}")

# 4. 프론트엔드 메인 페이지 로드 확인
print("\n=== Frontend page load ===")
page = httpx.get(f"{FRONTEND}/", timeout=10)
print(f"Status: {page.status_code}")
print(f"Content-Type: {page.headers.get('content-type', 'N/A')}")
print(f"Body length: {len(page.text)}")
has_login_form = "닉네임" in page.text or "로그인" in page.text or "login" in page.text.lower()
print(f"Has login-related content: {has_login_form}")
