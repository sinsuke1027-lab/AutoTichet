import os

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: requires Graph API credentials",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if not os.environ.get("AZURE_TENANT_ID"):
        skip = pytest.mark.skip(reason="AZURE_TENANT_ID 未設定 – 統合テストをスキップ")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip)
