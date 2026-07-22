"""
Q6 LLM Parser: natural language to structured  
"""
import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from rapidfuzz import process, fuzz

load_dotenv()
client = OpenAI() 

SYSTEM_PROMPT = """You extract cell-line search criteria from a scientist's query.

Return ONLY a valid JSON object with these fields:
{
  "target_gene": "<hugo symbol (e.g. EGFR, ERBB2, KRAS) or null>",
  "lineage": "<DepMap lineage in lowercase (e.g. lung, breast, skin, colon) or null>",
  "primary_disease": "<full DepMap disease name (e.g. 'Lung Cancer', 'Non-Small Cell Lung Cancer') or null>",
  "subtype": "<Oncotree subtype (e.g. 'Lung Adenocarcinoma') or null>",
  "match_level": "<'subtype' | 'primary_disease' | 'lineage'>"
}

Rules:
- Use DepMap OncotreeLineage terminology
- Handle synonyms: NSCLC → Non-Small Cell Lung Cancer
- LUAD → Lung Adenocarcinoma
- HER2+ → target_gene = "ERBB2"
- If uncertain about subtype, leave null
- match_level = the deepest level user was specific about
- Return null (not empty string) if unknown
"""

def parse_query(user_input):
    response = client.chat.completion.create(
        model="gpt-4o-mini",
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_input}
        ]
    )
    return json.loads(response.choices[0].message.content)

def validate(parsed, dim):
    result = parsed.copy()
    result['warnings'] = []
    
    valid_lineages = set(dim['lineage'].dropna().unique())
    valid_diseases = set(dim['primary_disease'].dropna().unique())

    if result.get('lineage') and result['lineage'] not in valid_lineages:
        result['warnings'].append(f"lineage '{result['lineage']}' not found")
        result['lineage'] = None

    if result.get('primary_disease') and result['primary_disease'] not in valid_diseases:
        result['warnings'].append(f"disease '{result['primary_disease']}' not found")
        result['primary_disease'] = None

    return result

def parse_and_validate(user_input, dim):
    parsed = parse_query(user_input)
    return validate(parsed, dim)