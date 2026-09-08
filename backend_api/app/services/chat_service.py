"""
Chat service — OpenAI function-calling loop for the CellLineFinder chatbot.

The LLM receives a system prompt describing available tools, then
iteratively calls them to answer scientist questions about cell lines.
"""

import json
import os
import logging

from openai import OpenAI

from app.services.chat_tools import (
    get_gene_context,
    search_by_lineage,
    check_assay_compatibility,
    lookup_cell_line,
    list_options,
)

logger = logging.getLogger(__name__)

# ── OpenAI client ────────────────────────────────────────────

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY not set. Add it to .env or environment variables."
            )
        _client = OpenAI(api_key=api_key)
    return _client


# ── System prompt ────────────────────────────────────────────

SYSTEM_PROMPT = """You help scientists find cell lines for their experiments.

Rules:
- Always use tools to get real data — never make things up
- When the user mentions a specific gene, call get_gene_context FIRST
- Answer in 2-4 sentences, citing specific cell line names
- If a search finds NO cells, call list_options('lineages') to check valid values

IMPORTANT — Tool usage:
- When check_assay_compatibility returns WARN cells, ALWAYS mention them
  with their warning message. Never silently hide warnings.
- When passing cells between tools, always use actual results from a previous
  call. Never pass empty lists.
- If ALL cells in results have WARN, say so clearly and suggest alternatives.

Gene-specific behavior:
- Housekeeping genes (GAPDH, ACTB, TUBB): warn that expression ranking is
  not meaningful for these genes
- T-cell markers (CD3E): search 'blood' or 'lymphoid' lineages
- B-cell markers (CD19, CD20): search 'lymphoid'
- If data availability is limited (from get_gene_context): mention it

Limitation acknowledgment:
- You can search by lineage/disease and check assay compatibility
- You can look up individual cell line metadata
- If the user asks about expression ranking, explain that the main
  CellLineFinder search interface handles expression-based ranking

Tools:
- get_gene_context: AZ notes on a target gene (CALL FIRST when gene is mentioned)
- lookup_cell_line: get info on one cell line
- search_by_lineage: find cells by tissue/disease
- check_assay_compatibility: check if cells work for an assay type
- list_options: see valid values for lineages, diseases, growth patterns, assays

Standard workflows:
- Gene query: get_gene_context → search_by_lineage → answer
- Cell lookup: lookup_cell_line → answer
- Assay query: search_by_lineage → check_assay_compatibility → answer
"""


# ── Tool definitions for OpenAI ──────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_by_lineage",
            "description": (
                "Search cell lines by lineage, disease, or subtype. "
                "Returns top N cells ranked by hierarchical match score "
                "(1.0=exact subtype, 0.75=same disease, 0.50=same lineage). "
                "Provide at least one of lineage/disease/subtype."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "lineage": {
                        "type": "string",
                        "description": "Tissue type lowercase e.g. 'lung', 'breast'",
                    },
                    "disease": {
                        "type": "string",
                        "description": "Disease name e.g. 'Lung Cancer'",
                    },
                    "subtype": {
                        "type": "string",
                        "description": "Disease subtype e.g. 'Non-Small Cell Lung Cancer (NSCLC), Adenocarcinoma'",
                    },
                    "top_n": {"type": "integer", "default": 10},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_assay_compatibility",
            "description": (
                "Check if cell lines work for an assay type. "
                "Returns OK/WARN status per cell. "
                "cell_names MUST be non-empty — call search_by_lineage first."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cell_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of cell line names to check",
                    },
                    "assay_type": {
                        "type": "string",
                        "enum": [
                            "adherent_screen",
                            "3d_spheroid",
                            "suspension_screen",
                            "flexible",
                        ],
                    },
                },
                "required": ["cell_names", "assay_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_cell_line",
            "description": (
                "Get full metadata (lineage, disease, subtype, growth pattern, "
                "sex) for one cell line by name or ACH-ID."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name_or_id": {
                        "type": "string",
                        "description": "Cell name (e.g. 'HCC827') or ACH-ID (e.g. 'ACH-000012')",
                    },
                },
                "required": ["name_or_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_options",
            "description": (
                "List valid values for a category. Call when unsure what values "
                "exist (e.g. before search_by_lineage to find valid lineage names)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["lineages", "diseases", "growth_patterns", "assays"],
                    },
                },
                "required": ["category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_gene_context",
            "description": (
                "Get AstraZeneca notes on a target gene — includes data availability "
                "(proteomics/transcriptomics/GEO) and biological caveats. "
                "CALL THIS FIRST whenever a specific gene is mentioned."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "gene_symbol": {
                        "type": "string",
                        "description": "Gene symbol e.g. EGFR, ERBB2, GAPDH, CD3E",
                    },
                },
                "required": ["gene_symbol"],
            },
        },
    },
]


# ── Tool dispatch ────────────────────────────────────────────

TOOL_FUNCTIONS = {
    "search_by_lineage": search_by_lineage,
    "check_assay_compatibility": check_assay_compatibility,
    "lookup_cell_line": lookup_cell_line,
    "list_options": list_options,
    "get_gene_context": get_gene_context,
}


# ── Main chat function ───────────────────────────────────────

MAX_TOOL_ROUNDS = 5
MODEL = os.getenv("CHAT_MODEL", "gpt-4o-mini")


def chat(user_message: str, history: list[dict] | None = None) -> dict:
    """
    Process a chat message using OpenAI function calling.

    Args:
        user_message: The user's question.
        history: Optional list of previous messages [{role, content}, ...].

    Returns:
        {"answer": str, "tool_calls_made": list[str], "history": list[dict]}
    """
    client = _get_client()

    # Build messages list
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if history:
        # Only include user/assistant messages from history (skip system, tool)
        for msg in history:
            if msg.get("role") in ("user", "assistant"):
                messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": user_message})

    tool_calls_made = []

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            temperature=0,
        )

        msg = response.choices[0].message
        messages.append(msg)

        # If no tool calls, we have the final answer
        if not msg.tool_calls:
            answer = msg.content or "I couldn't generate a response."
            break

        # Execute each tool call
        for tool_call in msg.tool_calls:
            func_name = tool_call.function.name
            try:
                args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                args = {}

            logger.info(f"Chat tool call: {func_name}({args})")
            tool_calls_made.append(func_name)

            if func_name in TOOL_FUNCTIONS:
                try:
                    result = TOOL_FUNCTIONS[func_name](**args)
                except Exception as e:
                    result = {"error": str(e)}
            else:
                result = {"error": f"Unknown tool: {func_name}"}

            # Truncate large results to avoid token overflow
            result_str = json.dumps(result, default=str)
            if len(result_str) > 3000:
                result_str = result_str[:3000] + '..."}'

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result_str,
            })
    else:
        answer = "Sorry, I needed too many steps to answer that. Try a simpler question."

    # Build clean history for the frontend
    clean_history = []
    if history:
        clean_history.extend(history)
    clean_history.append({"role": "user", "content": user_message})
    clean_history.append({"role": "assistant", "content": answer})

    return {
        "answer": answer,
        "tool_calls_made": tool_calls_made,
        "history": clean_history,
    }
