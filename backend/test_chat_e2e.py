"""E2E 테스트: 로그인 → 세션 생성 → OpenAI 채팅까지 전체 흐름 확인."""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import httpx
import json

BASE = "http://localhost:8000"


def main():
    # 1. 로그인
    r = httpx.post(f"{BASE}/api/auth/login", json={"nickname": "tester", "password": "Test1234"})
    assert r.status_code == 200, f"로그인 실패: {r.text}"
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    print("[1] 로그인 성공")

    # 2. 내 정보
    me = httpx.get(f"{BASE}/api/auth/me", headers=h).json()
    print(f"[2] 유저: {me['nickname']}, role={me['role']}, age={me['age_group']}")

    # 3. 모델 확인
    models = httpx.get(f"{BASE}/api/models", headers=h).json()
    print(f"[3] LLM 모델: {len(models)}개")
    for m in models:
        print(f"    - {m['display_name']} ({m['provider']}/{m['model_id']})")

    # 4. 페르소나 확인
    personas = httpx.get(f"{BASE}/api/personas", headers=h).json()
    print(f"[4] 페르소나: {personas['total']}개")
    for p in personas["items"]:
        print(f"    - {p['display_name']} ({p['id']})")

    if not personas["items"]:
        print("페르소나가 없습니다. seed_test.py를 먼저 실행하세요.")
        return

    persona_id = personas["items"][0]["id"]
    model_id = models[0]["id"]

    # 5. 채팅 세션 생성
    session_r = httpx.post(
        f"{BASE}/api/chat/sessions",
        headers=h,
        json={"persona_id": persona_id, "llm_model_id": model_id},
    )
    print(f"[5] 세션 생성: {session_r.status_code}")
    if session_r.status_code != 201:
        print(f"    에러: {session_r.text[:500]}")
        return

    session = session_r.json()
    session_id = session["id"]
    print(f"    세션 ID: {session_id}")

    # 5-1. 인사말 확인
    msgs = httpx.get(f"{BASE}/api/chat/sessions/{session_id}/messages", headers=h).json()
    if msgs:
        items = msgs if isinstance(msgs, list) else msgs.get("items", msgs.get("messages", []))
        if items:
            print(f"    인사말: {items[0].get('content', '')[:100]}")

    # 6. 메시지 전송 (OpenAI 실제 호출)
    print("[6] 메시지 전송 중 (OpenAI API 호출)...")
    msg_r = httpx.post(
        f"{BASE}/api/chat/sessions/{session_id}/messages",
        headers=h,
        json={"content": "안녕! 너 좋아하는 웹툰 있어?"},
        timeout=30.0,
    )
    print(f"    응답 상태: {msg_r.status_code}")

    if msg_r.status_code == 201:
        msg = msg_r.json()
        print(f"    AI 응답: {msg['content'][:300]}")
        print(f"    토큰: {msg.get('token_count', 'N/A')}")
        if msg.get("emotion_signal"):
            print(f"    감정: {msg['emotion_signal']}")
        print("\n✅ 전체 E2E 테스트 성공! 프론트엔드에서도 채팅 가능합니다.")
        print(f"\n   http://localhost:3000 접속")
        print(f"   로그인: tester / Test1234")
    else:
        print(f"    에러: {msg_r.text[:500]}")


if __name__ == "__main__":
    main()
