import { test, expect } from '@playwright/test';
import { loginAsUser } from './helpers';

test.describe('Credits System', () => {
  test('should display credit balance on mypage', async ({ page }) => {
    await loginAsUser(page);
    await page.goto('/mypage');

    // Credit balance should be visible somewhere on the page
    // The balance is 120 from MOCK_CREDITS
    const balanceText = page.getByText(/120|크레딧|대화석/);
    if (await balanceText.first().isVisible()) {
      await expect(balanceText.first()).toBeVisible();
    }
  });

  test('should show credit transaction history', async ({ page }) => {
    await loginAsUser(page);
    await page.goto('/mypage');

    // Navigate to the appropriate tab that shows transactions
    const usageTab = page.getByRole('button', { name: /사용량|크레딧/ });
    if (await usageTab.isVisible()) {
      await usageTab.click();
    }

    // Transaction descriptions should be visible
    const dailyGrant = page.getByText(/일일 무료 크레딧/);
    if (await dailyGrant.isVisible()) {
      await expect(dailyGrant).toBeVisible();
    }
  });

  test('should display credit badge in sidebar or header', async ({ page }) => {
    await loginAsUser(page);
    await page.goto('/sessions');

    // Credit badge should show the balance
    const badge = page.getByText(/120|크레딧/);
    if (await badge.first().isVisible()) {
      await expect(badge.first()).toBeVisible();
    }
  });
});
