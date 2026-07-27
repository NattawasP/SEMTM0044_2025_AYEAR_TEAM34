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
  "subtype": "EXACT DepMap Subtype string, or null",
  "match_level": "subtype, primary_disease, or lineage"
}

DepMap Lineage terms (USE EXACTLY THESE):
- lung, breast, skin, colorectal, ovary, prostate
- pancreas, liver, kidney, bladder, urinary_tract
- central_nervous_system, peripheral_nervous_system
- lymphoid, myeloid, blood
- bone, soft_tissue, thyroid, uterus
- upper_aerodigestive, esophagus, stomach, gastric

DepMap Disease examples (USE EXACT NAMES):
- "Lung Cancer", "Breast Cancer", "Colon/Colorectal Cancer"
- "Skin Cancer", "Bladder Cancer", "Ovarian Cancer"

DepMap Subtype format (COMPOUND — must use full string):
Lung subtypes:
- "Non-Small Cell Lung Cancer (NSCLC), Adenocarcinoma"      (for LUAD)
- "Non-Small Cell Lung Cancer (NSCLC), Squamous Cell Carcinoma"  (for LUSC)
- "Non-Small Cell Lung Cancer (NSCLC), Large Cell Carcinoma"
- "Non-Small Cell Lung Cancer (NSCLC), Adenosquamous Carcinoma"
- "Non-Small Cell Lung Cancer (NSCLC), unspecified"
- "Small Cell Lung Cancer (SCLC)"
- "Mesothelioma"
- "Carcinoid"

Breast subtypes:
- "Invasive Breast Carcinoma"
- "Ductal Adenocarcinoma"
- "Ductal Adenocarcinoma, exocrine"

Colorectal subtypes:
- "Colon Adenocarcinoma"
- "Adenocarcinoma"

Skin subtypes:
- "Melanoma"
- "Squamous Cell Carcinoma"

Synonyms to convert:
- HER2 → ERBB2
- NSCLC → Non-Small Cell Lung Cancer
- LUAD → subtype "Non-Small Cell Lung Cancer (NSCLC), Adenocarcinoma"
- LUSC → subtype "Non-Small Cell Lung Cancer (NSCLC), Squamous Cell Carcinoma"
- SCLC → subtype "Small Cell Lung Cancer (SCLC)"
- CRC → Colorectal Cancer

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