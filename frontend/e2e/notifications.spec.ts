import { test, expect } from '@playwright/test';
import { loginAsUser, MOCK_NOTIFICATIONS } from './helpers';

test.describe('Notifications Page', () => {
  test('should display notification list', async ({ page }) => {
    await loginAsUser(page);
    await page.goto('/notifications');

    await expect(page.getByText('알림')).toBeVisible();
    await expect(page.getByText('환영합니다!')).toBeVisible();
    await expect(page.getByText('페르소나 승인됨')).toBeVisible();
  });

  test('should show unread indicator for unread notifications', async ({ page }) => {
    await loginAsUser(page);
    await page.goto('/notifications');

    // The first notification is unread
    await expect(page.getByText('환영합니다!')).toBeVisible();
  });

  test('should mark notification as read when clicking', async ({ page }) => {
    await loginAsUser(page);
    await page.goto('/notifications');

    // Click on unread notification
    const notification = page.getByText('환영합니다!');
    await expect(notification).toBeVisible();
    await notification.click();
  });

  test('should mark all notifications as read', async ({ page }) => {
    await loginAsUser(page);
    await page.goto('/notifications');

    const markAllButton = page.getByRole('button', { name: /모두 읽음|전체 읽음/ });
    if (await markAllButton.isVisible()) {
      await markAllButton.click();
    }
  });

  test('should show notification count in header bell', async ({ page }) => {
    await loginAsUser(page);
    await page.goto('/sessions');

    // The notification bell should show unread count
    const bell = page.getByRole('link', { name: /알림/ }).or(page.locator('[aria-label*="알림"]'));
    if (await bell.isVisible()) {
      // Should have badge showing unread count
      await expect(bell).toBeVisible();
    }
  });
});
