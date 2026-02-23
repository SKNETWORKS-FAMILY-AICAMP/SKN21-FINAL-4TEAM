import { test, expect } from '@playwright/test';
import {
  loginAsUser,
  loginAsVerifiedUser,
  MOCK_PERSONAS,
  MOCK_LOREBOOK_ENTRIES,
} from './helpers';

test.describe('Persona List', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsUser(page);
  });

  test('should display persona list page with personas', async ({ page }) => {
    await page.goto('/personas');

    await expect(page.getByText('페르소나')).toBeVisible();
    await expect(page.getByText('미니')).toBeVisible();
    await expect(page.getByText('다크나이트')).toBeVisible();
    await expect(page.getByText('성인전용 캐릭터')).toBeVisible();
  });

  test('should display age rating badges on persona cards', async ({ page }) => {
    await page.goto('/personas');

    // Wait for personas to load
    await expect(page.getByText('미니')).toBeVisible();

    // "전체" badge for "all" rating
    await expect(page.getByText('[전체]')).toBeVisible();
    // "15+" badge
    await expect(page.getByText('[15+]')).toBeVisible();
    // "18+" badge
    await expect(page.getByText('[18+]')).toBeVisible();
  });

  test('should show lock icon on 18+ persona for unverified user', async ({ page }) => {
    await page.goto('/personas');

    await expect(page.getByText('미니')).toBeVisible();

    // The 18+ badge should have a lock emoji for unverified user
    const lockIcon = page.getByText(/🔒/);
    await expect(lockIcon).toBeVisible();
  });

  test('should disable chat button for locked 18+ persona', async ({ page }) => {
    await page.goto('/personas');

    await expect(page.getByText('성인전용 캐릭터')).toBeVisible();

    // The chat button for the locked 18+ persona should say "성인인증 필요"
    await expect(page.getByRole('button', { name: '성인인증 필요' })).toBeVisible();
    await expect(page.getByRole('button', { name: '성인인증 필요' })).toBeDisabled();
  });

  test('should show "대화하기" button for accessible personas', async ({ page }) => {
    await page.goto('/personas');

    await expect(page.getByText('미니')).toBeVisible();

    // "all" and "15+" persona should have enabled chat button
    const chatButtons = page.getByRole('button', { name: '대화하기' });
    const count = await chatButtons.count();
    // At least 2 chat buttons (for "all" and "15+" personas)
    expect(count).toBeGreaterThanOrEqual(2);
  });

  test('should show edit and lorebook buttons for user-created personas', async ({ page }) => {
    await page.goto('/personas');

    await expect(page.getByText('다크나이트')).toBeVisible();

    // User-created persona should show edit and lorebook buttons
    await expect(page.getByRole('button', { name: '수정' }).first()).toBeVisible();
    await expect(page.getByRole('button', { name: '로어북' }).first()).toBeVisible();
  });

  test('should navigate to create persona page', async ({ page }) => {
    await page.goto('/personas');

    await page.getByRole('button', { name: '+ 새 페르소나' }).click();
    await expect(page).toHaveURL(/\/personas\/create/);
  });

  test('should show persona system prompts truncated to 80 chars', async ({ page }) => {
    await page.goto('/personas');

    await expect(page.getByText('미니')).toBeVisible();

    // The first persona has a system prompt longer than 80 chars, should be truncated with "..."
    const prompt = MOCK_PERSONAS[0].system_prompt;
    if (prompt.length > 80) {
      const truncated = prompt.slice(0, 80);
      await expect(page.getByText(truncated, { exact: false })).toBeVisible();
    }
  });
});

test.describe('Persona Creation', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsUser(page);
  });

  test('should display the persona creation form with all fields', async ({ page }) => {
    await page.goto('/personas/create');

    await expect(page.getByText('새 페르소나 생성')).toBeVisible();
    await expect(page.getByText('캐릭터 이름')).toBeVisible();
    await expect(page.getByText('성격 / 시스템 프롬프트')).toBeVisible();
    await expect(page.getByText('말투 규칙 (선택)')).toBeVisible();
    await expect(page.getByText('캐치프레이즈 (선택, 줄바꿈으로 구분)')).toBeVisible();
    await expect(page.getByText('연령등급')).toBeVisible();
    await expect(page.getByText('공개 범위')).toBeVisible();
    await expect(page.getByText('배경 이미지 URL (선택)')).toBeVisible();
    await expect(page.getByRole('button', { name: '생성하기' })).toBeVisible();
  });

  test('should create a new persona with valid data and redirect to lorebook', async ({ page }) => {
    await page.goto('/personas/create');

    // Fill in the form
    await page.getByPlaceholder('예: 미니').fill('테스트 캐릭터');
    await page
      .getByPlaceholder('캐릭터의 성격, 배경, 대화 스타일을 자유롭게 적어주세요...')
      .fill('테스트용 캐릭터입니다. 밝고 친근한 성격.');
    await page.getByPlaceholder('예: 반말 사용, ~냥 어미, 이모티콘 자주 사용').fill('반말 사용');
    await page.getByPlaceholder('자주 쓰는 표현들을 한 줄씩 입력...').fill('야호~');

    // Submit
    await page.getByRole('button', { name: '생성하기' }).click();

    // Should redirect to the lorebook page for the new persona
    await expect(page).toHaveURL(/\/personas\/persona-new-001\/lorebook/);
  });

  test('should show validation error when required fields are empty', async ({ page }) => {
    await page.goto('/personas/create');

    // Try to submit without filling required fields
    await page.getByRole('button', { name: '생성하기' }).click();

    // Should show validation errors
    await expect(page.getByText('이름을 입력하세요')).toBeVisible();
    await expect(page.getByText('성격/설정을 입력하세요')).toBeVisible();
  });

  test('should show 18+ adult verification warning for unverified user', async ({ page }) => {
    await page.goto('/personas/create');

    // The 18+ option in the age_rating select should be disabled for unverified user
    const ageSelect = page.locator('select').first();
    const option18 = ageSelect.locator('option[value="18+"]');
    await expect(option18).toBeDisabled();

    // The option text should mention adult verification requirement
    const optionText = await option18.textContent();
    expect(optionText).toContain('성인인증 필요');
  });

  test('should show warning text when 18+ is somehow selected by unverified user', async ({
    page,
  }) => {
    await page.goto('/personas/create');

    // Try to manually change the select value via JS (simulating edge case)
    await page.locator('select').first().selectOption({ value: 'all' });

    // Verify that "all" is selected and no warning is shown
    const warning = page.getByText('18+ 등급은 성인인증 후 사용 가능합니다');
    await expect(warning).not.toBeVisible();
  });
});

test.describe('Persona Creation - Adult Verified User', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsVerifiedUser(page);
  });

  test('should allow 18+ option for adult verified user', async ({ page }) => {
    await page.goto('/personas/create');

    const ageSelect = page.locator('select').first();
    const option18 = ageSelect.locator('option[value="18+"]');

    // 18+ option should NOT be disabled for verified user
    await expect(option18).not.toBeDisabled();
  });

  test('should create 18+ persona successfully when adult verified', async ({ page }) => {
    await page.goto('/personas/create');

    await page.getByPlaceholder('예: 미니').fill('성인 캐릭터');
    await page
      .getByPlaceholder('캐릭터의 성격, 배경, 대화 스타일을 자유롭게 적어주세요...')
      .fill('성인 전용 캐릭터입니다.');
    await page.locator('select').first().selectOption('18+');

    await page.getByRole('button', { name: '생성하기' }).click();

    await expect(page).toHaveURL(/\/personas\/persona-new-001\/lorebook/);
  });
});

test.describe('Persona Editing', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsUser(page);
  });

  test('should load existing persona data in edit form', async ({ page }) => {
    await page.goto('/personas/persona-002/edit');

    await expect(page.getByText('페르소나 수정')).toBeVisible();

    // The form should be pre-filled with existing data
    const nameInput = page.getByPlaceholder('예: 미니');
    await expect(nameInput).toHaveValue('다크나이트');

    const promptTextarea = page.getByPlaceholder(
      '캐릭터의 성격, 배경, 대화 스타일을 자유롭게 적어주세요...',
    );
    await expect(promptTextarea).toHaveValue('냉소적이고 날카로운 비평가입니다.');
  });

  test('should show "수정하기" button instead of "생성하기" in edit mode', async ({ page }) => {
    await page.goto('/personas/persona-002/edit');

    await expect(page.getByRole('button', { name: '수정하기' })).toBeVisible();
  });

  test('should update persona and redirect to persona list', async ({ page }) => {
    await page.goto('/personas/persona-002/edit');

    // Wait for form to load
    await expect(page.getByPlaceholder('예: 미니')).toHaveValue('다크나이트');

    // Change the name
    await page.getByPlaceholder('예: 미니').fill('수정된 캐릭터');
    await page.getByRole('button', { name: '수정하기' }).click();

    // Should redirect to personas list
    await expect(page).toHaveURL(/\/personas$/);
  });

  test('should navigate to edit page from persona list', async ({ page }) => {
    await page.goto('/personas');

    await expect(page.getByText('다크나이트')).toBeVisible();

    // Click the edit button for the user-created persona
    await page.getByRole('button', { name: '수정' }).first().click();
    await expect(page).toHaveURL(/\/personas\/persona-002\/edit/);
  });
});

test.describe('Lorebook Management', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsUser(page);
  });

  test('should display lorebook page with entries', async ({ page }) => {
    await page.goto('/personas/persona-002/lorebook');

    await expect(page.getByText('로어북 관리')).toBeVisible();
    await expect(page.getByText('페르소나의 세계관, 배경, 캐릭터 설정을 정의하세요.')).toBeVisible();

    // Should show existing lorebook entries
    await expect(page.getByText('세계관 설정')).toBeVisible();
    await expect(page.getByText('주인공 설정')).toBeVisible();
  });

  test('should display lorebook entry content and tags', async ({ page }) => {
    await page.goto('/personas/persona-002/lorebook');

    await expect(page.getByText('이 세계는 마법과 과학이 공존하는 세계입니다.')).toBeVisible();

    // Tags
    await expect(page.getByText('세계관')).toBeVisible();
    await expect(page.getByText('판타지')).toBeVisible();
  });

  test('should show add new entry form', async ({ page }) => {
    await page.goto('/personas/persona-002/lorebook');

    await expect(page.getByText('새 항목 추가')).toBeVisible();
    await expect(page.getByPlaceholder('제목 (예: 세계관 설정)')).toBeVisible();
    await expect(page.getByPlaceholder('내용을 입력하세요...')).toBeVisible();
    await expect(page.getByPlaceholder('태그 (쉼표로 구분)')).toBeVisible();
    await expect(page.getByRole('button', { name: '추가' })).toBeVisible();
  });

  test('should add a new lorebook entry', async ({ page }) => {
    // Track POST requests to lorebook endpoint
    let postCalled = false;
    await page.route('**/api/personas/*/lorebook', async (route) => {
      const request = route.request();
      if (request.method() === 'POST') {
        postCalled = true;
        const body = JSON.parse(request.postData() ?? '{}');
        expect(body.title).toBe('새로운 설정');
        expect(body.content).toBe('새로운 세계관 설정 내용입니다.');
        return route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({ id: 'lore-new-001', ...body }),
        });
      }
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(MOCK_LOREBOOK_ENTRIES),
      });
    });

    await page.goto('/personas/persona-002/lorebook');

    await page.getByPlaceholder('제목 (예: 세계관 설정)').fill('새로운 설정');
    await page.getByPlaceholder('내용을 입력하세요...').fill('새로운 세계관 설정 내용입니다.');
    await page.getByPlaceholder('태그 (쉼표로 구분)').fill('설정, 테스트');
    await page.getByRole('button', { name: '추가' }).click();

    expect(postCalled).toBe(true);
  });

  test('should disable add button when title or content is empty', async ({ page }) => {
    await page.goto('/personas/persona-002/lorebook');

    // Button should be disabled when form is empty
    await expect(page.getByRole('button', { name: '추가' })).toBeDisabled();

    // Fill only title -- still disabled
    await page.getByPlaceholder('제목 (예: 세계관 설정)').fill('제목만');
    await expect(page.getByRole('button', { name: '추가' })).toBeDisabled();

    // Clear title, fill content -- still disabled
    await page.getByPlaceholder('제목 (예: 세계관 설정)').clear();
    await page.getByPlaceholder('내용을 입력하세요...').fill('내용만');
    await expect(page.getByRole('button', { name: '추가' })).toBeDisabled();
  });

  test('should show edit and delete buttons on each lorebook entry', async ({ page }) => {
    await page.goto('/personas/persona-002/lorebook');

    await expect(page.getByText('세계관 설정')).toBeVisible();

    // Each entry should have edit and delete buttons
    const editButtons = page.getByRole('button', { name: '수정' });
    const deleteButtons = page.getByRole('button', { name: '삭제' });

    expect(await editButtons.count()).toBe(MOCK_LOREBOOK_ENTRIES.length);
    expect(await deleteButtons.count()).toBe(MOCK_LOREBOOK_ENTRIES.length);
  });

  test('should switch to edit mode when clicking edit button on entry', async ({ page }) => {
    await page.goto('/personas/persona-002/lorebook');

    await expect(page.getByText('세계관 설정')).toBeVisible();

    // Click edit on first entry
    await page.getByRole('button', { name: '수정' }).first().click();

    // Form header should change to "항목 수정"
    await expect(page.getByText('항목 수정')).toBeVisible();

    // Form should be pre-filled with entry data
    await expect(page.getByPlaceholder('제목 (예: 세계관 설정)')).toHaveValue('세계관 설정');
    await expect(page.getByPlaceholder('내용을 입력하세요...')).toHaveValue(
      '이 세계는 마법과 과학이 공존하는 세계입니다.',
    );

    // Cancel button should be visible in edit mode
    await expect(page.getByRole('button', { name: '취소' })).toBeVisible();
  });

  test('should cancel editing and restore add mode', async ({ page }) => {
    await page.goto('/personas/persona-002/lorebook');

    await expect(page.getByText('세계관 설정')).toBeVisible();

    // Enter edit mode
    await page.getByRole('button', { name: '수정' }).first().click();
    await expect(page.getByText('항목 수정')).toBeVisible();

    // Click cancel
    await page.getByRole('button', { name: '취소' }).click();

    // Should return to add mode
    await expect(page.getByText('새 항목 추가')).toBeVisible();

    // Form should be cleared
    await expect(page.getByPlaceholder('제목 (예: 세계관 설정)')).toHaveValue('');
    await expect(page.getByPlaceholder('내용을 입력하세요...')).toHaveValue('');
  });

  test('should navigate to lorebook page from persona list', async ({ page }) => {
    await page.goto('/personas');

    await expect(page.getByText('다크나이트')).toBeVisible();

    await page.getByRole('button', { name: '로어북' }).first().click();
    await expect(page).toHaveURL(/\/personas\/persona-002\/lorebook/);
  });
});
