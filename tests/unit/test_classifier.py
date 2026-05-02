from src.services.classifier import classify_sensitivity


def test_general_text_is_pattern_a() -> None:
    result = classify_sensitivity("来週の会議の議題について確認します")
    assert result.label == "pattern_a"
    assert result.detected_keywords == []


def test_salary_text_is_pattern_b() -> None:
    result = classify_sensitivity("今月の給与について田中さんに連絡してください")
    assert result.label == "pattern_b"
    assert "給与" in result.detected_keywords


def test_customer_info_is_pattern_b() -> None:
    result = classify_sensitivity("A社との契約金額を山田さんに共有してください")
    assert result.label == "pattern_b"
    assert "契約" in result.detected_keywords


def test_personal_info_is_pattern_b() -> None:
    result = classify_sensitivity("山田さんのマイナンバーを確認してください")
    assert result.label == "pattern_b"


def test_evaluation_is_pattern_b() -> None:
    result = classify_sensitivity("今期の人事評価を部長に提出する")
    assert result.label == "pattern_b"


def test_empty_text_is_pattern_a() -> None:
    result = classify_sensitivity("")
    assert result.label == "pattern_a"
