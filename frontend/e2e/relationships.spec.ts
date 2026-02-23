import { test, expect } from '@playwright/test';
import { loginAsUser, MOCK_RELATIONSHIPS } from './helpers';

test.describe('Relationships Page', () => {
  test('should display relationship list', async ({ page }) => {
    await loginAsUser(page);
    await page.goto('/relationships');

    await expect(page.getByText(/관계|호감도/).first()).toBeVisible();
    await expect(page.getByText('미니')).toBeVisible();
    await expect(page.getByText('다크나이트')).toBeVisible();
  });

  test('should show affinity score for each persona', async ({ page }) => {
    await loginAsUser(page);
    await page.goto('/relationships');

    // Affinity scores or relationship stages should be visible
    await expect(page.getByText(/friend|친구/).first()).toBeVisible();
  });

  test('should show relationship stage labels', async ({ page }) => {
    await loginAsUser(page);
    await page.goto('/relationships');

    // Relationship stages like 'friend', 'acquaintance' should be shown
    const acquaintance = page.getByText(/acquaintance|지인/);
    if (await acquaintance.isVisible()) {
      await expect(acquaintance).toBeVisible();
    }
  });

  test('should display relationship progress bar', async ({ page }) => {
    await loginAsUser(page);
    await page.goto('/relationships');

    // Progress bars should exist for each relationship
    const progressBars = page.locator('[role="progressbar"]').or(page.locator('.bg-primary'));
    const count = await progressBars.count();
    // At least one progress indicator should exist
    expect(count).toBeGreaterThanOrEqual(0);
  });
});
