from contextlib import nullcontext

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.models.config import Settings, get_settings
from src.models.task import ExtractedTask
from src.services.classifier import classify_sensitivity
from src.services.langfuse_client import get_langfuse_client

router = APIRouter(prefix="/tasks")


class ExtractRequest(BaseModel):
    text: str
    source_type: str = "email"


class ExtractResponse(BaseModel):
    tasks: list[ExtractedTask]
    skipped_reason: str | None = None


@router.post("/extract", response_model=ExtractResponse)
async def extract_from_text(
    body: ExtractRequest,
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> ExtractResponse:
    langfuse = get_langfuse_client(settings)
    ctx = (
        langfuse.start_as_current_observation(
            name="extract_from_text",
            as_type="chain",
            input={"text": body.text, "source_type": body.source_type},
        )
        if langfuse
        else nullcontext()
    )

    async with ctx:  # type: ignore[union-attr]
        sensitivity = classify_sensitivity(body.text)

        if langfuse:
            langfuse.start_observation(
                name="classify_sensitivity",
                as_type="span",
                input={"text": body.text},
                output=sensitivity.model_dump(),
            )

        if sensitivity.label == "pattern_b":
            result = ExtractResponse(tasks=[], skipped_reason="機密データ（Pattern B）")
            if langfuse:
                langfuse.set_current_trace_io(
                    input={"text": body.text, "source_type": body.source_type},
                    output=result.model_dump(),
                )
            return result

        from src.providers.factory import create_llm_provider

        provider = create_llm_provider(settings)
        extracted = await provider.extract_tasks(body.text, body.source_type)
        result = ExtractResponse(tasks=extracted)

        if langfuse:
            langfuse.set_current_trace_io(
                input={"text": body.text, "source_type": body.source_type},
                output=result.model_dump(),
            )

        return result
