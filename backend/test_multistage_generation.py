import time
import json
from app.services.ollama_generation import get_generation_client
from app.services.prompt_builder import (
    JSON_SCHEMA_INSTRUCTION,
    build_initial_story_prompt,
    LENGTH_SPECS,
    ATMOSPHERE_GUIDELINES,
)

client = get_generation_client()

premise = "A night watchman discovers the pendulum clock in the bell tower has stopped swinging, yet continues to chime."
atmosphere = "Quiet suspense"

print("--- Step 1: Generate Outline ---")
outline_system = (
    "You are the master literary architect of The Midnight Archivist. "
    "Your role is to plan an expansive, literary 3-act narrative outline (targeting 1,500 to 2,000 words total across 3 connected sections).\n\n"
    "Return your response as a valid JSON object matching EXACTLY this structure:\n"
    "{\n"
    '  "title": "Title of the Story",\n'
    '  "sections": [\n'
    '    {"act": "Act I: Inciting Incident", "summary": "Detailed narrative summary of section 1 (~550-650 words expected)"},\n'
    '    {"act": "Act II: Rising Dread & Complication", "summary": "Detailed narrative summary of section 2 (~550-650 words expected)"},\n'
    '    {"act": "Act III: Confrontation & Crossroads", "summary": "Detailed narrative summary of section 3 reaching a decisive crossroads (~550-650 words expected)"}\n'
    '  ]\n'
    "}"
)
outline_messages = [
    {"role": "system", "content": outline_system},
    {"role": "user", "content": f"Premise: {premise}\nAtmosphere: {atmosphere}\nCreate the 3-act outline."}
]
raw_outline = client.generate_chat_completion(outline_messages, format_json=True, max_tokens=800)
outline_data = json.loads(raw_outline)
title = outline_data.get("title", "The Chime in the Bell Tower")
sections = outline_data.get("sections", [])
print(f"Outline generated: '{title}' with {len(sections)} sections")

prose_sections = []

# Section 1
print("\n--- Step 2: Generating Section 1 ---")
s1_prompt = [
    {
        "role": "system",
        "content": (
            "You are the master literary narrator of The Midnight Archivist. "
            "Write Section 1 of a 3-part expansive atmospheric story.\n"
            "REQUIREMENTS:\n"
            "1. Write 4 to 5 expansive paragraphs (targeting approximately 550 to 650 words).\n"
            "2. Establish the setting with tactile sensory details, quiet dread, and deep immersion.\n"
            "3. Conclude Section 1 on an intriguing moment of discovery, leading into Section 2.\n"
            "4. Do NOT include markdown headings, section labels, or preamble.\n"
            'Return JSON: {"title": "' + title + '", "prose": "..."}'
        )
    },
    {
        "role": "user",
        "content": f"Story: \"{title}\"\nPremise: {premise}\nAtmosphere: {atmosphere}\nSection 1 Outline Focus: {sections[0]['summary']}\nWrite the prose (strictly 500-650 words)."
    }
]
r1 = client.generate_chat_completion(s1_prompt, format_json=True, max_tokens=1000)
d1 = json.loads(r1)
p1 = d1.get("prose", "")
words1 = len(p1.split())
print(f"Section 1 generated: {words1} words")
prose_sections.append(p1)

# Section 2
print("\n--- Step 3: Generating Section 2 ---")
s2_prompt = [
    {
        "role": "system",
        "content": (
            "You are the master literary narrator of The Midnight Archivist continuing Section 2 of a 3-part expansive atmospheric story.\n"
            "REQUIREMENTS:\n"
            "1. Continue directly from Section 1 without missing a beat.\n"
            "2. Write 4 to 5 expansive paragraphs (targeting approximately 550 to 650 words).\n"
            "3. Deepen the mystery and escalating tension.\n"
            "4. Do NOT re-introduce the protagonist or setting. Do NOT include headings or titles.\n"
            'Return JSON: {"prose": "..."}'
        )
    },
    {
        "role": "user",
        "content": f"Story: \"{title}\"\nPremise: {premise}\nAtmosphere: {atmosphere}\nSection 2 Outline Focus: {sections[1]['summary']}\nPreceding Section 1 conclusion:\n\"{p1[-400:]}\"\nWrite Section 2 prose (strictly 500-650 words)."
    }
]
r2 = client.generate_chat_completion(s2_prompt, format_json=True, max_tokens=1000)
d2 = json.loads(r2)
p2 = d2.get("prose", "")
words2 = len(p2.split())
print(f"Section 2 generated: {words2} words")
prose_sections.append(p2)

# Section 3
print("\n--- Step 4: Generating Section 3 & Branch Choices ---")
s3_prompt = [
    {
        "role": "system",
        "content": (
            "You are the master literary narrator of The Midnight Archivist concluding Section 3 of a 3-part expansive atmospheric story.\n"
            "REQUIREMENTS:\n"
            "1. Continue directly from Section 2 to a gripping climactic revelation.\n"
            "2. Write 4 to 5 expansive paragraphs (targeting approximately 550 to 650 words).\n"
            "3. End the narrative at a critical crossroads.\n"
            "4. Provide 2 or 3 distinct branch choices for where the protagonist ventures next.\n"
            'Return JSON: {"prose": "...", "branch_choices": [{"id": "choice_1", "label": "...", "description": "..."}, {"id": "choice_2", "label": "...", "description": "..."}]}'
        )
    },
    {
        "role": "user",
        "content": f"Story: \"{title}\"\nPremise: {premise}\nAtmosphere: {atmosphere}\nSection 3 Outline Focus: {sections[2]['summary']}\nPreceding Section 2 conclusion:\n\"{p2[-400:]}\"\nWrite Section 3 prose (strictly 500-650 words) and branch choices."
    }
]
r3 = client.generate_chat_completion(s3_prompt, format_json=True, max_tokens=1200)
d3 = json.loads(r3)
p3 = d3.get("prose", "")
words3 = len(p3.split())
choices = d3.get("branch_choices", [])
print(f"Section 3 generated: {words3} words, {len(choices)} branch choices")
prose_sections.append(p3)

assembled_story = "\n\n".join(prose_sections)
total_words = len(assembled_story.split())
print(f"\n=== ASSEMBLED STORY TOTAL WORDS: {total_words} ===")
print(f"Target range: 1,500 - 2,000 words. In bounds: {1500 <= total_words <= 2000}")
