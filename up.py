import asyncio
import aiohttp
import json
from tqdm.asyncio import tqdm
from typing import List
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
assert api_key, "OPENAI_API_KEY is not set"

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

# Путь к входному и выходному файлам
input_path = "/Users/saraevsviatoslav/Documents/ai_knowledge_assistant/data/external/arxiv_filtered.json"
output_path = "/Users/saraevsviatoslav/Documents/ai_knowledge_assistant/data/external/new.jsonl"

# Ограничение по параллельности (не превышай лимит OpenAI)
MAX_CONCURRENT_REQUESTS = 5


async def fetch_embedding(session, abstract: str, title: str):
    url = "https://api.openai.com/v1/embeddings"
    payload = {
        "input": abstract,
        "model": "text-embedding-3-small"
    }

    async with session.post(url, headers=headers, json=payload) as response:
        if response.status == 200:
            result = await response.json()
            return {
                "title": title,
                "abstract": abstract,
                "embedding": result["data"][0]["embedding"]
            }
        else:
            error = await response.text()
            print(f"Error {response.status}: {error}")
            return None


async def process_entries(entries: List[dict]):
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    connector = aiohttp.TCPConnector(limit=MAX_CONCURRENT_REQUESTS)

    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = []

        async def sem_task(entry):
            async with semaphore:
                return await fetch_embedding(session, entry["abstract"], entry["title"])

        for entry in entries:
            tasks.append(sem_task(entry))

        results = []
        for f in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Embedding progress"):
            result = await f
            if result:
                results.append(result)
                with open(output_path, "a", encoding="utf-8") as f_out:
                    f_out.write(json.dumps(result) + "\n")
        return results


def load_data(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)



entries = load_data(input_path)
asyncio.run(process_entries(entries))