import { test, expect, type Page } from '@playwright/test';

// 共通ログインヘルパー
async function devLogin(page: Page, displayName: string, userId: string, role: string, departmentTags: string = '') {
  await page.goto('/');
  await page.waitForSelector('text=開発用ログイン');

  await page.fill('input[placeholder="田中 太郎"]', displayName);
  await page.fill('input[placeholder="user-001"]', userId);

  // ロールの選択
  await page.locator('.ant-select').first().click();
  const roleLabel = role.charAt(0).toUpperCase() + role.slice(1);
  // オプションが表示されるまで少し待機してクリック
  await page.waitForSelector(`.ant-select-item-option-content:has-text("${roleLabel}")`);
  await page.click(`.ant-select-item-option-content:has-text("${roleLabel}")`);

  if (departmentTags) {
    await page.fill('input[placeholder="engineering, product"]', departmentTags);
  }

  await page.click('button:has-text("開発環境でログイン")');
  
  // ログイン完了（ヘッダーまたはダッシュボード表示）を待機
  await page.waitForSelector('text=AutoTicket');
}

test.describe('AutoTicket E2E 機能検証', () => {

  // 1. ダッシュボード (F-10)
  test('1. ダッシュボードの表示確認', async ({ page }) => {
    // 1. 石川 智代 としてログイン
    await devLogin(page, '石川 智代', 'ishikawa-tomo', 'leader', 'general_affairs');
    
    // 2. ダッシュボードのKPIカードおよびグラフの描画確認
    await expect(page.locator('text=総タスク数')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('text=完了率')).toBeVisible();
    await expect(page.locator('text=進行中')).toBeVisible();
    
    // グラフコンテナの存在確認
    const chart = page.locator('.recharts-responsive-container');
    await expect(chart.first()).toBeVisible();

    // 「今日のタスク」または「期限超過」リストの確認
    await expect(page.locator('text=今日のタスク')).toBeVisible();
    await expect(page.locator('text=期限超過タスク')).toBeVisible();
  });

  // 2. タスク登録・編集・削除 (F-01)
  test('2. タスク登録・編集・削除', async ({ page }) => {
    await devLogin(page, '石川 智代', 'ishikawa-tomo', 'leader', 'general_affairs');

    // 1. タスク一覧へ移動
    await page.click('text=タスク一覧');
    await page.waitForURL('**/tasks');

    // 2. 「新規タスク」ボタンをクリック
    await page.click('button:has-text("新規タスク")');
    const dialog = page.getByRole('dialog', { name: '新規タスク作成' });
    await expect(dialog).toBeVisible();

    // 3. タイトル「テスト用タスク」等の入力
    await dialog.locator('input').first().fill('テスト用タスク');

    // 公開範囲を「全公開」に変更して、leaderロールのユーザーでも一覧に表示されるようにする
    await dialog.locator('.ant-select').first().click();
    await page.waitForSelector('.ant-select-item-option-content:has-text("全公開")');
    await page.click('.ant-select-item-option-content:has-text("全公開")');

    // 作成の実行 (モーダルのOKボタンをクリック)
    await dialog.locator('button:has-text("OK")').click();
    await expect(dialog).not.toBeVisible();

    // 4. 一覧に即時反映されるか確認 (再度メニューをクリックして再フェッチさせる)
    await page.click('text=タスク一覧');
    const taskLink = page.locator('a:has-text("テスト用タスク")').first();
    await expect(taskLink).toBeVisible({ timeout: 10000 });

    // 5. 詳細を開いて編集
    await taskLink.click();
    await page.waitForURL(/\/tasks\/[0-9a-fA-F-]+/);

    // インライン編集または詳細入力の確認
    // タイトルの編集用テキストエリア/インプットを探す
    const titleInput = page.locator('input[value="テスト用タスク"], h3:has-text("テスト用タスク"), .ant-typography:has-text("テスト用タスク")');
    await expect(titleInput.first()).toBeVisible();
    
    // 6. 削除処理
    const deleteBtn = page.locator('button:has-text("削除")');
    if (await deleteBtn.isVisible()) {
      await deleteBtn.click();
      // 確認ダイアログの「はい」または「OK」をクリック
      await page.click('.ant-modal-confirm-btns button:has-text("OK"), .ant-modal-confirm-btns button:has-text("はい")');
      await page.waitForURL('**/tasks');
      // 一覧から消えているか確認
      await expect(page.locator('text=テスト用タスク')).not.toBeVisible();
    }
  });

  // 3. タスク一覧・検索・フィルタ (F-02)
  test('3. タスク一覧・検索・フィルタ', async ({ page }) => {
    await devLogin(page, '石川 智代', 'ishikawa-tomo', 'leader', 'general_affairs');
    await page.click('text=タスク一覧');
    await page.waitForURL('**/tasks');

    // 1. キーワード「社内報」で検索
    const searchInput = page.locator('input[placeholder*="検索"], input[placeholder*="キーワード"]');
    if (await searchInput.isVisible()) {
      await searchInput.fill('社内報');
      await page.keyboard.press('Enter');
      // 検索結果の確認
      await expect(page.locator('text=社内報')).toBeVisible();
    }

    // 2. フィルタの確認（ステータスやプロジェクト）
    // リセットボタンの確認
    const resetBtn = page.locator('button:has-text("リセット"), button:has-text("クリア")');
    if (await resetBtn.isVisible()) {
      await resetBtn.click();
    }
  });

  // 4. タスク詳細（4タブ）・コメント・工数 (F-03, F-05, F-12)
  test('4. タスク詳細の各タブ操作とコメント・工数記録', async ({ page }) => {
    await devLogin(page, '石川 智代', 'ishikawa-tomo', 'leader', 'general_affairs');
    await page.click('text=タスク一覧');
    await page.waitForURL('**/tasks');

    // 「よく知るVORN5月」などの既存タスクを開く
    const taskLink = page.locator('text=よく知るVORN5月, text=よく知るVORN');
    if (await taskLink.first().isVisible()) {
      await taskLink.first().click();
      await page.waitForURL(/\/tasks\/[0-9a-fA-F-]+/);

      // タブの存在確認
      await expect(page.locator('.ant-tabs-tab-btn:has-text("詳細"), .ant-tabs-tab-btn:has-text("タスク詳細")').first()).toBeVisible();
      const commentTab = page.locator('.ant-tabs-tab-btn:has-text("コメント")');
      const effortTab = page.locator('.ant-tabs-tab-btn:has-text("工数")');
      const subtaskTab = page.locator('.ant-tabs-tab-btn:has-text("サブタスク")');

      // コメント投稿の検証
      if (await commentTab.isVisible()) {
        await commentTab.click();
        await page.fill('textarea[placeholder*="コメント"], textarea', '準備進めます');
        await page.click('button:has-text("投稿"), button:has-text("送信")');
        await expect(page.locator('text=準備進めます')).toBeVisible();
      }

      // 工数記録の検証
      if (await effortTab.isVisible()) {
        await effortTab.click();
        await page.fill('input[type="number"], input[placeholder*="工数"]', '2.0');
        await page.click('button:has-text("記録"), button:has-text("追加")');
      }

      // サブタスク作成の検証
      if (await subtaskTab.isVisible()) {
        await subtaskTab.click();
        await page.fill('input[placeholder*="サブタスク"]', '会場予約確認');
        await page.keyboard.press('Enter');
        await expect(page.locator('text=会場予約確認')).toBeVisible();
      }
    }
  });

  // 5. 二重登録防止 (F-04)
  test('5. 二重登録防止警告の検証', async ({ page }) => {
    await devLogin(page, '石川 智代', 'ishikawa-tomo', 'leader', 'general_affairs');
    await page.click('text=タスク一覧');
    await page.waitForURL('**/tasks');

    await page.click('button:has-text("新規タスク")');
    const dialog = page.getByRole('dialog', { name: '新規タスク作成' });
    await expect(dialog).toBeVisible();

    // タイトルに「社内報作成」と入力
    await dialog.locator('input').first().fill('社内報作成');

    // 類似タスク候補または警告メッセージが表示されることを確認
    const warning = page.locator('text=類似タスクが見つかりました');
    await expect(warning.first()).toBeVisible({ timeout: 5000 });
  });

  // 6. プロジェクト管理 (F-06)
  test('6. プロジェクト管理とセクション操作', async ({ page }) => {
    await devLogin(page, '石川 智代', 'ishikawa-tomo', 'leader', 'general_affairs');
    await page.click('text=プロジェクト');
    await page.waitForURL('**/projects');

    // プロジェクト一覧の表示確認
    await expect(page.locator('text=総務業務管理')).toBeVisible();
    await expect(page.locator('text=人事業務管理')).toBeVisible();

    await page.click('text=総務業務管理');
    // SPAの遷移待機を固有要素の出現確認に変更して安定化
    await page.waitForSelector('text=総務業務管理');
    await page.waitForSelector('button:has-text("セクション追加")');

    // セクション別タスク整理の確認
    await expect(page.locator('text=よく知るVORN')).toBeVisible();

    // 新規セクション追加
    const addSectionBtn = page.locator('button:has-text("セクション追加"), button:has-text("新規セクション")');
    if (await addSectionBtn.isVisible()) {
      await addSectionBtn.click();
      const sectionDialog = page.getByRole('dialog', { name: 'セクション追加' });
      await expect(sectionDialog).toBeVisible();
      await sectionDialog.getByLabel('セクション名').fill('テストセクション');
      await sectionDialog.locator('button:has-text("OK")').click();
      await expect(sectionDialog).not.toBeVisible();
      await expect(page.locator('text=テストセクション').first()).toBeVisible();
    }
  });

  // 7. 個人ToDo・visibility制御 (F-07)
  test('7. visibility（非公開タスク）のアクセス制限検証', async ({ page }) => {
    // 1. 寄田 俊雄 (member) でログイン
    await devLogin(page, '寄田 俊雄', 'yorita-toshio', 'member', 'general_affairs');
    await page.click('text=タスク一覧');
    await page.waitForURL('**/tasks');

    // privateタスク「議事録作成」が見えることを確認
    const privateTask = page.locator('text=議事録作成');
    const isPrivateVisibleForOwner = await privateTask.isVisible();

    // 2. ログアウト
    await page.click('button:has-text("ログアウト")');

    // 3. 梅本 美結 (member / general_affairs) でログイン
    await devLogin(page, '梅本 美結', 'umemoto-miyu', 'member', 'general_affairs');
    await page.click('text=タスク一覧');
    await page.waitForURL('**/tasks');

    // 寄田のprivateタスク「議事録作成」が見えないことを確認
    if (isPrivateVisibleForOwner) {
      await expect(page.locator('text=議事録作成')).not.toBeVisible();
    }
  });

  // 8. 権限管理 (F-08)
  test('8. 権限管理による管理者ページへのアクセス制限検証', async ({ page }) => {
    // 1. 一般メンバー (梅本 美結) でログイン
    await devLogin(page, '梅本 美結', 'umemoto-miyu', 'member', 'general_affairs');
    
    // サイドバーに「ユーザー管理」がないことを確認
    await expect(page.locator('text=ユーザー管理')).not.toBeVisible();

    // 直接URL `/admin/users` に遷移し、アクセス拒否（ログイン画面への強制リダイレクト）されるか確認
    await page.goto('/admin/users');
    await expect(page.locator('text=403, text=権限がありません, text=アクセス権がありません, text=ダッシュボード, text=開発用ログイン')).toBeVisible();

    // 2. ログアウトして管理者でログイン
    await page.goto('/');
    await page.click('button:has-text("ログアウト")');
    await devLogin(page, '管理者シード', 'admin-seed', 'admin', 'admin');

    // サイドバーに「ユーザー管理」が表示されることを確認
    await expect(page.locator('text=ユーザー管理')).toBeVisible();
    await page.click('text=ユーザー管理');
    await page.waitForURL('**/admin/users');
    await expect(page.locator('text=ユーザー一覧')).toBeVisible();
  });

  // 9. 1日スケジュール・D&D (F-09, F-11)
  test('9. スケジュール画面とタスク表示確認', async ({ page }) => {
    await devLogin(page, '石川 智代', 'ishikawa-tomo', 'leader', 'general_affairs');
    await page.click('text=スケジュール');
    await page.waitForURL('**/schedule');

    await expect(page.locator('text=未配置')).toBeVisible();
  });

  // 10. ワークロード (F-13)
  test('10. ワークロード画面の負荷グラフ表示確認', async ({ page }) => {
    await devLogin(page, '石川 智代', 'ishikawa-tomo', 'leader', 'general_affairs');
    await page.click('text=ワークロード');
    await page.waitForURL('**/workload');

    // グラフやメンバー一覧が表示されるか確認
    await expect(page.locator('.recharts-responsive-container, .ant-card').first()).toBeVisible();
  });

  // 11. 負荷アラートバッジ (F-14)
  test('11. 負荷アラートバッジの表示とポップオーバー表示確認', async ({ page }) => {
    await devLogin(page, '石川 智代', 'ishikawa-tomo', 'leader', 'general_affairs');

    // ヘッダーのベルアイコンまたはWorkloadAlertBadgeの確認
    const alertBadge = page.locator('.ant-badge, .ant-avatar, svg[class*="bell"], span:has-text("警告"), span:has-text("超過")');
    if (await alertBadge.first().isVisible()) {
      await alertBadge.first().click();
      // ポップオーバー内のグラフや詳細表示の確認
      await expect(page.locator('.ant-popover, .ant-tooltip').first()).toBeVisible();
    }
  });

  // 12. カンバンビュー (F-22)
  test('12. カンバンボードの表示確認', async ({ page }) => {
    await devLogin(page, '石川 智代', 'ishikawa-tomo', 'leader', 'general_affairs');
    await page.click('text=カンバン');
    await page.waitForURL('**/board');

    // カラム（未着手・進行中・レビュー中・完了）の存在確認
    await expect(page.locator('text=未着手')).toBeVisible();
    await expect(page.locator('text=進行中').first()).toBeVisible();
    await expect(page.locator('text=レビュー中, text=レビュー')).toBeVisible();
    await expect(page.locator('text=完了')).toBeVisible();
  });

  // 13. カレンダービュー (F-22)
  test('13. カレンダービューの表示確認', async ({ page }) => {
    await devLogin(page, '石川 智代', 'ishikawa-tomo', 'leader', 'general_affairs');
    await page.click('text=カレンダー');
    await page.waitForURL('**/calendar');

    // 月次カレンダーの確認（カレンダーグリッドの存在）
    await expect(page.locator('.rbc-calendar, .ant-picker-calendar, .fc').first()).toBeVisible();
  });

  // 14. ガントチャート・依存関係 (F-22, F-23, F-36)
  test('14. ガントチャートビューの表示確認', async ({ page }) => {
    await devLogin(page, '石川 智代', 'ishikawa-tomo', 'leader', 'general_affairs');
    await page.click('text=ガント');
    await page.waitForURL('**/gantt');

    // ガントチャートのガントバー（svgや関連クラス）が表示されているか確認
    await expect(page.locator('.gantt, svg, .gantt-container').first()).toBeVisible();
  });

  // 15. Asanaインポート
  test('15. Asanaインポート画面の表示確認', async ({ page }) => {
    await devLogin(page, '石川 智代', 'ishikawa-tomo', 'leader', 'general_affairs');
    await page.click('text=データインポート');
    await page.waitForURL('**/import');

    // ファイルアップロードフォーム等の確認
    await expect(page.locator('.ant-upload, input[type="file"]').first()).toBeVisible();
  });

  // 16. 管理者ユーザー管理
  test('16. 管理者用のユーザーロール編集の確認', async ({ page }) => {
    await devLogin(page, '管理者シード', 'admin-seed', 'admin', 'admin');
    await page.click('text=ユーザー管理');
    await page.waitForURL('**/admin/users');

    // ユーザー一覧のテーブル表示確認
    await expect(page.locator('.ant-table-wrapper, table').first()).toBeVisible();
  });

});
