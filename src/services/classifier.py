from src.models.task import SensitivityResult

_CONFIDENTIAL_KEYWORDS: list[str] = [
    # 人事
    "給与",
    "報酬",
    "賞与",
    "ボーナス",
    "評価",
    "採用",
    "解雇",
    "懲戒",
    "昇進",
    "降格",
    "人事",
    "退職",
    "休職",
    # 個人情報
    "マイナンバー",
    "住所",
    "生年月日",
    "健康診断",
    "病歴",
    # 顧客・財務
    "顧客名",
    "取引金額",
    "契約金額",
    "契約",
    "見積",
    "受注",
    "売上",
    "利益",
    "決算",
    "予算",
    "コスト",
]


def classify_sensitivity(text: str) -> SensitivityResult:
    if not text:
        return SensitivityResult(
            label="pattern_a",
            reason="空テキスト",
            detected_keywords=[],
        )

    found = [kw for kw in _CONFIDENTIAL_KEYWORDS if kw in text]
    if found:
        return SensitivityResult(
            label="pattern_b",
            reason=f"機密キーワードを検出: {', '.join(found)}",
            detected_keywords=found,
        )
    return SensitivityResult(
        label="pattern_a",
        reason="機密キーワードなし",
        detected_keywords=[],
    )
