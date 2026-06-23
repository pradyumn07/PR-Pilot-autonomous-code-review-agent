from langgraph.graph import StateGraph, END
from .state import PRReviewState
from .nodes import (
    load_pr_state,
    ast_parse_node,
    semgrep_scan_node,
    llm_review_node,
    synthesize_review_node,
    post_review_node,
    request_human_node,
    generate_tests_node
)


def should_post_or_flag(state: PRReviewState) -> str:
    if state.get("should_post"):
        return "post"
    return "flag"


def build_graph():
    graph = StateGraph(PRReviewState)

    # Add all nodes
    graph.add_node("load_pr_state", load_pr_state)
    graph.add_node("ast_parse_node", ast_parse_node)
    graph.add_node("semgrep_scan_node", semgrep_scan_node)
    graph.add_node("llm_review_node", llm_review_node)
    graph.add_node("synthesize_review_node", synthesize_review_node)
    graph.add_node("post_review_node", post_review_node)
    graph.add_node("request_human_node", request_human_node)
    graph.add_node("generate_tests_node", generate_tests_node)

    # Entry point
    graph.set_entry_point("load_pr_state")

    # Fan-out to parallel nodes
    graph.add_edge("load_pr_state", "ast_parse_node")
    graph.add_edge("load_pr_state", "semgrep_scan_node")
    graph.add_edge("load_pr_state", "llm_review_node")

    # Fan-in to synthesize
    graph.add_edge("ast_parse_node", "synthesize_review_node")
    graph.add_edge("semgrep_scan_node", "synthesize_review_node")
    graph.add_edge("llm_review_node", "synthesize_review_node")

    # Confidence routing
    graph.add_conditional_edges(
        "synthesize_review_node",
        should_post_or_flag,
        {
            "post": "post_review_node",
            "flag": "request_human_node"
        }
    )

    # After posting, generate tests
    graph.add_edge("post_review_node", "generate_tests_node")
    graph.add_edge("request_human_node", END)
    graph.add_edge("generate_tests_node", END)

    return graph.compile()


pr_pilot_graph = build_graph()