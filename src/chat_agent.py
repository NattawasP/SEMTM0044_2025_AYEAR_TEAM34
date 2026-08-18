import json
from openai import OpenAI
from dotenv import load_dotenv
from gene_context import get_gene_context

from search_tools import (
    search_by_lineage,
    check_assay_compatibility,
    lookup_cell_line,
    list_options,
)

load_dotenv()
client = OpenAI()


SYSTEM_PROMPT = """You help scientists find cell lines.

Rules:
- Always use tools to get real data, don't make things up
- When user mentions a specific gene, call get_gene_context FIRST
- Answer in 2-4 sentences
- Cite specific cell line names

IMPORTANT — Tool usage:
- When check_assay_compatibility returns WARN cells, ALWAYS mention them
  with their warning message. Never silently hide cells.
- If a search finds NO cells matching a lineage, call list_options('lineages')
  to see valid values, then try synonyms (e.g. T-cell → blood/lymphoid)
- When passing cells between tools, always use actual results from previous
  call. Never pass empty lists.
- If ALL cells in results have WARN, say so clearly and suggest alternatives.

Gene-specific behavior:
- Housekeeping genes (GAPDH, ACTB, TUBB): warn "expression not meaningful"
- T-cell markers (CD3E): search 'blood' or 'lymphoid' lineages
- B-cell markers (CD19, CD20): search 'lymphoid'
- If data availability limited (from get_gene_context): mention it

Limitation acknowledgment:
- You DON'T have direct expression data tools yet (RNA/protein rankings)
- If user asks "top expressers" or "highest expression":
  * Explain you can filter by tissue but not rank by expression yet
  * Suggest they check Q1/Q2 modules directly

Tools:
- get_gene_context: AZ notes on a target gene (CALL FIRST when gene is mentioned)
- lookup_cell_line: get info on one cell
- search_by_lineage: find cells by tissue/disease
- check_assay_compatibility: check if cells work for an assay
- list_options: see valid values

Standard workflows:
- Gene query: get_gene_context → search_by_lineage → answer
- Cell lookup: lookup_cell_line → answer
- Assay query: search_by_lineage → check_assay_compatibility → answer
"""


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_by_lineage",
            "description": "Search cells by lineage, disease, or subtype. Returns top N cells ranked by hierarchical match score (1.0=exact subtype+lineage, 0.75=same disease, 0.50=same lineage). Provide at least one of lineage/disease/subtype.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lineage": {"type": "string", "description": "Tissue lowercase e.g. 'lung', 'breast'"},
                    "disease": {"type": "string", "description": "Full DepMap disease name e.g. 'Lung Cancer'"},
                    "subtype": {"type": "string", "description": "Full DepMap subtype e.g. 'Non-Small Cell Lung Cancer (NSCLC), Adenocarcinoma'"},
                    "top_n": {"type": "integer", "default": 10}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_assay_compatibility",
            "description": "Check if cells work for an assay. Returns OK/WARN status per cell. Cell_names MUST be non-empty, pass results from search_by_lineage first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cell_names": {"type": "array", "items": {"type": "string"}},
                    "assay_type": {"type": "string","enum": ["adherent_screen", "3d_spheroid", "suspension_screen", "flexible"]}
                },
                "required": ["cell_names", "assay_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_cell_line",
            "description": "Get full metadata (lineage, disease, subtype, growth pattern, sex, age, source) for one specific cell line by name or ACH-ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name_or_id": {"type": "string", "description": "Cell name (e.g. 'HCC827') or ACH-ID (e.g. 'ACH-000012')"}
                },
                "required": ["name_or_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_options",
            "description": "List valid values for a category. Call when unsure what values exist (e.g. before search_by_lineage to find valid lineage names).",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string",
                        "enum": ["lineages", "diseases", "growth_patterns", "assays"]}
                },
                "required": ["category"]
            }
        }
    },
    {
        "type": "function",
        "function":{
            "name": "get_gene_context",
            "description": "Get AstraZeneca notes on a target gene, includes data availability (proteomics/transcriptomics/GEO) and biological caveats (housekeeping genes, marker genes). CALL THIS FIRST whenever a specific gene is mentioned.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gene_symbol": {
                        "type": "string",
                        "description": "Gene symbol e.g. EGFR, ERBB2, GAPDH, CD3E"
                    }
                },
                "required": ["gene_symbol"]
            }
        }
    }
]


TOOL_FUNCTIONS = {
    "search_by_lineage": search_by_lineage,
    "check_assay_compatibility": check_assay_compatibility,
    "lookup_cell_line": lookup_cell_line,
    "list_options": list_options,
    "get_gene_context": get_gene_context
}


def chat(user_message):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message}
    ]

    for _ in range(5):
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=TOOLS,
            temperature=0,
        )

        msg = response.choices[0].message
        messages.append(msg)

        if not msg.tool_calls:
            return msg.content

        for tool_call in msg.tool_calls:
            func_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)

            print(f"  [{func_name}({args})]")
            result = TOOL_FUNCTIONS[func_name](**args)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result, default=str)[:3000]
            })

    return "Sorry, too many tool calls."