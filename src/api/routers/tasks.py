from fastapi import APIRouter, Depends

from src.models.config import Settings, get_settings
from src.services.classifier import classify_sensitivity

router = APIRouter(prefix="/tasks")


@router.post("/extract")
async def extract_from_text(
    text: str,
    source_type: str = "email",
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> dict[str, object]:
    sensitivity = classify_sensitivity(text)
    if sensitivity.label == "pattern_b":
        return {"tasks": [], "skipped_reason": "機密データ（Pattern B）"}

    from src.providers.factory import create_llm_provider

    provider = create_llm_provider(settings)
    tasks = await provider.extract_tasks(text, source_type)
    return {"tasks": [t.model_dump() for t in tasks]}
