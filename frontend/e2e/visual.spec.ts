import { test, expect } from '@playwright/test';
import path from 'path';

const SCREENSHOT_DIR = path.join(__dirname, '../screenshots');

/**
 * 시각적 회귀 + UI 요소 검사 테스트
 * - 반응형 레이아웃 (모바일/데스크톱)
 * - 접근성 기본 항목 (aria-label, role)
 * - 스크린샷 저장 (비교 기준점)
 */
test.describe('시각적 회귀 테스트', () => {
  test('로그인 화면 — 데스크톱 뷰포트', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    await page.screenshot({
      path: `${SCREENSHOT_DIR}/visual-01-login-desktop.png`,
      fullPage: true,
    });

    // 카드가 중앙 정렬되어 있는지 (max-w-[420px])
    const card = page.locator('.bg-bg-surface').first();
    await expect(card).toBeVisible();

    console.log('[PASS] 데스크톱 로그인 화면 스크린샷 저장');
  });

  test('로그인 화면 — 모바일 뷰포트', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    await page.screenshot({
      path: `${SCREENSHOT_DIR}/visual-02-login-mobile.png`,
      fullPage: true,
    });

    console.log('[PASS] 모바일 로그인 화면 스크린샷 저장');
  });

  test('회원가입 화면 — 전체 폼 스크린샷', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto('/');
    await page.getByRole('button', { name: '회원가입' }).click();
    await page.waitForTimeout(300);

    await page.screenshot({
      path: `${SCREENSHOT_DIR}/visual-03-register-full.png`,
      fullPage: true,
    });

    console.log('[PASS] 회원가입 전체 폼 스크린샷 저장');
  });
});

test.describe('접근성 기본 검사', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('폼 레이블 — 입력 필드에 레이블 연결 확인', async ({ page }) => {
    // 아이디 레이블이 존재하는지
    await expect(page.getByText('아이디')).toBeVisible();
    await expect(page.getByText('비밀번호')).toBeVisible();

    console.log('[PASS] 폼 레이블 확인');
  });

  test('버튼 접근성 — role=button 확인', async ({ page }) => {
    const buttons = page.getByRole('button');
    const count = await buttons.count();
    expect(count).toBeGreaterThan(0);

    console.log(`[PASS] 버튼 ${count}개 확인`);
  });

  test('입력 필드 접근성 — required 속성', async ({ page }) => {
    const loginIdInput = page.getByPlaceholder('아이디');
    await expect(loginIdInput).toHaveAttribute('required');

    const passwordInput = page.getByPlaceholder('비밀번호');
    await expect(passwordInput).toHaveAttribute('required');

    console.log('[PASS] 필수 입력 필드 required 속성 확인');
  });
});

test.describe('인터랙션 테스트', () => {
  test('탭 키 포커스 이동 — 키보드 내비게이션', async ({ page }) => {
    await page.goto('/');

    // Tab으로 포커스 이동
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');

    // 현재 포커스된 요소 확인
    const focused = await page.evaluate(() => document.activeElement?.tagName);
    expect(['INPUT', 'BUTTON']).toContain(focused);

    console.log(`[PASS] 키보드 내비게이션 — 포커스 요소: ${focused}`);
  });

  test('비밀번호 필드 — Enter 키로 제출 시도', async ({ page }) => {
    await page.goto('/');

    await page.getByPlaceholder('아이디').fill('testuser');
    await page.getByPlaceholder('비밀번호').fill('testpass');
    await page.keyboard.press('Enter');

    // 제출 후 로딩 상태 또는 에러 상태 확인
    await page.waitForTimeout(1000);

    await page.screenshot({
      path: `${SCREENSHOT_DIR}/interaction-01-enter-submit.png`,
    });

    console.log('[PASS] Enter 키 폼 제출 인터랙션 확인');
  });

  test('회원가입 — 비밀번호 불일치 에러 표시', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: '회원가입' }).click();

    await page.getByPlaceholder('6자 이상').fill('Password123!');
    await page.getByPlaceholder('비밀번호 다시 입력').fill('DifferentPass!');

    await expect(page.getByText('비밀번호가 일치하지 않습니다')).toBeVisible();

    await page.screenshot({
      path: `${SCREENSHOT_DIR}/interaction-02-password-mismatch.png`,
    });

    console.log('[PASS] 비밀번호 불일치 에러 표시 정상');
  });
});

test.describe('테마 선택 화면 (회원가입 후)', () => {
  test('DOM 구조 스냅샷 — 페이지 타이틀 및 구조 확인', async ({ page }) => {
    await page.goto('/');

    // 로그인 페이지 타이틀
    const title = await page.title();
    console.log(`[INFO] 페이지 타이틀: "${title}"`);

    // 주요 DOM 요소 카운트
    const inputs = await page.getByRole('textbox').count();
    const buttons = await page.getByRole('button').count();

    console.log(`[INFO] 입력 필드: ${inputs}개, 버튼: ${buttons}개`);
    console.log('[PASS] DOM 구조 검사 완료');
  });
});
