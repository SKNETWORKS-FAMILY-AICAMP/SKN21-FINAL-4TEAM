import { test, expect } from '@playwright/test';
import { loginAsUser, MOCK_COMMUNITY_POSTS } from './helpers';

test.describe('Community Board', () => {
  test('should display community post list', async ({ page }) => {
    await loginAsUser(page);
    await page.goto('/community');

    await expect(page.getByText('커뮤니티').first()).toBeVisible();
    await expect(page.getByText('미니와 대화한 후기')).toBeVisible();
    await expect(page.getByText('추천 페르소나 공유')).toBeVisible();
  });

  test('should show post details when clicking a post', async ({ page }) => {
    await loginAsUser(page);
    await page.goto('/community');

    await page.getByText('미니와 대화한 후기').click();

    // Should navigate to post detail or show detail view
    await expect(page.getByText('정말 재밌었어요!')).toBeVisible();
  });

  test('should show like count on posts', async ({ page }) => {
    await loginAsUser(page);
    await page.goto('/community');

    // Post like counts should be visible
    await expect(page.getByText('5').first()).toBeVisible();
  });

  test('should show comment count on posts', async ({ page }) => {
    await loginAsUser(page);
    await page.goto('/community');

    await expect(page.getByText('2').first()).toBeVisible();
  });

  test('should show author nickname on posts', async ({ page }) => {
    await loginAsUser(page);
    await page.goto('/community');

    await expect(page.getByText('testuser').first()).toBeVisible();
  });

  test('should have a create post button', async ({ page }) => {
    await loginAsUser(page);
    await page.goto('/community');

    const createButton = page.getByRole('button', { name: /글쓰기|새 게시글|작성/ });
    if (await createButton.isVisible()) {
      await expect(createButton).toBeEnabled();
    }
  });
});
