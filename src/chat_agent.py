import json
from openai import OpenAI
from dotenv import load_dotenv

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
- Answer in 2-4 sentences
- Cite specific cell line names

Tools:
- lookup_cell_line: get info on one cell
- search_by_lineage: find cells by tissue/disease
- check_assay_compatibility: check if cells work for an assay
- list_options: see valid values
"""


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_by_lineage",
            "description": "Search cells by lineage, disease, or subtype",
            "parameters": {
                "type": "object",
                "properties": {
                    "lineage": {"type": "string"},
                    "disease": {"type": "string"},
                    "subtype": {"type": "string"},
                    "top_n": {"type": "integer", "default": 10}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_assay_compatibility",
            "description": "Check if cells work for an assay",
            "parameters": {
                "type": "object",
                "properties": {
                    "cell_names": {"type": "array", "items": {"type": "string"}},
                    "assay_type": {"type": "string",
                        "enum": ["adherent_screen", "3d_spheroid", "suspension_screen", "flexible"]}
                },
                "required": ["cell_names", "assay_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_cell_line",
            "description": "Get info on one specific cell line",
            "parameters": {
                "type": "object",
                "properties": {
                    "name_or_id": {"type": "string"}
                },
                "required": ["name_or_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_options",
            "description": "List valid values for a category",
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
]


TOOL_FUNCTIONS = {
    "search_by_lineage": search_by_lineage,
    "check_assay_compatibility": check_assay_compatibility,
    "lookup_cell_line": lookup_cell_line,
    "list_options": list_options,
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