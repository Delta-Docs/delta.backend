from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph

from app.services.workflow.state import DriftAnalysisState
from app.services.workflow.nodes.scout_changes import scout_changes
from app.services.workflow.nodes.retrieve_docs import retrieve_docs
from app.services.workflow.nodes.deep_analyze import deep_analyze
from app.services.workflow.nodes.aggregate_results import aggregate_results


def build_drift_analysis_graph() -> CompiledStateGraph:
    graph = StateGraph(DriftAnalysisState)  # type: ignore[bad-specialization]

    graph.add_node("scout_changes", scout_changes)  # type: ignore[no-matching-overload]
    graph.add_node("retrieve_docs", retrieve_docs)  # type: ignore[no-matching-overload]
    graph.add_node("deep_analyze", deep_analyze)  # type: ignore[no-matching-overload]
    graph.add_node("aggregate_results", aggregate_results)  # type: ignore[no-matching-overload]

    graph.add_edge(START, "scout_changes")
    graph.add_edge("scout_changes", "retrieve_docs")
    graph.add_edge("retrieve_docs", "deep_analyze")
    graph.add_edge("deep_analyze", "aggregate_results")
    graph.add_edge("aggregate_results", END)

    return graph.compile()


drift_analysis_graph = build_drift_analysis_graph()
