"""
Test questions with the expected tool the agent should call. This measures
agentic decision quality specifically - not whether the final answer is
well-written, but whether the model correctly routes each question type to
the right tool. Add more cases as you find questions the agent handles
surprisingly well or badly.
"""

TOOL_EVAL_SET = [
    {
        "query": "How much did I spend on Swiggy in June 2026?",
        "expected_tool": "query_orders",
    },
    {
        "query": "How many orders did I place in May 2026?",
        "expected_tool": "query_orders",
    },
    {
        "query": "Show me orders similar to healthy bowls",
        "expected_tool": "semantic_search",
    },
    {
        "query": "What are some spicy dishes I've ordered before?",
        "expected_tool": "semantic_search",
    },
    {
        "query": "Compare my Zomato and Swiggy spending for June 2026",
        "expected_tool": "compare_platforms",
    },
    {
        "query": "Which platform did I spend more on in June 2026?",
        "expected_tool": "compare_platforms",
    },
    {
        "query": "Give me a full spending report for June 2026",
        "expected_tool": "generate_monthly_report",
    },
    {
        "query": "Summarize all my food delivery spending for June 2026",
        "expected_tool": "generate_monthly_report",
    },
]
