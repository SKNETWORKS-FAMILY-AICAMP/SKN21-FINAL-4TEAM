import { Page } from '@playwright/test';

// ---------------------------------------------------------------------------
// Mock data constants
// ---------------------------------------------------------------------------

export const MOCK_USER = {
  id: 'user-001',
  nickname: 'testuser',
  role: 'user' as const,
  age_group: 'unverified',
  adult_verified_at: null,
  preferred_llm_model_id: 'model-001',
};

export const MOCK_ADMIN = {
  id: 'admin-001',
  nickname: 'adminuser',
  role: 'admin' as const,
  age_group: 'adult_verified',
  adult_verified_at: '2026-01-01T00:00:00Z',
  preferred_llm_model_id: 'model-001',
};

export const MOCK_ADULT_VERIFIED_USER = {
  id: 'user-002',
  nickname: 'verifieduser',
  role: 'user' as const,
  age_group: 'adult_verified',
  adult_verified_at: '2026-01-15T00:00:00Z',
  preferred_llm_model_id: 'model-001',
};

export const MOCK_TOKEN = { access_token: 'mock-jwt-token-abc123', token_type: 'bearer' };

export const MOCK_PERSONAS = [
  {
    id: 'persona-001',
    display_name: '미니',
    age_rating: 'all' as const,
    visibility: 'public',
    type: 'system',
    system_prompt: '밝고 활발한 성격의 웹툰 리뷰어입니다. 항상 긍정적으로 리뷰합니다.',
    background_image_url: null,
    created_by: null,
  },
  {
    id: 'persona-002',
    display_name: '다크나이트',
    age_rating: '15+' as const,
    visibility: 'public',
    type: 'user_created',
    system_prompt: '냉소적이고 날카로운 비평가입니다. 작품의 약점을 잘 찾아냅니다.',
    background_image_url: '/assets/backgrounds/dark.jpg',
    created_by: 'user-001',
  },
  {
    id: 'persona-003',
    display_name: '성인전용 캐릭터',
    age_rating: '18+' as const,
    visibility: 'public',
    type: 'user_created',
    system_prompt: '성인 전용 캐릭터입니다. 성숙한 리뷰를 제공합니다.',
    background_image_url: null,
    created_by: 'user-002',
  },
];

export const MOCK_SESSIONS = [
  {
    id: 'session-001',
    persona_display_name: '미니',
    persona_age_rating: 'all',
    llm_model_name: 'Llama 3 70B',
    last_message_at: '2026-02-13T10:00:00Z',
    message_count: 12,
  },
  {
    id: 'session-002',
    persona_display_name: '다크나이트',
    persona_age_rating: '15+',
    llm_model_name: 'GPT-4o',
    last_message_at: '2026-02-12T15:30:00Z',
    message_count: 5,
  },
];

export const MOCK_MESSAGES = [
  { role: 'user', content: '안녕하세요!', emotion_signal: null },
  {
    role: 'assistant',
    content: '안녕하세요! 무슨 웹툰에 대해 이야기하고 싶으세요?',
    emotion_signal: 'happy',
  },
];

export const MOCK_MODELS = [
  {
    id: 'model-001',
    display_name: 'Llama 3 70B',
    provider: 'runpod',
    model_id: 'llama-3-70b',
    input_cost_per_1m: 0.59,
    output_cost_per_1m: 0.79,
    max_context_length: 128000,
    is_adult_only: false,
    is_active: true,
  },
  {
    id: 'model-002',
    display_name: 'GPT-4o',
    provider: 'openai',
    model_id: 'gpt-4o',
    input_cost_per_1m: 2.5,
    output_cost_per_1m: 10.0,
    max_context_length: 128000,
    is_adult_only: false,
    is_active: true,
  },
  {
    id: 'model-003',
    display_name: 'Adult Model X',
    provider: 'runpod',
    model_id: 'adult-model-x',
    input_cost_per_1m: 1.0,
    output_cost_per_1m: 2.0,
    max_context_length: 64000,
    is_adult_only: true,
    is_active: true,
  },
];

export const MOCK_LOREBOOK_ENTRIES = [
  {
    id: 'lore-001',
    title: '세계관 설정',
    content: '이 세계는 마법과 과학이 공존하는 세계입니다.',
    tags: ['세계관', '판타지'],
  },
  {
    id: 'lore-002',
    title: '주인공 설정',
    content: '주인공은 용감한 모험가입니다.',
    tags: ['캐릭터', '주인공'],
  },
];

export const MOCK_ADMIN_USERS = [
  {
    id: 'user-001',
    nickname: 'testuser',
    role: 'user',
    age_group: 'unverified',
    adult_verified_at: null,
    created_at: '2026-01-10T00:00:00Z',
  },
  {
    id: 'user-002',
    nickname: 'verifieduser',
    role: 'user',
    age_group: 'adult_verified',
    adult_verified_at: '2026-01-15T00:00:00Z',
    created_at: '2026-01-05T00:00:00Z',
  },
  {
    id: 'admin-001',
    nickname: 'adminuser',
    role: 'admin',
    age_group: 'adult_verified',
    adult_verified_at: '2026-01-01T00:00:00Z',
    created_at: '2026-01-01T00:00:00Z',
  },
];

export const MOCK_ADMIN_PERSONAS = [
  {
    id: 'persona-002',
    display_name: '다크나이트',
    type: 'user_created',
    age_rating: '15+',
    visibility: 'public',
    moderation_status: 'pending',
    created_by_nickname: 'testuser',
  },
  {
    id: 'persona-004',
    display_name: '대기중 페르소나',
    type: 'user_created',
    age_rating: 'all',
    visibility: 'public',
    moderation_status: 'pending',
    created_by_nickname: 'verifieduser',
  },
];

export const MOCK_MONITORING_STATS = {
  total_users: 150,
  total_sessions: 420,
  total_messages: 8500,
  daily_messages: 230,
  weekly_messages: 1250,
  moderation_pending: 3,
};

export const MOCK_DASHBOARD_STATS = {
  total_users: 150,
  daily_active_users: 42,
  total_sessions: 420,
  total_messages: 8500,
  daily_messages: 230,
  total_personas: 35,
  moderation_pending: 3,
};

export const MOCK_MONITORING_LOGS = [
  {
    id: 'log-001',
    user_nickname: 'testuser',
    model_name: 'Llama 3 70B',
    input_tokens: 1200,
    output_tokens: 450,
    cost: 0.0011,
    created_at: '2026-02-13T09:30:00Z',
  },
  {
    id: 'log-002',
    user_nickname: 'verifieduser',
    model_name: 'GPT-4o',
    input_tokens: 800,
    output_tokens: 320,
    cost: 0.0052,
    created_at: '2026-02-13T08:15:00Z',
  },
];

export const MOCK_USAGE_SUMMARY = {
  total_tokens: 50000,
  total_cost: 0.45,
  daily_tokens: 2000,
  daily_cost: 0.018,
  monthly_tokens: 35000,
  monthly_cost: 0.31,
  by_model: [
    {
      model_name: 'Llama 3 70B',
      input_cost_per_1m: 0.59,
      output_cost_per_1m: 0.79,
      total_tokens: 30000,
      total_cost: 0.02,
    },
    {
      model_name: 'GPT-4o',
      input_cost_per_1m: 2.5,
      output_cost_per_1m: 10.0,
      total_tokens: 20000,
      total_cost: 0.43,
    },
  ],
};

export const MOCK_USAGE_HISTORY = [
  { date: '2026-02-10', tokens: 5000, cost: 0.05 },
  { date: '2026-02-11', tokens: 8000, cost: 0.07 },
  { date: '2026-02-12', tokens: 6000, cost: 0.06 },
  { date: '2026-02-13', tokens: 2000, cost: 0.02 },
];

export const MOCK_ADMIN_USAGE_SUMMARY = {
  total_tokens: 500000,
  total_cost: 4.5,
  daily_tokens: 20000,
  daily_cost: 0.18,
  monthly_tokens: 350000,
  monthly_cost: 3.1,
};

export const MOCK_ADMIN_USER_USAGES = [
  { user_id: 'user-001', nickname: 'testuser', total_tokens: 30000, total_cost: 0.28 },
  { user_id: 'user-002', nickname: 'verifieduser', total_tokens: 20000, total_cost: 0.17 },
];

export const MOCK_FAVORITES = [
  {
    id: 'fav-001',
    persona_id: 'persona-001',
    persona_display_name: '미니',
    persona_age_rating: 'all',
    created_at: '2026-02-10T00:00:00Z',
  },
];

export const MOCK_NOTIFICATIONS = [
  {
    id: 'notif-001',
    type: 'system',
    title: '환영합니다!',
    message: '서비스에 가입해 주셔서 감사합니다.',
    is_read: false,
    created_at: '2026-02-13T10:00:00Z',
  },
  {
    id: 'notif-002',
    type: 'persona',
    title: '페르소나 승인됨',
    message: '다크나이트 페르소나가 승인되었습니다.',
    is_read: true,
    created_at: '2026-02-12T15:00:00Z',
  },
];

export const MOCK_CREDITS = {
  balance: 120,
  daily_earned: 50,
  total_spent: 380,
};

export const MOCK_CREDIT_TRANSACTIONS = [
  {
    id: 'tx-001',
    type: 'daily_grant',
    amount: 50,
    balance_after: 120,
    description: '일일 무료 크레딧',
    created_at: '2026-02-13T00:00:00Z',
  },
  {
    id: 'tx-002',
    type: 'chat_usage',
    amount: -5,
    balance_after: 70,
    description: '채팅 사용',
    created_at: '2026-02-12T14:30:00Z',
  },
];

export const MOCK_COMMUNITY_POSTS = [
  {
    id: 'post-001',
    title: '미니와 대화한 후기',
    content: '정말 재밌었어요!',
    author_nickname: 'testuser',
    like_count: 5,
    comment_count: 2,
    created_at: '2026-02-13T09:00:00Z',
  },
  {
    id: 'post-002',
    title: '추천 페르소나 공유',
    content: '이 페르소나 추천합니다.',
    author_nickname: 'verifieduser',
    like_count: 12,
    comment_count: 4,
    created_at: '2026-02-12T18:00:00Z',
  },
];

export const MOCK_RELATIONSHIPS = [
  {
    id: 'rel-001',
    persona_id: 'persona-001',
    persona_display_name: '미니',
    affinity_score: 450,
    relationship_stage: 'friend',
    updated_at: '2026-02-13T10:00:00Z',
  },
  {
    id: 'rel-002',
    persona_id: 'persona-002',
    persona_display_name: '다크나이트',
    affinity_score: 120,
    relationship_stage: 'acquaintance',
    updated_at: '2026-02-12T08:00:00Z',
  },
];

export const MOCK_SUBSCRIPTION_PLANS = [
  { id: 'plan-free', name: '무료', price: 0, daily_credits: 50, features: ['기본 채팅', '페르소나 생성'] },
  { id: 'plan-premium', name: '프리미엄', price: 9900, daily_credits: 300, features: ['무제한 채팅', '우선 응답', 'TTS'] },
];

// ---------------------------------------------------------------------------
// API mock setup
// ---------------------------------------------------------------------------

/**
 * Sets up API route interception so tests run without a real backend.
 * The user parameter determines what /api/auth/me returns.
 */
export async function setupMockAPI(
  page: Page,
  user: typeof MOCK_USER | typeof MOCK_ADMIN | typeof MOCK_ADULT_VERIFIED_USER = MOCK_USER,
) {
  // --- Auth ---
  await page.route('**/api/auth/login', (route) => {
    const request = route.request();
    if (request.method() === 'POST') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_TOKEN) });
    }
    return route.fallback();
  });

  await page.route('**/api/auth/register', async (route) => {
    const request = route.request();
    if (request.method() === 'POST') {
      const body = JSON.parse(request.postData() ?? '{}');
      if (body.nickname === 'duplicate') {
        return route.fulfill({
          status: 409,
          contentType: 'application/json',
          body: JSON.stringify({ detail: '이미 존재하는 닉네임입니다', error_code: 'AUTH_NICKNAME_EXISTS' }),
        });
      }
      return route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ id: 'new-user-001', nickname: body.nickname, role: 'user', age_group: 'unverified', adult_verified_at: null, preferred_llm_model_id: null }),
      });
    }
    return route.fallback();
  });

  await page.route('**/api/auth/me', (route) => {
    const request = route.request();
    if (request.method() === 'GET') {
      const authHeader = request.headers()['authorization'];
      if (!authHeader) {
        return route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ detail: 'Not authenticated' }) });
      }
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(user) });
    }
    if (request.method() === 'PUT') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ...user, ...JSON.parse(request.postData() ?? '{}') }) });
    }
    return route.fallback();
  });

  await page.route('**/api/auth/adult-verify', (route) => {
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ message: '성인인증이 완료되었습니다' }),
    });
  });

  // --- Personas ---
  await page.route('**/api/personas', (route) => {
    const request = route.request();
    if (request.method() === 'GET') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_PERSONAS) });
    }
    if (request.method() === 'POST') {
      const body = JSON.parse(request.postData() ?? '{}');
      const newPersona = { id: 'persona-new-001', ...body, created_by: user.id, type: 'user_created' };
      return route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify(newPersona) });
    }
    return route.fallback();
  });

  await page.route('**/api/personas/*/lorebook', (route) => {
    const request = route.request();
    if (request.method() === 'GET') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_LOREBOOK_ENTRIES) });
    }
    if (request.method() === 'POST') {
      const body = JSON.parse(request.postData() ?? '{}');
      return route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ id: 'lore-new-001', ...body }),
      });
    }
    return route.fallback();
  });

  // Persona detail (GET for editing, PUT for update) -- must come after /lorebook route
  await page.route(/\/api\/personas\/[^/]+$/, (route) => {
    const request = route.request();
    if (request.method() === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          display_name: '다크나이트',
          system_prompt: '냉소적이고 날카로운 비평가입니다.',
          style_rules: '',
          catchphrases: '',
          age_rating: '15+',
          visibility: 'public',
          live2d_model_id: '',
          background_image_url: '',
        }),
      });
    }
    if (request.method() === 'PUT') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ id: 'persona-002', message: 'updated' }) });
    }
    return route.fallback();
  });

  // --- Lorebook CRUD ---
  await page.route('**/api/lorebook/*', (route) => {
    const request = route.request();
    if (request.method() === 'PUT') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ message: 'updated' }) });
    }
    if (request.method() === 'DELETE') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ message: 'deleted' }) });
    }
    return route.fallback();
  });

  // --- Chat sessions ---
  await page.route('**/api/chat/sessions', (route) => {
    const request = route.request();
    if (request.method() === 'GET') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_SESSIONS) });
    }
    if (request.method() === 'POST') {
      return route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ id: 'session-new-001' }),
      });
    }
    return route.fallback();
  });

  await page.route('**/api/chat/sessions/*/messages', (route) => {
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_MESSAGES) });
  });

  // SSE streaming endpoint
  await page.route('**/api/chat/sessions/*/messages/stream', (route) => {
    const sseBody = [
      'data: {"type":"chunk","content":"안녕"}',
      '',
      'data: {"type":"chunk","content":"하세요! "}',
      '',
      'data: {"type":"chunk","content":"오늘 어떤 웹툰을 리뷰할까요?"}',
      '',
      'data: {"type":"emotion","emotion":"happy"}',
      '',
      'data: {"type":"done"}',
      '',
      'data: [DONE]',
      '',
    ].join('\n');

    return route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      headers: { 'Cache-Control': 'no-cache', Connection: 'keep-alive' },
      body: sseBody,
    });
  });

  // --- Models ---
  await page.route('**/api/models', (route) => {
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_MODELS) });
  });

  // --- Usage ---
  await page.route('**/api/usage/me', (route) => {
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_USAGE_SUMMARY) });
  });

  await page.route('**/api/usage/me/history', (route) => {
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_USAGE_HISTORY) });
  });

  // --- Admin APIs ---
  await page.route('**/api/admin/monitoring/stats', (route) => {
    if (user.role !== 'admin') {
      return route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({ detail: 'Forbidden' }) });
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_DASHBOARD_STATS) });
  });

  await page.route('**/api/admin/monitoring/logs*', (route) => {
    if (user.role !== 'admin') {
      return route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({ detail: 'Forbidden' }) });
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_MONITORING_LOGS) });
  });

  await page.route('**/api/admin/users', (route) => {
    const request = route.request();
    if (user.role !== 'admin') {
      return route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({ detail: 'Forbidden' }) });
    }
    if (request.method() === 'GET') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_ADMIN_USERS) });
    }
    return route.fallback();
  });

  await page.route('**/api/admin/users/*', (route) => {
    if (user.role !== 'admin') {
      return route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({ detail: 'Forbidden' }) });
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ message: 'updated' }) });
  });

  await page.route('**/api/admin/personas*', (route) => {
    if (user.role !== 'admin') {
      return route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({ detail: 'Forbidden' }) });
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_ADMIN_PERSONAS) });
  });

  await page.route('**/api/admin/personas/*/moderate', (route) => {
    if (user.role !== 'admin') {
      return route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({ detail: 'Forbidden' }) });
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ message: 'moderated' }) });
  });

  await page.route('**/api/admin/usage/summary', (route) => {
    if (user.role !== 'admin') {
      return route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({ detail: 'Forbidden' }) });
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_ADMIN_USAGE_SUMMARY) });
  });

  await page.route('**/api/admin/usage/users', (route) => {
    if (user.role !== 'admin') {
      return route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({ detail: 'Forbidden' }) });
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_ADMIN_USER_USAGES) });
  });

  await page.route('**/api/admin/usage/history', (route) => {
    if (user.role !== 'admin') {
      return route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({ detail: 'Forbidden' }) });
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_USAGE_HISTORY) });
  });

  await page.route('**/api/admin/llm-models', (route) => {
    if (user.role !== 'admin') {
      return route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({ detail: 'Forbidden' }) });
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_MODELS) });
  });

  await page.route('**/api/admin/llm-models/*', (route) => {
    if (user.role !== 'admin') {
      return route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({ detail: 'Forbidden' }) });
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ message: 'updated' }) });
  });

  await page.route('**/api/admin/content/webtoons', (route) => {
    if (user.role !== 'admin') {
      return route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({ detail: 'Forbidden' }) });
    }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        { id: 'wt-001', title: '테스트 웹툰', author: '작가A', platform: 'naver', episode_count: 50, created_at: '2026-01-01T00:00:00Z' },
      ]),
    });
  });

  // --- Favorites ---
  await page.route('**/api/favorites', (route) => {
    const request = route.request();
    if (request.method() === 'GET') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_FAVORITES) });
    }
    if (request.method() === 'POST') {
      return route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify({ message: 'added' }) });
    }
    return route.fallback();
  });

  await page.route('**/api/favorites/*', (route) => {
    if (route.request().method() === 'DELETE') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ message: 'removed' }) });
    }
    return route.fallback();
  });

  // --- Notifications ---
  await page.route('**/api/notifications', (route) => {
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_NOTIFICATIONS) });
  });

  await page.route('**/api/notifications/*/read', (route) => {
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ message: 'read' }) });
  });

  await page.route('**/api/notifications/read-all', (route) => {
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ message: 'all read' }) });
  });

  // --- Credits ---
  await page.route('**/api/credits/balance', (route) => {
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_CREDITS) });
  });

  await page.route('**/api/credits/transactions', (route) => {
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_CREDIT_TRANSACTIONS) });
  });

  // --- Community Board ---
  await page.route('**/api/board/posts', (route) => {
    const request = route.request();
    if (request.method() === 'GET') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: MOCK_COMMUNITY_POSTS, total: MOCK_COMMUNITY_POSTS.length }) });
    }
    if (request.method() === 'POST') {
      const body = JSON.parse(request.postData() ?? '{}');
      return route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify({ id: 'post-new-001', ...body }) });
    }
    return route.fallback();
  });

  await page.route('**/api/board/posts/*', (route) => {
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_COMMUNITY_POSTS[0]) });
  });

  // --- Relationships ---
  await page.route('**/api/relationships', (route) => {
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_RELATIONSHIPS) });
  });

  // --- Subscriptions ---
  await page.route('**/api/subscriptions/plans', (route) => {
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_SUBSCRIPTION_PLANS) });
  });

  await page.route('**/api/subscriptions/me', (route) => {
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ plan: 'free', status: 'active' }) });
  });

  // --- TTS ---
  await page.route('**/api/tts/synthesize-message', (route) => {
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ audio_url: '/uploads/audio/test.mp3', characters_count: 20, provider: 'openai', voice: 'alloy' }) });
  });

  await page.route('**/api/tts/voices', (route) => {
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ voices: [{ voice_id: 'alloy', name: 'Alloy', language: 'multilingual' }], provider: 'openai' }) });
  });

  // --- Image Gen ---
  await page.route('**/api/image-gen/generate', (route) => {
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ image_url: '/uploads/images/generated/test.png', prompt: 'test', style: 'anime', width: 1024, height: 1024, seed: null, provider: 'openai' }) });
  });

  // --- User Personas ---
  await page.route('**/api/user-personas', (route) => {
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });

  // --- Memories ---
  await page.route('**/api/memories', (route) => {
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });

  // --- Health ---
  await page.route('**/api/health', (route) => {
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok' }) });
  });
}

/**
 * Performs login flow on the landing page by filling the form and clicking submit.
 * After login, sets the token in localStorage and navigates based on role.
 */
export async function login(page: Page, nickname: string, password: string) {
  await page.goto('/');
  await page.getByPlaceholder('닉네임').fill(nickname);
  await page.getByPlaceholder('비밀번호').fill(password);
  await page.getByRole('button', { name: '로그인' }).click();
}

/**
 * Sets up mock API with admin role and performs the login flow.
 * This is a convenience function that combines setupMockAPI + login.
 * Do NOT call setupMockAPI separately before this function.
 */
export async function loginAsAdmin(page: Page) {
  await setupMockAPI(page, MOCK_ADMIN);
  await login(page, MOCK_ADMIN.nickname, 'adminpass');
}

/**
 * Sets up mock API with regular user role and performs the login flow.
 * This is a convenience function that combines setupMockAPI + login.
 * Do NOT call setupMockAPI separately before this function.
 */
export async function loginAsUser(page: Page) {
  await setupMockAPI(page, MOCK_USER);
  await login(page, MOCK_USER.nickname, 'userpass');
}

/**
 * Sets up mock API with adult-verified user role and performs the login flow.
 * This is a convenience function that combines setupMockAPI + login.
 * Do NOT call setupMockAPI separately before this function.
 */
export async function loginAsVerifiedUser(page: Page) {
  await setupMockAPI(page, MOCK_ADULT_VERIFIED_USER);
  await login(page, MOCK_ADULT_VERIFIED_USER.nickname, 'verifiedpass');
}

/**
 * Injects auth token directly into localStorage so pages that require
 * authentication can be visited without going through the login form.
 */
export async function injectAuth(page: Page) {
  await page.evaluate(() => {
    localStorage.setItem('token', 'mock-jwt-token-abc123');
  });
}
