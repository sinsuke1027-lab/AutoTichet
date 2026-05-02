import operator
from functools import partial
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, StateGraph

from src.agents import nodes
from src.models.task import ExtractedTask, SensitivityResult
from src.providers.base import LLMProvider


class AgentState(TypedDict):
    source_text: str
    source_type: str
    source_id: str
    sensitivity: SensitivityResult | None
    extracted_tasks: list[ExtractedTask]
    actions: list[tuple[str, str]]
    errors: Annotated[list[str], operator.add]


def build_graph(
    llm_provider: LLMProvider,
    auto_threshold: float,
    review_threshold: float,
) -> Any:
    builder: StateGraph[AgentState] = StateGraph(AgentState)

    # Node functions accept dict[str, Any] for flexibility; structurally
    # compatible with AgentState at runtime. Suppress mypy's type-var constraint.
    builder.add_node("classify", nodes.node_classify)  # type: ignore[type-var]
    builder.add_node(
        "extract",
        partial(nodes.node_extract, llm_provider=llm_provider),
    )
    builder.add_node(
        "route",
        partial(
            nodes.node_route,
            auto_threshold=auto_threshold,
            review_threshold=review_threshold,
        ),
    )

    builder.set_entry_point("classify")
    builder.add_edge("classify", "extract")
    builder.add_edge("extract", "route")
    builder.add_edge("route", END)

    return builder.compile()
