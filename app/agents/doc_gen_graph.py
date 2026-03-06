from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph

from app.agents.state import DocGenState
from app.agents.nodes.doc_gen_nodes import plan_updates, rewrite_docs, apply_changes


# Build and compile the document generation LangGraph workflow
def build_doc_gen_graph() -> CompiledStateGraph:
    graph = StateGraph(DocGenState)  # type: ignore[bad-specialization]

    # Register each processing node
    graph.add_node("plan_updates", plan_updates)  # type: ignore[no-matching-overload]
    graph.add_node("rewrite_docs", rewrite_docs)  # type: ignore[no-matching-overload]
    graph.add_node("apply_changes", apply_changes)  # type: ignore[no-matching-overload]

    # Add edges between the registered nodes
    graph.add_edge(START, "plan_updates")
    graph.add_edge("plan_updates", "rewrite_docs")
    graph.add_edge("rewrite_docs", "apply_changes")
    graph.add_edge("apply_changes", END)

    return graph.compile()


doc_gen_graph = build_doc_gen_graph()
