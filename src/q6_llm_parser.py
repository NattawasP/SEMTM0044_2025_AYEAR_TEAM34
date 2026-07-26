"""
Q6 LLM Parser: natural language to structured  
"""
import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI() 

SYSTEM_PROMPT = """You extract cell-line search info from a scientist's query.

Return ONLY valid JSON with these fields:
{
  "target_gene": "gene symbol like EGFR, or null",
  "lineage": "DepMap lineage in lowercase, or null",
  "primary_disease": "DepMap disease name in Title Case, or null",
  "subtype": "specific subtype, or null",
  "match_level": "subtype, primary_disease, or lineage"
}

DepMap Lineage terms (USE EXACTLY THESE):
- lung, breast, skin, colorectal, ovary, prostate
- pancreas, liver, kidney, bladder, urinary_tract
- central_nervous_system, peripheral_nervous_system
- lymphoid, myeloid, blood
- bone, soft_tissue, thyroid, uterus
- upper_aerodigestive, esophagus, stomach

DepMap Disease examples (USE EXACT NAMES):
- "Lung Cancer", "Non-Small Cell Lung Cancer", "Small Cell Lung Cancer"
- "Breast Cancer"
- "Colon/Colorectal Cancer"
- "Skin Cancer", "Melanoma"
- "Bladder Cancer"
- "Ovarian Cancer"
- "Pancreatic Cancer"
- "Liver Cancer"
- "Brain Cancer"

Synonyms to convert:
- HER2 → ERBB2
- NSCLC → Non-Small Cell Lung Cancer
- LUAD → Lung Adenocarcinoma
- CRC → Colorectal Cancer
- colon → colorectal (lineage)
- kidney → kidney (not renal)

Use null if not sure. Be conservative — better null than wrong.
"""

def parse_query(user_input):
    response = client.chat.completions.create(
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