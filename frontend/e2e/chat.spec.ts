import { test, expect } from '@playwright/test';
import {
  loginAsUser,
  MOCK_SESSIONS,
  MOCK_MESSAGES,
} from './helpers';

test.describe('Sessions Page', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsUser(page);
  });

  test('should display sessions list with session details', async ({ page }) => {
    await page.goto('/sessions');

    await expect(page.getByText('내 세션')).toBeVisible();

    // Session list should show persona names
    await expect(page.getByText('미니')).toBeVisible();
    await expect(page.getByText('다크나이트')).toBeVisible();

    // Should show LLM model names
    await expect(page.getByText('Llama 3 70B')).toBeVisible();
    await expect(page.getByText('GPT-4o')).toBeVisible();

    // Should show message counts
    await expect(page.getByText('12개 메시지')).toBeVisible();
    await expect(page.getByText('5개 메시지')).toBeVisible();
  });

  test('should display age rating badges on sessions', async ({ page }) => {
    await page.goto('/sessions');

    await expect(page.getByText('미니')).toBeVisible();

    // Age rating badges
    await expect(page.getByText('전체')).toBeVisible();
    await expect(page.getByText('15+')).toBeVisible();
  });

  test('should show "새 대화" button that navigates to personas', async ({ page }) => {
    await page.goto('/sessions');

    const newChatButton = page.getByRole('button', { name: '+ 새 대화' });
    await expect(newChatButton).toBeVisible();

    await newChatButton.click();
    await expect(page).toHaveURL(/\/personas/);
  });

  test('should show empty state when no sessions exist', async ({ page }) => {
    // Override sessions endpoint to return empty array
    await page.route('**/api/chat/sessions', (route) => {
      if (route.request().method() === 'GET') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([]),
        });
      }
      return route.fallback();
    });

    await page.goto('/sessions');

    await expect(page.getByText('진행 중인 대화가 없습니다.')).toBeVisible();
    await expect(
      page.getByRole('button', { name: '페르소나를 선택하고 대화를 시작해보세요' }),
    ).toBeVisible();
  });

  test('should navigate to chat page when clicking on a session', async ({ page }) => {
    await page.goto('/sessions');

    await expect(page.getByText('미니')).toBeVisible();

    // Click on the first session card
    await page.getByText('미니').click();
    await expect(page).toHaveURL(/\/chat\/session-001/);
  });
});

test.describe('Creating a Chat Session', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsUser(page);
  });

  test('should create a new session when clicking "대화하기" on persona', async ({ page }) => {
    let sessionCreateCalled = false;
    await page.route('**/api/chat/sessions', (route) => {
      const request = route.request();
      if (request.method() === 'POST') {
        sessionCreateCalled = true;
        const body = JSON.parse(request.postData() ?? '{}');
        expect(body.persona_id).toBe('persona-001');
        return route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({ id: 'session-new-001' }),
        });
      }
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_SESSIONS),
      });
    });

    await page.goto('/personas');
    await expect(page.getByText('미니')).toBeVisible();

    // Click "대화하기" on the first persona (미니, which is "all" rating)
    await page.getByRole('button', { name: '대화하기' }).first().click();

    // Should create a session and redirect to chat
    await expect(page).toHaveURL(/\/chat\/session-new-001/);
    expect(sessionCreateCalled).toBe(true);
  });
});

test.describe('Chat Window', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsUser(page);
  });

  test('should display chat page with message history', async ({ page }) => {
    await page.goto('/chat/session-001');

    // Wait for messages to load
    await expect(page.getByText('안녕하세요!')).toBeVisible();
    await expect(page.getByText('무슨 웹툰에 대해 이야기하고 싶으세요?')).toBeVisible();
  });

  test('should show user and assistant message labels', async ({ page }) => {
    await page.goto('/chat/session-001');

    await expect(page.getByText('안녕하세요!')).toBeVisible();

    // User messages should have "나" label, assistant should have "캐릭터"
    await expect(page.getByText('나')).toBeVisible();
    await expect(page.getByText('캐릭터')).toBeVisible();
  });

  test('should display emotion signal on assistant messages', async ({ page }) => {
    await page.goto('/chat/session-001');

    await expect(page.getByText('안녕하세요!')).toBeVisible();

    // The assistant message has emotion_signal: 'happy'
    await expect(page.getByText('happy')).toBeVisible();
  });

  test('should show message input area with send button', async ({ page }) => {
    await page.goto('/chat/session-001');

    await expect(page.getByPlaceholder('메시지를 입력하세요...')).toBeVisible();
    await expect(page.getByRole('button', { name: '전송' })).toBeVisible();
  });

  test('should disable send button when input is empty', async ({ page }) => {
    await page.goto('/chat/session-001');

    const sendButton = page.getByRole('button', { name: '전송' });
    await expect(sendButton).toBeDisabled();
  });

  test('should enable send button when text is entered', async ({ page }) => {
    await page.goto('/chat/session-001');

    const input = page.getByPlaceholder('메시지를 입력하세요...');
    await input.fill('테스트 메시지');

    const sendButton = page.getByRole('button', { name: '전송' });
    await expect(sendButton).toBeEnabled();
  });

  test('should send message and display it in chat', async ({ page }) => {
    await page.goto('/chat/session-001');

    await expect(page.getByText('안녕하세요!')).toBeVisible();

    // Type and send a message
    const input = page.getByPlaceholder('메시지를 입력하세요...');
    await input.fill('새로운 메시지입니다');
    await page.getByRole('button', { name: '전송' }).click();

    // The user message should appear in the chat
    await expect(page.getByText('새로운 메시지입니다')).toBeVisible();

    // Input should be cleared after sending
    await expect(input).toHaveValue('');
  });

  test('should receive streaming SSE response after sending message', async ({ page }) => {
    await page.goto('/chat/session-001');

    await expect(page.getByText('안녕하세요!')).toBeVisible();

    // Send a message
    const input = page.getByPlaceholder('메시지를 입력하세요...');
    await input.fill('안녕!');
    await page.getByRole('button', { name: '전송' }).click();

    // The SSE mock sends chunks: "안녕" + "하세요! " + "오늘 어떤 웹툰을 리뷰할까요?"
    // Wait for the full streamed response to appear
    await expect(page.getByText('오늘 어떤 웹툰을 리뷰할까요?', { exact: false })).toBeVisible({
      timeout: 5000,
    });
  });

  test('should show empty chat state for new session', async ({ page }) => {
    // Mock empty message history
    await page.route('**/api/chat/sessions/*/messages', (route) => {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });

    await page.goto('/chat/session-001');

    await expect(page.getByText('대화를 시작해보세요!')).toBeVisible();
  });

  test('should support Enter key to send message', async ({ page }) => {
    await page.goto('/chat/session-001');

    await expect(page.getByText('안녕하세요!')).toBeVisible();

    const input = page.getByPlaceholder('메시지를 입력하세요...');
    await input.fill('엔터로 보내기');
    await input.press('Enter');

    // The message should appear
    await expect(page.getByText('엔터로 보내기')).toBeVisible();
  });

  test('should not send message on Shift+Enter (allows newline)', async ({ page }) => {
    await page.goto('/chat/session-001');

    const input = page.getByPlaceholder('메시지를 입력하세요...');
    await input.fill('줄바꿈');
    await input.press('Shift+Enter');

    // The message should NOT be sent (still in input)
    // The text should still be in the input field
    const currentVal = await input.inputValue();
    expect(currentVal).toContain('줄바꿈');
  });
});

test.describe('Settings Page', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsUser(page);
  });

  test('should display settings page with model selection', async ({ page }) => {
    await page.goto('/settings');

    await expect(page.getByText('설정')).toBeVisible();
    await expect(page.getByText('LLM 모델 선택')).toBeVisible();
    await expect(page.getByText('대화에 사용할 AI 모델을 선택하세요.')).toBeVisible();

    // Should show available models
    await expect(page.getByText('Llama 3 70B')).toBeVisible();
    await expect(page.getByText('GPT-4o')).toBeVisible();
  });

  test('should display model cost information', async ({ page }) => {
    await page.goto('/settings');

    await expect(page.getByText('Llama 3 70B')).toBeVisible();

    // Cost info should be visible
    await expect(page.getByText('입력: $0.59/1M')).toBeVisible();
    await expect(page.getByText('출력: $0.79/1M')).toBeVisible();
  });

  test('should show adult-only model as locked for unverified user', async ({ page }) => {
    await page.goto('/settings');

    // The "Adult Model X" should be visible but locked (opacity-50)
    await expect(page.getByText('Adult Model X')).toBeVisible();
    await expect(page.getByText('성인전용')).toBeVisible();
  });

  test('should show adult verification section', async ({ page }) => {
    await page.goto('/settings');

    await expect(page.getByText('성인인증')).toBeVisible();
    await expect(page.getByText('18+ 콘텐츠 이용을 위해 성인인증이 필요합니다.')).toBeVisible();
    await expect(
      page.getByRole('button', { name: /성인인증 하기/ }),
    ).toBeVisible();
  });
});

test.describe('Usage Page', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsUser(page);
  });

  test('should display usage page with token statistics', async ({ page }) => {
    await page.goto('/usage');

    await expect(page.getByText('사용량')).toBeVisible();

    // Daily stats
    await expect(page.getByText('오늘')).toBeVisible();
    await expect(page.getByText('2,000 토큰')).toBeVisible();

    // Monthly stats
    await expect(page.getByText('이번 달')).toBeVisible();
    await expect(page.getByText('35,000 토큰')).toBeVisible();

    // Total stats
    await expect(page.getByText('전체')).toBeVisible();
    await expect(page.getByText('50,000 토큰')).toBeVisible();
  });

  test('should display model-specific usage section', async ({ page }) => {
    await page.goto('/usage');

    await expect(page.getByText('모델별 사용량')).toBeVisible();
  });

  test('should display daily usage chart section', async ({ page }) => {
    await page.goto('/usage');

    await expect(page.getByText('일별 사용량')).toBeVisible();
  });
});
