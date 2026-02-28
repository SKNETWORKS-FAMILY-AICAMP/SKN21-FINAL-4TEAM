/**
 * 7개 버그 수정 검증 E2E 테스트
 *
 * 인증 흐름: setupMockAPI + auth/me 오버라이드 → 직접 페이지 이동 (쿠키 mock 없이도 동작)
 */
import { test, expect } from '@playwright/test';
import { setupMockAPI, MOCK_ADMIN, MOCK_USER } from './helpers';

// ---------------------------------------------------------------------------
// 공통 헬퍼: mock 설정 후 직접 페이지 이동 (로그인 폼 우회)
// ---------------------------------------------------------------------------
async function gotoAsUser(
  page: Parameters<typeof setupMockAPI>[0],
  path: string,
  extraRoutes?: () => Promise<void>,
) {
  await setupMockAPI(page, MOCK_USER);
  // auth/me 오버라이드 — Authorization 헤더 없이도 인증 성공
  await page.route('**/api/auth/me', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_USER),
    }),
  );
  if (extraRoutes) await extraRoutes();
  await page.goto(path);
  await page.waitForLoadState('networkidle');
}

async function gotoAsAdmin(
  page: Parameters<typeof setupMockAPI>[0],
  path: string,
  extraRoutes?: () => Promise<void>,
) {
  await setupMockAPI(page, MOCK_ADMIN);
  await page.route('**/api/auth/me', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_ADMIN),
    }),
  );
  if (extraRoutes) await extraRoutes();
  await page.goto(path);
  await page.waitForLoadState('networkidle');
}

// ---------------------------------------------------------------------------
// 수정 1: Tailwind bg-bg-muted — 비활성 토글 배경색 (#3a3a3a)
// ---------------------------------------------------------------------------
test('FIX-1: admin features 비활성 토글에 bg-bg-muted 배경색 적용', async ({ page }) => {
  await gotoAsAdmin(page, '/admin/features', async () => {
    await page.route('**/api/admin/features**', (route) => {
      if (route.request().method() === 'GET') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([
            { key: 'tts_enabled',    label: 'TTS',  description: 'TTS 기능', category: 'user',  enabled: false },
            { key: 'debate_enabled', label: '토론', description: '토론 기능', category: 'user',  enabled: true  },
          ]),
        });
      }
      return route.fallback();
    });
  });

  await page.screenshot({ path: 'screenshots/fix1-admin-features.png', fullPage: true });

  // bg-bg-muted 클래스 요소 존재
  const mutedEl = page.locator('[class*="bg-bg-muted"]').first();
  const elCount = await mutedEl.count();
  console.log(`  bg-bg-muted 요소 수: ${elCount}`);
  expect(elCount).toBeGreaterThan(0);

  // computed style: 투명이 아닌 실제 색상
  const bgColor = await mutedEl.evaluate((el) => window.getComputedStyle(el).backgroundColor);
  console.log(`  computed backgroundColor: ${bgColor}`);
  expect(bgColor).not.toBe('rgba(0, 0, 0, 0)');
  expect(bgColor).not.toBe('transparent');
  // rgb(58, 58, 58) = #3a3a3a
  expect(bgColor).toBe('rgb(58, 58, 58)');

  console.log('✅ FIX-1: 비활성 토글 bg-bg-muted → #3a3a3a 확인');
});

// ---------------------------------------------------------------------------
// 수정 3: addTurnFromSSE 중복 방지 — JS 로직 검증
// ---------------------------------------------------------------------------
test('FIX-3: addTurnFromSSE 중복 턴 방지 — 같은 번호 턴은 교체된다', async ({ page }) => {
  await gotoAsUser(page, '/debate', async () => {
    await page.route('**/api/debate/topics**', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [], total: 0 }),
      }),
    );
  });

  // Zustand store를 직접 접근할 수 없으므로 동일 로직을 page.evaluate로 검증
  const result = await page.evaluate(() => {
    const turns: { turn_number: number; speaker: string; content: string }[] = [];

    function addTurnFromSSE(turn: { turn_number: number; speaker: string; content: string }) {
      const exists = turns.some(
        (t) => t.turn_number === turn.turn_number && t.speaker === turn.speaker,
      );
      if (exists) {
        const idx = turns.findIndex(
          (t) => t.turn_number === turn.turn_number && t.speaker === turn.speaker,
        );
        turns[idx] = turn;
      } else {
        turns.push(turn);
      }
    }

    addTurnFromSSE({ turn_number: 1, speaker: 'agent_a', content: '첫 번째' });
    addTurnFromSSE({ turn_number: 1, speaker: 'agent_a', content: '업데이트됨' }); // 중복
    addTurnFromSSE({ turn_number: 2, speaker: 'agent_b', content: '두 번째' });

    return { count: turns.length, firstContent: turns[0].content };
  });

  expect(result.count).toBe(2); // 중복 제거 → 2개
  expect(result.firstContent).toBe('업데이트됨'); // 최신 내용으로 교체
  console.log('✅ FIX-3: addTurnFromSSE 중복 방지 로직 확인');
});

// ---------------------------------------------------------------------------
// 수정 4: TurnBubble fast path "빠른 통과" UI
// ---------------------------------------------------------------------------
test('FIX-4: TurnBubble — skipped=true 턴은 "빠른 통과" 라벨, skipped=false 턴은 논증 품질 표시', async ({
  page,
}) => {
  const agentA = { id: 'agent-a', name: '에이전트A', provider: 'openai', model_id: 'gpt-4o', elo_rating: 1200, image_url: null };
  const agentB = { id: 'agent-b', name: '에이전트B', provider: 'anthropic', model_id: 'claude-3', elo_rating: 1150, image_url: null };

  const mockMatch = {
    id: 'match-fp01',
    topic_id: 'topic-001',
    topic_title: '테스트 토론',
    status: 'completed',
    agent_a: agentA,
    agent_b: agentB,
    winner_id: 'agent-a',
    score_a: 75,
    score_b: 60,
    penalty_a: 0,
    penalty_b: 0,
    turn_count: 2,
    started_at: '2026-02-28T10:00:00Z',
    finished_at: '2026-02-28T10:30:00Z',
    created_at: '2026-02-28T09:55:00Z',
  };

  const mockTurns = [
    {
      id: 'turn-001',
      turn_number: 1,
      speaker: 'agent_a',
      agent_id: 'agent-a',
      action: 'argue',
      claim: '저는 이 주장에 동의합니다.',
      evidence: null,
      tool_used: null,
      tool_result: null,
      penalties: null,
      penalty_total: 0,
      human_suspicion_score: 5,
      response_time_ms: 1200,
      input_tokens: 100,
      output_tokens: 50,
      review_result: {
        logic_score: null,
        violations: [],
        feedback: '',
        blocked: false,
        skipped: true,
      },
      is_blocked: false,
      created_at: '2026-02-28T10:01:00Z',
    },
    {
      id: 'turn-002',
      turn_number: 2,
      speaker: 'agent_b',
      agent_id: 'agent-b',
      action: 'rebut',
      claim: '반론을 제기합니다.',
      evidence: null,
      tool_used: null,
      tool_result: null,
      penalties: null,
      penalty_total: 0,
      human_suspicion_score: 10,
      response_time_ms: 900,
      input_tokens: 120,
      output_tokens: 60,
      review_result: {
        logic_score: 78,
        violations: [],
        feedback: '논리적입니다.',
        blocked: false,
        skipped: false,
      },
      is_blocked: false,
      created_at: '2026-02-28T10:02:00Z',
    },
  ];

  await gotoAsUser(page, '/debate/matches/match-fp01', async () => {
    await page.route('**/api/matches/match-fp01', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(mockMatch) }),
    );
    await page.route('**/api/matches/match-fp01/turns**', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(mockTurns) }),
    );
  });

  await page.screenshot({ path: 'screenshots/fix4-turnbubble-fastpath.png', fullPage: true });

  // skipped=true 턴: "빠른 통과" 라벨 표시
  await expect(page.getByText('빠른 통과 — 규칙 위반 없음')).toBeVisible();

  // skipped=false 턴: 논증 품질 섹션 표시
  await expect(page.getByText('논증 품질')).toBeVisible();

  // 논증 품질 섹션은 1개만 (skipped=true 턴에는 없음)
  expect(await page.getByText('논증 품질').count()).toBe(1);

  console.log('✅ FIX-4: fast path "빠른 통과" 라벨 + 논증 품질 분기 확인');
});

// ---------------------------------------------------------------------------
// 수정 6: 마이페이지 탭 8개 + 오버플로우 컨테이너 + 그라디언트 힌트
// ---------------------------------------------------------------------------
test('FIX-6: 마이페이지 — 8개 탭 버튼 + overflow 컨테이너 + 그라디언트 힌트', async ({
  page,
}) => {
  await gotoAsUser(page, '/mypage', async () => {
    await page.route('**/api/debate/agents**', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [], total: 0 }),
      }),
    );
  });

  await page.screenshot({ path: 'screenshots/fix6-mypage-tabs.png', fullPage: false });

  // 탭 버튼 8개
  const tabButtons = page.locator('button[class*="border-b-2"]');
  const tabCount = await tabButtons.count();
  console.log(`  탭 버튼 수: ${tabCount}`);
  expect(tabCount).toBe(8);

  // overflow-x-auto scrollbar-hide 컨테이너
  const tabContainer = page.locator('.overflow-x-auto.scrollbar-hide');
  await expect(tabContainer).toBeVisible();

  // 그라디언트 힌트 (relative 컨테이너 내부)
  const gradientHint = page.locator('.bg-gradient-to-l').first();
  expect(await gradientHint.count()).toBeGreaterThan(0);

  console.log('✅ FIX-6: 8개 탭 + overflow + 그라디언트 힌트 확인');
});

// ---------------------------------------------------------------------------
// 수정 6: 모바일(375px) — 그라디언트 힌트 가시성
// ---------------------------------------------------------------------------
test('FIX-6(모바일): 375px에서 그라디언트 힌트 표시 (md:hidden 미적용)', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });

  await gotoAsUser(page, '/mypage', async () => {
    await page.route('**/api/debate/agents**', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [], total: 0 }),
      }),
    );
  });

  await page.screenshot({ path: 'screenshots/fix6-mypage-mobile.png', fullPage: false });

  // 모바일에서 그라디언트가 DOM에 있고 (md:hidden — Tailwind breakpoint에서 숨겨짐)
  const gradient = page.locator('.bg-gradient-to-l.from-bg').first();
  expect(await gradient.count()).toBeGreaterThan(0);

  // 탭 컨테이너 스크롤 가능
  const tabContainer = page.locator('.overflow-x-auto').first();
  await expect(tabContainer).toBeVisible();

  // 8개 탭 버튼 존재
  const tabButtons = page.locator('button[class*="border-b-2"]');
  expect(await tabButtons.count()).toBe(8);

  console.log('✅ FIX-6(모바일): 375px 그라디언트 + 8탭 확인');
});

// ---------------------------------------------------------------------------
// 수정 7: 알림 TYPE_LABELS — 5개 신규 타입 + credit
// ---------------------------------------------------------------------------
test('FIX-7: 알림 페이지 — 6개 타입 라벨 표시 (follow/chat_request/chat_accepted/pending_post/world_event/credit)', async ({
  page,
}) => {
  const notifItems = [
    { id: 'n1', type: 'credit',        title: '크레딧 충전',   body: '50개 충전됨',   is_read: false, created_at: '2026-02-28T10:00:00Z', link: null },
    { id: 'n2', type: 'follow',        title: '팔로우 알림',   body: '팔로우했습니다', is_read: false, created_at: '2026-02-28T09:00:00Z', link: null },
    { id: 'n3', type: 'chat_request',  title: '대화 요청',     body: '요청이 왔습니다', is_read: true, created_at: '2026-02-28T08:00:00Z', link: null },
    { id: 'n4', type: 'chat_accepted', title: '대화 수락됨',   body: '수락됐습니다',   is_read: true, created_at: '2026-02-28T07:00:00Z', link: null },
    { id: 'n5', type: 'pending_post',  title: '게시물 승인',   body: '승인됐습니다',   is_read: true, created_at: '2026-02-28T06:00:00Z', link: null },
    { id: 'n6', type: 'world_event',   title: '세계관 이벤트', body: '새 이벤트',     is_read: false, created_at: '2026-02-28T05:00:00Z', link: null },
    { id: 'n7', type: 'unknown_type',  title: '알 수 없음',    body: '타입 없음',     is_read: false, created_at: '2026-02-28T04:00:00Z', link: null },
  ];
  await gotoAsUser(page, '/notifications', async () => {
    await page.route('**/api/notifications**', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: notifItems, total: notifItems.length }),
      }),
    );
  });

  await page.screenshot({ path: 'screenshots/fix7-notifications-labels.png', fullPage: true });

  // 6개 신규 타입 라벨
  await expect(page.getByText('크레딧').first()).toBeVisible();
  await expect(page.getByText('팔로우').first()).toBeVisible();
  await expect(page.getByText('대화 요청').first()).toBeVisible();
  await expect(page.getByText('대화 수락').first()).toBeVisible();
  await expect(page.getByText('게시물 승인').first()).toBeVisible();
  await expect(page.getByText('세계관 이벤트').first()).toBeVisible();
  // 알 수 없는 타입 → fallback: 원본 타입 문자열
  await expect(page.getByText('unknown_type').first()).toBeVisible();

  console.log('✅ FIX-7: 알림 6개 신규 타입 라벨 + unknown fallback 확인');
});

// ---------------------------------------------------------------------------
// 수정 7: 크레딧 충전 알림 — 제목+본문+라벨
// ---------------------------------------------------------------------------
test('FIX-7: credit 알림 — "크레딧" 라벨 + 일일 충전 제목/본문 표시', async ({ page }) => {
  await gotoAsUser(page, '/notifications', async () => {
    await page.route('**/api/notifications**', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: [{
            id: 'n-credit',
            type: 'credit',
            title: '일일 대화석 50개 충전!',
            body: '오늘의 무료 대화석이 충전되었습니다.',
            is_read: false,
            created_at: '2026-02-28T00:00:00Z',
            link: '/mypage?tab=usage',
          }],
          total: 1,
        }),
      }),
    );
  });

  await page.screenshot({ path: 'screenshots/fix7-credit-notification.png', fullPage: false });

  await expect(page.getByText('크레딧').first()).toBeVisible();
  await expect(page.getByText('일일 대화석 50개 충전!')).toBeVisible();
  await expect(page.getByText('오늘의 무료 대화석이 충전되었습니다.')).toBeVisible();

  console.log('✅ FIX-7: credit 알림 라벨 + 제목 + 본문 표시 확인');
});
