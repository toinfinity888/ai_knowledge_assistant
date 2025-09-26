import json
import uuid

input_path = "/Users/saraevsviatoslav/Documents/ai_knowledge_assistant/data/external/new.jsonl"
output_path = "/Users/saraevsviatoslav/Documents/ai_knowledge_assistant/data/external/new3.jsonl"

with open(input_path, "r", encoding="utf-8") as fin, open(output_path, "w", encoding="utf-8") as fout:
    for idx, line in enumerate(fin):
        item = json.loads(line)
        item["id"] = str(uuid.uuid4()) # или: str(uuid.uuid4())
        fout.write(json.dumps(item) + "\n")