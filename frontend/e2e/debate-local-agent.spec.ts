import { test, expect } from '@playwright/test';
import { setupMockAPI, MOCK_USER, MOCK_TOKEN, login } from './helpers';

const MOCK_DEVELOPER = {
  id: 'dev-001',
  nickname: 'devuser',
  role: 'user' as const,
  age_group: 'adult_verified',
  adult_verified_at: '2026-01-15T00:00:00Z',
  preferred_llm_model_id: 'model-001',
};

const MOCK_AGENTS = [
  {
    id: 'agent-local-1',
    owner_id: 'dev-001',
    name: 'My Local Agent',
    description: 'Test local agent',
    provider: 'local',
    model_id: 'custom',
    elo_rating: 1500,
    wins: 0,
    losses: 0,
    draws: 0,
    is_active: true,
    is_connected: false,
    created_at: '2026-01-01',
    updated_at: '2026-01-01',
  },
];

const MOCK_AGENT_VERSIONS = [
  {
    id: 'v1',
    version_number: 1,
    version_tag: 'v1',
    system_prompt: 'Test prompt',
    parameters: null,
    wins: 0,
    losses: 0,
    draws: 0,
    created_at: '2026-01-01',
  },
];

async function setupDebateMocks(page: import('@playwright/test').Page) {
  await setupMockAPI(page, MOCK_DEVELOPER);

  // Agent API mocks
  await page.route('**/api/agents/me', (route) => {
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_AGENTS),
    });
  });

  await page.route('**/api/agents', (route) => {
    const request = route.request();
    if (request.method() === 'POST') {
      const body = JSON.parse(request.postData() ?? '{}');
      const newAgent = {
        id: 'agent-new-1',
        owner_id: 'dev-001',
        name: body.name,
        description: body.description || null,
        provider: body.provider,
        model_id: body.model_id || 'custom',
        elo_rating: 1500,
        wins: 0,
        losses: 0,
        draws: 0,
        is_active: true,
        is_connected: false,
        created_at: '2026-01-01',
        updated_at: '2026-01-01',
      };
      return route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify(newAgent),
      });
    }
    return route.fallback();
  });

  await page.route(/\/api\/agents\/[^/]+\/versions$/, (route) => {
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_AGENT_VERSIONS),
    });
  });

  await page.route(/\/api\/agents\/[^/]+$/, (route) => {
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_AGENTS[0]),
    });
  });

  // Topics/ranking
  await page.route('**/api/topics*', (route) => {
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: [], total: 0 }),
    });
  });

  await page.route('**/api/agents/ranking', (route) => {
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    });
  });
}

test.describe('Local Agent Flow', () => {
  test('should display local agent in agent list', async ({ page }) => {
    await setupDebateMocks(page);
    await login(page, MOCK_DEVELOPER.nickname, 'devpass');

    await page.goto('/debate/agents');
    await expect(page.getByText('My Local Agent')).toBeVisible();
    await expect(page.getByText('로컬')).toBeVisible();
  });

  test('should show agent creation form with local provider option', async ({ page }) => {
    await setupDebateMocks(page);
    await login(page, MOCK_DEVELOPER.nickname, 'devpass');

    await page.goto('/debate/agents/create');
    const providerSelect = page.locator('select');
    await providerSelect.selectOption('local');

    // API Key field should be hidden, WebSocket guide should be visible
    await expect(page.getByText('WebSocket 연결 안내')).toBeVisible();
    await expect(page.getByPlaceholder('sk-...')).not.toBeVisible();
  });

  test('should create local agent without API key', async ({ page }) => {
    await setupDebateMocks(page);
    await login(page, MOCK_DEVELOPER.nickname, 'devpass');

    await page.goto('/debate/agents/create');
    await page.locator('select').selectOption('local');
    await page.getByPlaceholder('My Debate Agent').fill('New Local Agent');
    await page.locator('textarea').fill('Test system prompt for local agent');

    await page.getByRole('button', { name: '에이전트 생성' }).click();

    // Should redirect to agents list
    await page.waitForURL('**/debate/agents');
  });

  test('should show connection guide on agent detail page', async ({ page }) => {
    await setupDebateMocks(page);
    await login(page, MOCK_DEVELOPER.nickname, 'devpass');

    await page.goto('/debate/agents/agent-local-1');

    // Connection guide should be visible for local agents
    await expect(page.getByText(/WebSocket 연결/)).toBeVisible();
    await expect(page.getByText(/ws:\/\/.*\/ws\/agent\/agent-local-1/)).toBeVisible();
  });
});
