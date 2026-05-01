# Microsoft Graph API アプリ登録手順書

**対象**: IT管理者様  
**依頼者**: AutoTicketプロジェクト担当者  
**目的**: 自動タスク起票システム（AutoTicket）のM365連携に必要なAzure ADアプリ登録

---

## 必要な権限スコープ

| フェーズ | スコープ | 用途 | 種別 |
|---------|---------|------|------|
| Phase 1 | `Mail.Read` | Outlookメール読み取り | Application |
| Phase 1 | `OnlineMeetings.Read.All` | Teams会議文字起こし取得 | Application |
| Phase 1 | `Tasks.ReadWrite.All` | Microsoft Plannerへのタスク起票 | Application |
| Phase 1 | `User.Read.All` | ユーザー情報・担当者照合 | Application |
| Phase 2（将来） | `ChannelMessage.Read.All` | Teamsチャット読み取り | Application |
| Phase 2（将来） | `Notes.Read.All` | OneNote取得 | Application |

※ Phase 1 の4スコープのみ最初に申請をお願いします。

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

## セキュリティ注意事項
- クライアントシークレットはメール送付禁止。1Password等のセキュアな方法で共有をお願いします
- シークレットの有効期限が近づいたら更新が必要です（有効期限1ヶ月前を目安に担当者へ通知）
- アプリの権限は上記スコープ以上に付与しないようお願いします（最小権限原則）

---

## 完了後の連絡先
設定完了後、以下の情報をプロジェクト担当者（shinsuke-imanaka@vorn.co.jp）にご連絡ください。
