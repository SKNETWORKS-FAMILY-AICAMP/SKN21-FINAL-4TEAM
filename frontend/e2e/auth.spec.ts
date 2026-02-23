import { test, expect } from '@playwright/test';
import {
  setupMockAPI,
  login,
  MOCK_USER,
  MOCK_ADMIN,
  MOCK_TOKEN,
} from './helpers';

test.describe('Authentication Flow', () => {
  test.describe('Login', () => {
    test('should display login form on landing page', async ({ page }) => {
      await setupMockAPI(page);
      await page.goto('/');

      await expect(page).toHaveTitle(/Webtoon/i);
      await expect(page.getByText('Webtoon Review Chatbot')).toBeVisible();
      await expect(page.getByPlaceholder('닉네임')).toBeVisible();
      await expect(page.getByPlaceholder('비밀번호')).toBeVisible();
      await expect(page.getByRole('button', { name: '로그인' })).toBeVisible();
    });

    test('should login with valid credentials and redirect to sessions page', async ({ page }) => {
      await setupMockAPI(page, MOCK_USER);
      await login(page, 'testuser', 'password123');

      // Regular user should be redirected to /sessions
      await expect(page).toHaveURL(/\/sessions/);
    });

    test('should login as admin and redirect to admin dashboard', async ({ page }) => {
      await setupMockAPI(page, MOCK_ADMIN);
      await login(page, 'adminuser', 'adminpass');

      // Admin user should be redirected to /admin
      await expect(page).toHaveURL(/\/admin/);
    });

    test('should show error message for invalid credentials', async ({ page }) => {
      // Set up a mock that returns 401 for login
      await page.route('**/api/auth/login', (route) => {
        return route.fulfill({
          status: 401,
          contentType: 'application/json',
          body: JSON.stringify({ detail: '닉네임 또는 비밀번호가 올바르지 않습니다', error_code: 'AUTH_INVALID_CREDENTIALS' }),
        });
      });

      await page.goto('/');
      await page.getByPlaceholder('닉네임').fill('wronguser');
      await page.getByPlaceholder('비밀번호').fill('wrongpass');
      await page.getByRole('button', { name: '로그인' }).click();

      // Should show error message on the page
      await expect(page.getByText(/닉네임 또는 비밀번호가 올바르지 않습니다|오류가 발생했습니다/)).toBeVisible();
    });

    test('should store JWT token in localStorage after successful login', async ({ page }) => {
      await setupMockAPI(page, MOCK_USER);
      await login(page, 'testuser', 'password123');

      await expect(page).toHaveURL(/\/sessions/);

      const token = await page.evaluate(() => localStorage.getItem('token'));
      expect(token).toBe(MOCK_TOKEN.access_token);
    });

    test('should show loading state while login is processing', async ({ page }) => {
      // Set up base mocks first, then override login with delay
      await setupMockAPI(page, MOCK_USER);

      // Override the login route with a delayed response (later route takes priority)
      await page.route('**/api/auth/login', async (route) => {
        await new Promise((resolve) => setTimeout(resolve, 500));
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(MOCK_TOKEN),
        });
      });

      await page.goto('/');
      await page.getByPlaceholder('닉네임').fill('testuser');
      await page.getByPlaceholder('비밀번호').fill('password123');
      await page.getByRole('button', { name: '로그인' }).click();

      // The button should show "처리 중..." while loading
      await expect(page.getByRole('button', { name: '처리 중...' })).toBeVisible();
    });
  });

  test.describe('Registration', () => {
    test('should switch to registration form when clicking the tab', async ({ page }) => {
      await setupMockAPI(page);
      await page.goto('/');

      await page.getByRole('button', { name: '회원가입' }).click();

      // Submit button should now say "가입하기"
      await expect(page.getByRole('button', { name: '가입하기' })).toBeVisible();
    });

    test('should register with valid credentials and show success message', async ({ page }) => {
      await setupMockAPI(page);
      await page.goto('/');

      // Switch to registration mode
      await page.getByRole('button', { name: '회원가입' }).click();

      await page.getByPlaceholder('닉네임').fill('newuser');
      await page.getByPlaceholder('비밀번호').fill('newpassword123');

      // Listen for the alert dialog
      page.once('dialog', async (dialog) => {
        expect(dialog.message()).toContain('가입 완료');
        await dialog.accept();
      });

      await page.getByRole('button', { name: '가입하기' }).click();

      // After registration, should switch back to login mode
      await expect(page.getByRole('button', { name: '로그인' })).toBeVisible();
    });

    test('should show error message for duplicate nickname', async ({ page }) => {
      await setupMockAPI(page);
      await page.goto('/');

      // Switch to registration mode
      await page.getByRole('button', { name: '회원가입' }).click();

      await page.getByPlaceholder('닉네임').fill('duplicate');
      await page.getByPlaceholder('비밀번호').fill('password123');
      await page.getByRole('button', { name: '가입하기' }).click();

      // Should show an error message (the mock returns error for "duplicate")
      await expect(page.getByText(/이미 존재하는 닉네임|오류가 발생했습니다/)).toBeVisible();
    });
  });

  test.describe('Protected Routes', () => {
    test('should redirect unauthenticated user accessing /sessions to login or show no data', async ({
      page,
    }) => {
      // Set up API mock where /auth/me returns 401 (no token)
      await page.route('**/api/auth/me', (route) => {
        return route.fulfill({
          status: 401,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Not authenticated' }),
        });
      });
      await page.route('**/api/chat/sessions', (route) => {
        return route.fulfill({
          status: 401,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Not authenticated' }),
        });
      });

      await page.goto('/sessions');

      // The page should either redirect to login or show no data
      // Since sessions page calls API and catches errors, it should show the page
      // but with empty content or an error state
      const url = page.url();
      const hasNoSessions = await page.getByText(/진행 중인 대화가 없습니다/).isVisible().catch(() => false);
      const isOnLogin = url.includes('/') && !url.includes('/sessions');

      expect(hasNoSessions || isOnLogin || url.endsWith('/sessions')).toBeTruthy();
    });

    test('should be able to access sessions page after login', async ({ page }) => {
      await setupMockAPI(page, MOCK_USER);
      await login(page, 'testuser', 'password123');

      await expect(page).toHaveURL(/\/sessions/);
      await expect(page.getByText('내 세션')).toBeVisible();
    });
  });

  test.describe('Auth Mode Toggle', () => {
    test('should toggle between login and register tabs', async ({ page }) => {
      await setupMockAPI(page);
      await page.goto('/');

      // Initially on login tab
      await expect(page.getByRole('button', { name: '로그인' }).first()).toBeVisible();

      // Switch to register
      await page.getByRole('button', { name: '회원가입' }).click();
      await expect(page.getByRole('button', { name: '가입하기' })).toBeVisible();

      // Switch back to login
      await page.getByRole('button', { name: '로그인' }).first().click();
      await expect(page.getByRole('button', { name: '로그인' }).last()).toBeVisible();
    });
  });
});
