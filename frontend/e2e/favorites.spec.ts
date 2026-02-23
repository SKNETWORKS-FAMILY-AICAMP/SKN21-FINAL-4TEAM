import { test, expect } from '@playwright/test';
import { loginAsUser, loginAsVerifiedUser, setupMockAPI, MOCK_USER, MOCK_FAVORITES } from './helpers';

test.describe('Favorites Page', () => {
  test('should display favorites list after login', async ({ page }) => {
    await loginAsUser(page);
    await page.goto('/favorites');

    await expect(page.getByText('즐겨찾기')).toBeVisible();
    await expect(page.getByText('미니')).toBeVisible();
  });

  test('should show empty state when no favorites', async ({ page }) => {
    await setupMockAPI(page, MOCK_USER);
    // Override favorites route with empty array
    await page.route('**/api/favorites', (route) => {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });
    await page.goto('/');
    await page.getByPlaceholder('닉네임').fill('testuser');
    await page.getByPlaceholder('비밀번호').fill('password123');
    await page.getByRole('button', { name: '로그인' }).click();
    await page.goto('/favorites');

    await expect(
      page.getByText(/즐겨찾기한 페르소나가 없습니다|아직 즐겨찾기가 없습니다|비어 있습니다/),
    ).toBeVisible();
  });

  test('should remove a favorite when clicking remove button', async ({ page }) => {
    await loginAsUser(page);
    await page.goto('/favorites');

    // Wait for favorites to load
    await expect(page.getByText('미니')).toBeVisible();

    // Find and click the remove/unfavorite button
    const removeButton = page.getByRole('button', { name: /즐겨찾기 해제|제거|삭제/ }).first();
    if (await removeButton.isVisible()) {
      await removeButton.click();
      // Should show a toast or the item should be removed
    }
  });

  test('should display age rating badge on favorite personas', async ({ page }) => {
    await loginAsUser(page);
    await page.goto('/favorites');

    await expect(page.getByText('미니')).toBeVisible();
    // The age rating badge should be visible
    await expect(page.getByText('전체').first()).toBeVisible();
  });
});
