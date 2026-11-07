from langgraph.graph import END, START, StateGraph
from app.agents.portfolio_review.state import ReviewState
from app.agents.portfolio_review.nodes import build_nodes
from app.agents.portfolio_review.routing import route_research


def build_review_graph(session, settings):
    graph = StateGraph(ReviewState)
    calculate, research, no_targets, verify, report = build_nodes(session, settings)
    for name, node in [("calculate", calculate), ("research", research), ("no_targets", no_targets), ("verify", verify), ("report", report)]:
        graph.add_node(name, node)
    graph.add_edge(START, "calculate")
    graph.add_conditional_edges("calculate", route_research, {"research": "research", "no_targets": "no_targets"})
    graph.add_edge("research", "verify")
    graph.add_edge("no_targets", "verify")
    graph.add_edge("verify", "report")
    graph.add_edge("report", END)
    return graph.compile()
