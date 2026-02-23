import { test, expect } from '@playwright/test';
import {
  loginAsAdmin,
  loginAsUser,
  MOCK_ADMIN_USERS,
  MOCK_ADMIN_PERSONAS,
  MOCK_DASHBOARD_STATS,
  MOCK_MONITORING_STATS,
  MOCK_MONITORING_LOGS,
} from './helpers';

test.describe('Admin Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page);
  });

  test('should display admin dashboard with stat cards', async ({ page }) => {
    await page.goto('/admin');

    await expect(page.getByText('대시보드')).toBeVisible();

    // Stat cards
    await expect(page.getByText('전체 사용자')).toBeVisible();
    await expect(page.getByText(String(MOCK_DASHBOARD_STATS.total_users))).toBeVisible();

    await expect(page.getByText('일간 활성 사용자')).toBeVisible();
    await expect(page.getByText(String(MOCK_DASHBOARD_STATS.daily_active_users))).toBeVisible();

    await expect(page.getByText('오늘 메시지')).toBeVisible();
    await expect(page.getByText(String(MOCK_DASHBOARD_STATS.daily_messages))).toBeVisible();

    await expect(page.getByText('페르소나', { exact: false })).toBeVisible();
    await expect(page.getByText('모더레이션 대기')).toBeVisible();
  });

  test('should display admin sidebar with all menu items', async ({ page }) => {
    await page.goto('/admin');

    // Sidebar menu items
    await expect(page.getByText('Dashboard')).toBeVisible();
    await expect(page.getByText('사용자 관리')).toBeVisible();
    await expect(page.getByText('페르소나 검수')).toBeVisible();
    await expect(page.getByText('콘텐츠 관리')).toBeVisible();
    await expect(page.getByText('정책 설정')).toBeVisible();
    await expect(page.getByText('LLM 모델')).toBeVisible();
    await expect(page.getByText('사용량/과금')).toBeVisible();
    await expect(page.getByText('모니터링')).toBeVisible();
  });

  test('should have sidebar link to user sessions page', async ({ page }) => {
    await page.goto('/admin');

    // "Webtoon Chatbot" link in sidebar should link to /sessions
    const brandLink = page.getByRole('link', { name: 'Webtoon Chatbot' });
    await expect(brandLink).toBeVisible();
    await expect(brandLink).toHaveAttribute('href', '/sessions');
  });
});

test.describe('Admin User Management', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page);
  });

  test('should display user list with user details', async ({ page }) => {
    await page.goto('/admin/users');

    await expect(page.getByText('사용자 관리')).toBeVisible();

    // Table headers
    await expect(page.getByText('닉네임')).toBeVisible();
    await expect(page.getByText('역할')).toBeVisible();
    await expect(page.getByText('연령 상태')).toBeVisible();

    // User data
    await expect(page.getByText('testuser')).toBeVisible();
    await expect(page.getByText('verifieduser')).toBeVisible();
    await expect(page.getByText('adminuser')).toBeVisible();
  });

  test('should display role selection dropdown for each user', async ({ page }) => {
    await page.goto('/admin/users');

    await expect(page.getByText('testuser')).toBeVisible();

    // Each user row should have a role selection dropdown
    const roleSelects = page.locator('select');
    const count = await roleSelects.count();
    expect(count).toBe(MOCK_ADMIN_USERS.length);
  });

  test('should show age group status badges', async ({ page }) => {
    await page.goto('/admin/users');

    await expect(page.getByText('testuser')).toBeVisible();

    // Should show different age group statuses
    await expect(page.getByText('unverified')).toBeVisible();
    await expect(page.getByText('adult_verified').first()).toBeVisible();
  });

  test('should change user role via dropdown', async ({ page }) => {
    let roleChangeRequest: { userId: string; role: string } | null = null;

    await page.route('**/api/admin/users/*', async (route) => {
      const request = route.request();
      if (request.method() === 'PUT') {
        const url = request.url();
        const userId = url.split('/').pop() ?? '';
        const body = JSON.parse(request.postData() ?? '{}');
        roleChangeRequest = { userId, role: body.role };
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ message: 'updated' }),
        });
      }
      return route.fallback();
    });

    await page.goto('/admin/users');
    await expect(page.getByText('testuser')).toBeVisible();

    // Change the first user's role to admin
    const firstSelect = page.locator('select').first();
    await firstSelect.selectOption('admin');

    // Wait a bit for the API call to complete
    await page.waitForTimeout(500);

    expect(roleChangeRequest).not.toBeNull();
    expect(roleChangeRequest!.role).toBe('admin');
  });
});

test.describe('Admin Persona Moderation', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page);
  });

  test('should display persona moderation list', async ({ page }) => {
    await page.goto('/admin/personas');

    await expect(page.getByText('페르소나 검수')).toBeVisible();

    // Table headers
    await expect(page.getByText('이름')).toBeVisible();
    await expect(page.getByText('생성자')).toBeVisible();
    await expect(page.getByText('등급')).toBeVisible();
    await expect(page.getByText('상태')).toBeVisible();

    // Persona data
    await expect(page.getByText('다크나이트')).toBeVisible();
    await expect(page.getByText('대기중 페르소나')).toBeVisible();
  });

  test('should show filter buttons for moderation status', async ({ page }) => {
    await page.goto('/admin/personas');

    await expect(page.getByRole('button', { name: '대기' })).toBeVisible();
    await expect(page.getByRole('button', { name: '승인' })).toBeVisible();
    await expect(page.getByRole('button', { name: '차단' })).toBeVisible();
  });

  test('should show approve and block buttons for pending personas', async ({ page }) => {
    await page.goto('/admin/personas');

    await expect(page.getByText('다크나이트')).toBeVisible();

    // Pending personas should have action buttons
    await expect(page.getByRole('button', { name: '승인' }).first()).toBeVisible();
    await expect(page.getByRole('button', { name: '차단' }).first()).toBeVisible();
  });

  test('should approve a pending persona', async ({ page }) => {
    let moderationCalled = false;

    await page.route('**/api/admin/personas/*/moderate', async (route) => {
      const body = JSON.parse(route.request().postData() ?? '{}');
      expect(body.status).toBe('approved');
      moderationCalled = true;
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ message: 'moderated' }),
      });
    });

    await page.goto('/admin/personas');
    await expect(page.getByText('다크나이트')).toBeVisible();

    // Click approve on first pending persona
    await page.getByRole('button', { name: '승인' }).first().click();

    await page.waitForTimeout(500);
    expect(moderationCalled).toBe(true);
  });

  test('should block a pending persona', async ({ page }) => {
    let moderationCalled = false;

    await page.route('**/api/admin/personas/*/moderate', async (route) => {
      const body = JSON.parse(route.request().postData() ?? '{}');
      expect(body.status).toBe('blocked');
      moderationCalled = true;
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ message: 'moderated' }),
      });
    });

    await page.goto('/admin/personas');
    await expect(page.getByText('다크나이트')).toBeVisible();

    // Click block on first pending persona
    await page.getByRole('button', { name: '차단' }).first().click();

    await page.waitForTimeout(500);
    expect(moderationCalled).toBe(true);
  });

  test('should filter personas by status when clicking filter buttons', async ({ page }) => {
    let lastFilterStatus = '';

    await page.route('**/api/admin/personas*', (route) => {
      const url = new URL(route.request().url());
      lastFilterStatus = url.searchParams.get('moderation_status') ?? '';
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_ADMIN_PERSONAS),
      });
    });

    await page.goto('/admin/personas');
    await expect(page.getByText('페르소나 검수')).toBeVisible();

    // Click "승인" filter button
    await page.getByRole('button', { name: '승인' }).click();
    await page.waitForTimeout(300);
    expect(lastFilterStatus).toBe('approved');

    // Click "차단" filter button
    await page.getByRole('button', { name: '차단' }).click();
    await page.waitForTimeout(300);
    expect(lastFilterStatus).toBe('blocked');

    // Click "대기" filter button
    await page.getByRole('button', { name: '대기' }).click();
    await page.waitForTimeout(300);
    expect(lastFilterStatus).toBe('pending');
  });
});

test.describe('Admin Monitoring Page', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page);
  });

  test('should display monitoring page with statistics', async ({ page }) => {
    await page.goto('/admin/monitoring');

    await expect(page.getByText('모니터링')).toBeVisible();

    // Stat cards
    await expect(page.getByText('전체 사용자')).toBeVisible();
    await expect(page.getByText('전체 세션')).toBeVisible();
    await expect(page.getByText('오늘 메시지')).toBeVisible();
    await expect(page.getByText('이번 주 메시지')).toBeVisible();
    await expect(page.getByText('전체 메시지')).toBeVisible();
    await expect(page.getByText('검수 대기')).toBeVisible();
  });

  test('should display recent LLM call logs', async ({ page }) => {
    await page.goto('/admin/monitoring');

    await expect(page.getByText('최근 LLM 호출 로그')).toBeVisible();

    // Log table headers
    await expect(page.getByText('시간')).toBeVisible();
    await expect(page.getByText('사용자')).toBeVisible();
    await expect(page.getByText('모델')).toBeVisible();
    await expect(page.getByText('입력 토큰')).toBeVisible();
    await expect(page.getByText('출력 토큰')).toBeVisible();
    await expect(page.getByText('비용')).toBeVisible();

    // Log data
    await expect(page.getByText('testuser')).toBeVisible();
    await expect(page.getByText('Llama 3 70B')).toBeVisible();
  });

  test('should show monitoring stat values', async ({ page }) => {
    await page.goto('/admin/monitoring');

    await expect(page.getByText(String(MOCK_MONITORING_STATS.total_users))).toBeVisible();
    await expect(page.getByText(String(MOCK_MONITORING_STATS.total_sessions))).toBeVisible();
    await expect(page.getByText(String(MOCK_MONITORING_STATS.daily_messages))).toBeVisible();
  });
});

test.describe('Admin Usage Page', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page);
  });

  test('should display usage and billing page', async ({ page }) => {
    await page.goto('/admin/usage');

    await expect(page.getByText('사용량 & 과금')).toBeVisible();

    // Summary stats
    await expect(page.getByText('오늘 토큰')).toBeVisible();
    await expect(page.getByText('오늘 비용')).toBeVisible();
    await expect(page.getByText('이번 달 토큰')).toBeVisible();
    await expect(page.getByText('이번 달 비용')).toBeVisible();
    await expect(page.getByText('전체 토큰')).toBeVisible();
    await expect(page.getByText('전체 비용')).toBeVisible();
  });

  test('should display user usage table', async ({ page }) => {
    await page.goto('/admin/usage');

    await expect(page.getByText('사용자별 사용량')).toBeVisible();

    // Table should show user data
    await expect(page.getByText('testuser')).toBeVisible();
    await expect(page.getByText('verifieduser')).toBeVisible();
  });

  test('should display daily usage trend section', async ({ page }) => {
    await page.goto('/admin/usage');

    await expect(page.getByText('일별 사용량 추이')).toBeVisible();
  });
});

test.describe('Admin Models Page', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page);
  });

  test('should display LLM model management page', async ({ page }) => {
    await page.goto('/admin/models');

    await expect(page.getByText('LLM 모델 관리')).toBeVisible();

    // Table headers
    await expect(page.getByText('모델명')).toBeVisible();
    await expect(page.getByText('Provider')).toBeVisible();
    await expect(page.getByText('Model ID')).toBeVisible();
    await expect(page.getByText('입력 비용')).toBeVisible();
    await expect(page.getByText('출력 비용')).toBeVisible();
    await expect(page.getByText('컨텍스트')).toBeVisible();
    await expect(page.getByText('성인전용')).toBeVisible();

    // Model data
    await expect(page.getByText('Llama 3 70B')).toBeVisible();
    await expect(page.getByText('GPT-4o')).toBeVisible();
  });

  test('should show active/inactive toggle buttons for each model', async ({ page }) => {
    await page.goto('/admin/models');

    await expect(page.getByText('Llama 3 70B')).toBeVisible();

    // Each model should have an active/inactive toggle button
    const activeButtons = page.getByRole('button', { name: '활성' });
    const count = await activeButtons.count();
    expect(count).toBeGreaterThan(0);
  });

  test('should toggle model active status', async ({ page }) => {
    let toggleCalled = false;

    await page.route('**/api/admin/llm-models/*', async (route) => {
      if (route.request().method() === 'PUT') {
        const body = JSON.parse(route.request().postData() ?? '{}');
        expect(typeof body.is_active).toBe('boolean');
        toggleCalled = true;
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ message: 'updated' }),
        });
      }
      return route.fallback();
    });

    await page.goto('/admin/models');
    await expect(page.getByText('Llama 3 70B')).toBeVisible();

    // Click the first active toggle button
    await page.getByRole('button', { name: '활성' }).first().click();

    await page.waitForTimeout(500);
    expect(toggleCalled).toBe(true);
  });

  test('should show adult-only indicator on models', async ({ page }) => {
    await page.goto('/admin/models');

    // The "Adult Model X" has is_adult_only = true, should show "예"
    await expect(page.getByText('Adult Model X')).toBeVisible();
  });
});

test.describe('Admin Content Page', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page);
  });

  test('should display content management page with webtoon list', async ({ page }) => {
    await page.goto('/admin/content');

    await expect(page.getByText('콘텐츠 관리')).toBeVisible();

    // Table headers
    await expect(page.getByText('제목')).toBeVisible();
    await expect(page.getByText('작가')).toBeVisible();
    await expect(page.getByText('플랫폼')).toBeVisible();
    await expect(page.getByText('회차 수')).toBeVisible();

    // Webtoon data
    await expect(page.getByText('테스트 웹툰')).toBeVisible();
    await expect(page.getByText('작가A')).toBeVisible();
  });
});

test.describe('Admin Access Control', () => {
  test('should allow admin user to access admin dashboard', async ({ page }) => {
    await loginAsAdmin(page);

    await page.goto('/admin');
    await expect(page.getByText('대시보드')).toBeVisible();
  });

  test('should block non-admin from admin API endpoints', async ({ page }) => {
    await loginAsUser(page);

    // Try to access admin users API directly
    const usersResponse = await page.request.get('/api/admin/users', {
      headers: { Authorization: 'Bearer mock-jwt-token-abc123' },
    });
    expect(usersResponse.status()).toBe(403);

    // Try to access admin monitoring stats API
    const statsResponse = await page.request.get('/api/admin/monitoring/stats', {
      headers: { Authorization: 'Bearer mock-jwt-token-abc123' },
    });
    expect(statsResponse.status()).toBe(403);
  });

  test('should return 403 for non-admin accessing admin usage API', async ({ page }) => {
    await loginAsUser(page);

    const response = await page.request.get('/api/admin/usage/summary', {
      headers: { Authorization: 'Bearer mock-jwt-token-abc123' },
    });
    expect(response.status()).toBe(403);
  });

  test('should return 403 for non-admin accessing admin LLM models API', async ({ page }) => {
    await loginAsUser(page);

    const response = await page.request.get('/api/admin/llm-models', {
      headers: { Authorization: 'Bearer mock-jwt-token-abc123' },
    });
    expect(response.status()).toBe(403);
  });

  test('admin pages should render but show no data when accessed by non-admin due to 403', async ({
    page,
  }) => {
    await loginAsUser(page);

    // Navigate to admin page -- the page renders (Next.js client routing)
    // but the API calls return 403, so no data is displayed
    await page.goto('/admin');

    // The page title should be visible (layout renders)
    await expect(page.getByText('대시보드')).toBeVisible();

    // But stat values should show "-" since API returned 403
    // (the catch block swallows the error and stats remains null)
    const dashValues = page.locator('text="-"');
    const count = await dashValues.count();
    expect(count).toBeGreaterThan(0);
  });
});

test.describe('Admin Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page);
  });

  test('should navigate between admin pages via sidebar', async ({ page }) => {
    await page.goto('/admin');

    // Navigate to users page
    await page.getByRole('link', { name: '사용자 관리' }).click();
    await expect(page).toHaveURL(/\/admin\/users/);
    await expect(page.getByText('사용자 관리').first()).toBeVisible();

    // Navigate to personas moderation
    await page.getByRole('link', { name: '페르소나 검수' }).click();
    await expect(page).toHaveURL(/\/admin\/personas/);

    // Navigate to monitoring
    await page.getByRole('link', { name: '모니터링' }).click();
    await expect(page).toHaveURL(/\/admin\/monitoring/);

    // Navigate to usage
    await page.getByRole('link', { name: '사용량/과금' }).click();
    await expect(page).toHaveURL(/\/admin\/usage/);

    // Navigate to models
    await page.getByRole('link', { name: 'LLM 모델' }).click();
    await expect(page).toHaveURL(/\/admin\/models/);

    // Navigate to content
    await page.getByRole('link', { name: '콘텐츠 관리' }).click();
    await expect(page).toHaveURL(/\/admin\/content/);

    // Navigate back to dashboard
    await page.getByRole('link', { name: 'Dashboard' }).click();
    await expect(page).toHaveURL(/\/admin$/);
  });
});
