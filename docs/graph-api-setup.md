# Microsoft Graph API アプリ登録手順書

**対象**: IT管理者様  
**依頼者**: AutoTicketプロジェクト担当者  
**目的**: 自動タスク起票システム（AutoTicket）のM365連携に必要なAzure ADアプリ登録と、特定ユーザーへのアクセス制限設定

---

## 必要な権限スコープ

| フェーズ | スコープ | 用途 | 種別 |
|---------|---------|------|------|
| Phase 1 | `Mail.Read` | Outlookメール読み取り | Application |
| Phase 1 | `OnlineMeetings.Read.All` | Teams会議文字起こし取得 | Application |
| Phase 1 | `Tasks.ReadWrite.All` | Planner起票 + To Doプライベートタスク作成 | Application |
| Phase 1 | `User.Read.All` | ユーザー情報・担当者照合 | Application |
| Phase 1 | `Group.Read.All` | 部署（M365 Group）一覧取得 | Application |
| Phase 2（将来） | `ChannelMessage.Read.All` | Teamsチャット読み取り | Application |
| Phase 2（将来） | `Notes.Read.All` | OneNote取得 | Application |

> **重要**: スコープ付与後、必ず後述の「アクセス制限設定」も併せて実施してください。  
> Exchange（メール）のアクセスは段階的に制限します（最初は担当者1名、検証後に最大5名まで拡大）。

---

## 登録手順

### 手順1: アプリ登録
1. [Azure Active Directory 管理センター](https://aad.portal.azure.com) にアクセス
2. **Azure Active Directory** > **アプリの登録** > **新規登録**
3. 以下を入力：
   - **名前**: `AutoTicket-API`
   - **サポートされるアカウントの種類**: `この組織のディレクトリのみ（シングルテナント）`
   - **リダイレクトURI**: 設定不要（サーバー間通信のため）
4. **登録** をクリック

### 手順2: APIアクセス許可の追加
1. 登録したアプリの左メニュー > **APIのアクセス許可**
2. **アクセス許可の追加** > **Microsoft Graph** > **アプリケーションの許可**
3. 以下を検索して追加：
   - `Mail.Read`
   - `OnlineMeetings.Read.All`
   - `Tasks.ReadWrite.All`
   - `User.Read.All`
4. **「（テナント名）に管理者の同意を与えます」ボタンをクリック**（必須）

### 手順3: クライアントシークレット作成
1. 左メニュー > **証明書とシークレット** > **新しいクライアントシークレット**
2. 以下を設定：
   - **説明**: `AutoTicket Production`
   - **有効期限**: `24ヶ月`（推奨）
3. **追加** をクリック
4. 表示された **値** を必ずコピー（**この画面を閉じると二度と確認できません**）

### 手順4: 担当者への情報共有
以下3点をAutoTicketプロジェクト担当者にセキュアな方法で共有してください：

| 情報 | 確認場所 |
|------|---------|
| **テナントID** | 概要ページ > ディレクトリ（テナント）ID |
| **クライアントID** | 概要ページ > アプリケーション（クライアント）ID |
| **クライアントシークレット** | 手順3でコピーした値 |

---

## アクセス制限設定（段階的展開：1名 → 最大5名）

`Mail.Read` スコープはテナント全ユーザーのメールへのアクセスを許可するため、  
**Exchange Application Access Policy** を使用して特定ユーザーのみに制限します。  
**まず担当者1名のみで動作確認を行い、問題がなければ順次5名まで拡大します。**

### 前提条件
- Exchange Online PowerShell モジュールがインストールされていること
- Exchange 管理者権限を持つアカウントで実行すること

### 手順A: 対象ユーザーのセキュリティグループ作成

1. [Microsoft 365 管理センター](https://admin.microsoft.com) にアクセス
2. **チームとグループ** > **アクティブなチームとグループ** > **メールが有効なセキュリティグループ** > **グループを追加**
3. 以下を設定：
   - **グループ名**: `autoticket-allowed-users`
   - **グループメールアドレス**: `autoticket-allowed-users@（ドメイン）`
4. **最初は担当者1名（自身）のみ**をメンバーに追加する（検証完了後、順次追加・最大5名）

### 手順B: Application Access Policy の適用

Exchange Online PowerShell で以下を実行：

```powershell
# Exchange Online に接続
Connect-ExchangeOnline -UserPrincipalName admin@your-domain.com

# アクセスポリシーを作成（対象グループ以外のメールボックスへのアクセスを拒否）
New-ApplicationAccessPolicy `
  -AppId "（クライアントID）" `
  -PolicyScopeGroupId "autoticket-allowed-users@（ドメイン）" `
  -AccessRight RestrictAccess `
  -Description "AutoTicket は指定グループのメールボックスのみアクセス可"

# ポリシーの動作確認（対象ユーザーは Granted、対象外は Denied と表示されるはず）
Test-ApplicationAccessPolicy `
  -AppId "（クライアントID）" `
  -Identity "対象ユーザーのUPN@your-domain.com"
```

### 手順C: 対象ユーザーのIDをプロジェクト担当者に共有

以下のコマンドで対象ユーザーの Azure AD オブジェクトID（または UPN）を取得し、担当者に共有してください（最初は担当者自身の1名分）：

```powershell
# Azure AD PowerShell または Graph Explorer で確認
Get-MgUser -Filter "userPrincipalName eq '対象ユーザーのUPN@your-domain.com'" | Select-Object Id, DisplayName, UserPrincipalName
```

担当者は受け取ったIDを `.env` の `ALLOWED_USER_IDS` にカンマ区切りで設定します：

**Phase 1（1名検証）：**
```env
# 担当者自身のAzure ADオブジェクトIDまたはUPNのみ設定
ALLOWED_USER_IDS=your-own-user-guid
```

**Phase 2（最大5名に拡大）：自身の動作確認後、メンバーを追加**
```env
# カンマ区切りで追加メンバーのIDを追記
ALLOWED_USER_IDS=your-own-user-guid,user-guid-2,user-guid-3
```

> **注意**: `ALLOWED_USER_IDS` が設定されている場合、ツールは指定ユーザーのメールのみを処理します。  
> 空の場合はテナント全ユーザーを対象とするため、必ず設定してください。

---

## 段階的な展開手順

| フェーズ | 対象 | 作業内容 |
|---------|------|---------|
| **Step 1（初期検証）** | 担当者1名のみ | グループに自身のみ追加 → `.env` に自身のIDのみ設定 → 動作確認 |
| **Step 2（拡大）** | 最大5名まで | IT管理者にメンバー追加を依頼 → `.env` に追加メンバーのIDを追記 |

### Step 1 → Step 2 の拡大手順（IT管理者向け）

Step 2 への拡大時は、`autoticket-allowed-users` グループに追加メンバーを加えるだけです：

1. [Microsoft 365 管理センター](https://admin.microsoft.com) > **チームとグループ** > `autoticket-allowed-users` を選択
2. **メンバー** タブ > **メンバーを追加**
3. 追加するユーザーを選択して保存

Application Access Policy の再作成は不要です（グループへの追加のみで有効になります）。

---

## Phase 2 以降の追加申請について

Teams チャット（`ChannelMessage.Read.All`）および OneNote（`Notes.Read.All`）を追加する際は、  
**別途申請が必要**です。これらのスコープには Exchange のような Application Access Policy がないため、  
`ALLOWED_USER_IDS` によるコード側フィルタリングで対応します。

---

## セキュリティ注意事項
- クライアントシークレットはメール送付禁止。1Password等のセキュアな方法で共有をお願いします
- シークレットの有効期限が近づいたら更新が必要です（有効期限1ヶ月前を目安に担当者へ通知）
- アプリの権限は上記スコープ以上に付与しないようお願いします（最小権限原則）
- Application Access Policy が正しく適用されているか、定期的に `Test-ApplicationAccessPolicy` で確認することを推奨します

---

## 完了後の連絡先
設定完了後、以下の情報をプロジェクト担当者（shinsuke-imanaka@vorn.co.jp）にご連絡ください。
