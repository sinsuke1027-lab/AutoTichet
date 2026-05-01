---
description: 機密度分類スキル - テキストの機密度を判定してPattern A/Bを振り分ける
---

# 機密度分類スキル

`src/services/classifier.py` の実装・修正時に使用する。

## 分類基準

### Pattern B（ローカルLLM処理）が必要な条件
以下のキーワード・パターンが含まれる場合は必ずPattern Bへ：

| カテゴリ | キーワード例 |
|---------|------------|
| 人事関連 | 給与、報酬、評価、採用、解雇、懲戒、昇進、降格 |
| 個人情報 | マイナンバー、住所、生年月日、健康診断 |
| 顧客情報 | 顧客名、取引金額、契約内容、見積、受注 |
| 財務情報 | 売上、利益、コスト、予算、決算 |
| 音声ファイル | .wav, .mp3, .m4a 等の音声ファイル |

### Pattern A（M365完結）で処理可能
- 一般業務連絡・スケジュール調整
- プロジェクト進捗報告（金額・個人情報なし）
- 社内イベント案内
- 会議室予約・調整

## 実装上の注意
- 分類は保守的に行う（迷ったらPattern Bを選択）
- 分類結果はLangfuseにログ記録する（`sensitivity_label` フィールド）
- Phase 1ではPattern Bが検出された場合はスキップしてログのみ（Pattern Bはまだ未実装）

## 戻り値
```python
class SensitivityResult(BaseModel):
    label: Literal["pattern_a", "pattern_b"]
    reason: str
    detected_keywords: list[str]
```
