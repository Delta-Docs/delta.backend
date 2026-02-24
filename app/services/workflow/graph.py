from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph

from app.services.workflow.state import DriftAnalysisState

def build_drift_analysis_graph() -> CompiledStateGraph:
    graph = StateGraph(DriftAnalysisState)

    return graph.compile()


drift_analysis_graph = build_drift_analysis_graph()
