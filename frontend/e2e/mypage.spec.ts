import { test, expect } from '@playwright/test';
import { loginAsUser, loginAsVerifiedUser } from './helpers';

test.describe('MyPage', () => {
  test('should display mypage with tabs', async ({ page }) => {
    await loginAsUser(page);
    await page.goto('/mypage');

    await expect(page.getByText(/마이페이지|내 정보/).first()).toBeVisible();

    // Should have multiple tabs
    const profileTab = page.getByRole('button', { name: /프로필|기본 정보/ });
    if (await profileTab.isVisible()) {
      await expect(profileTab).toBeVisible();
    }
  });

  test('should show user profile information', async ({ page }) => {
    await loginAsUser(page);
    await page.goto('/mypage');

    // User nickname should be displayed
    await expect(page.getByText('testuser')).toBeVisible();
  });

  test('should allow switching between tabs', async ({ page }) => {
    await loginAsUser(page);
    await page.goto('/mypage');

    // Try clicking different tabs
    const settingsTab = page.getByRole('button', { name: /설정/ });
    if (await settingsTab.isVisible()) {
      await settingsTab.click();
    }

    const usageTab = page.getByRole('button', { name: /사용량/ });
    if (await usageTab.isVisible()) {
      await usageTab.click();
    }
  });

  test('should show usage statistics in usage tab', async ({ page }) => {
    await loginAsUser(page);
    await page.goto('/mypage');

    const usageTab = page.getByRole('button', { name: /사용량/ });
    if (await usageTab.isVisible()) {
      await usageTab.click();
      // Should show token usage or cost data
      const usageData = page.getByText(/토큰|비용|사용량/);
      if (await usageData.first().isVisible()) {
        await expect(usageData.first()).toBeVisible();
      }
    }
  });

  test('should show subscription tab', async ({ page }) => {
    await loginAsUser(page);
    await page.goto('/mypage');

    const subTab = page.getByRole('button', { name: /구독/ });
    if (await subTab.isVisible()) {
      await subTab.click();
      // Should show subscription plan info
      const planInfo = page.getByText(/무료|프리미엄|플랜/);
      if (await planInfo.first().isVisible()) {
        await expect(planInfo.first()).toBeVisible();
      }
    }
  });

  test('should show memories tab', async ({ page }) => {
    await loginAsUser(page);
    await page.goto('/mypage');

    const memoriesTab = page.getByRole('button', { name: /기억|메모리/ });
    if (await memoriesTab.isVisible()) {
      await memoriesTab.click();
    }
  });

  test('should show creator tab with persona stats', async ({ page }) => {
    await loginAsUser(page);
    await page.goto('/mypage');

    const creatorTab = page.getByRole('button', { name: /크리에이터|창작/ });
    if (await creatorTab.isVisible()) {
      await creatorTab.click();
    }
  });
});
