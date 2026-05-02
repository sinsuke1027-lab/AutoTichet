from typing import Protocol, runtime_checkable

from src.models.task import ExtractedTask


@runtime_checkable
class LLMProvider(Protocol):
    """LLMプロバイダーのプロトコル（構造的部分型）"""

    async def extract_tasks(self, text: str, source_type: str) -> list[ExtractedTask]:
        """テキストからタスクを抽出する

        Args:
            text: 抽出対象のテキスト（メール本文・議事録など）
            source_type: ソースの種類（email / meeting / chat など）

        Returns:
            抽出されたタスクのリスト
        """
        ...


@runtime_checkable
class VisionLLMProvider(Protocol):
    """ビジョン対応LLMプロバイダーのプロトコル"""

    async def analyze_image(self, image: bytes, comment: str) -> str:
        """画像を分析してテキスト説明を生成する

        Args:
            image: 画像バイナリデータ
            comment: 画像に付与されたコメント・補足情報

        Returns:
            画像の説明文
        """
        ...
