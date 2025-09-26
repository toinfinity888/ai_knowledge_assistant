import os, json, asyncio, aiohttp, uuid, math
from typing import List
from dotenv import load_dotenv
from tqdm.asyncio import tqdm
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance

# ───────────────────────────────
# 1. ПОДГОТОВКА
# ───────────────────────────────
load_dotenv()
QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')
QDRANT_HOST = os.getenv('QDRANT_HOST')
QDRANT_PORT = os.getenv('QDRANT_PORT')
API_KEY   = os.getenv("OPENAI_API_KEY")
assert API_KEY, "OPENAI_API_KEY не найден"

INPUT_PATH  = "/Users/saraevsviatoslav/Documents/ai_knowledge_assistant/data/external/arxiv_filtered.json"      # входной JSON (list[dict])
JSONL_PATH  = "/Users/saraevsviatoslav/Documents/ai_knowledge_assistant/data/external/new3.jsonl"   # будем дописывать построчно
JSONL_PATH2  = "/Users/saraevsviatoslav/Documents/ai_knowledge_assistant/data/external/new2.jsonl"   # будем дописывать построчно
COLLECTION  = "arxiv"
BATCH       = 64                         # сколько точек грузить в Qdrant за раз
MAX_CONC    = 10                         # параллельные запросы в OpenAI
EMB_MODEL   = "text-embedding-3-small"
EMB_SIZE    = 1536                       # размерность этой модели

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type":  "application/json"
}

# ───────────────────────────────
# 2. ЧТЕНИЕ ФИЛЬТРОВАННОГО JSON
# ───────────────────────────────
def load_entries(path: str) -> List[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)

# ───────────────────────────────
# 3. АСИНХРОННЫЙ EMBEDDING
# ───────────────────────────────
async def fetch_emb(session, abstract):
    url = "https://api.openai.com/v1/embeddings"
    payload = {"input": abstract, "model": EMB_MODEL}
    async with session.post(url, headers=headers, json=payload) as resp:
        data = await resp.json()
        if resp.status != 200:
            raise RuntimeError(data)
        return data["data"][0]["embedding"]

async def embed_all(entries: List[dict]):
    sem   = asyncio.Semaphore(MAX_CONC)
    conn  = aiohttp.TCPConnector(limit=MAX_CONC)
    async with aiohttp.ClientSession(connector=conn) as sess:
        async def one(entry):
            async with sem:
                emb = await fetch_emb(sess, entry["abstract"])
                out = {"id": str(uuid.uuid4()),
                       "title": entry["title"],
                       "abstract": entry["abstract"],
                       "embedding": emb}
                # пишем построчно, чтобы не потерять при сбое
                with open(JSONL_PATH, "a", encoding="utf-8") as f:
                    f.write(json.dumps(out, ensure_ascii=False) + "\n")
        tasks = [one(e) for e in entries]
        for coro in tqdm(asyncio.as_completed(tasks),
                         total=len(tasks), desc="Embedding"):
            await coro

# ───────────────────────────────
# 4. ЗАГРУЗКА В QDRANT
# ───────────────────────────────
def upload_to_qdrant(jsonl_path: str):
    client = QdrantClient(url=QDRANT_HOST,
                          port=QDRANT_PORT,
                          api_key=QDRANT_API_KEY)        
    if not client.collection_exists(COLLECTION):
        client.recreate_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=EMB_SIZE,
                                        distance=Distance.COSINE)
        )

    def gen_batches():
        batch = []
        with open(jsonl_path, encoding="utf-8") as f:
            for line in f:
                obj = json.loads(line)
                batch.append(
                    PointStruct(
                        id=obj["id"],
                        vector=obj["embedding"],
                        payload={
                            "title": obj["title"],
                            "abstract": obj["abstract"]
                        }
                    )
                )
                if len(batch) == BATCH:
                    yield batch
                    batch = []
            if batch:
                yield batch

    total_uploaded = 0
    for b in tqdm(gen_batches(), desc="Upload to Qdrant"):
        client.upload_points(collection_name=COLLECTION, points=b)
        total_uploaded += len(b)
    print(f"✅ Загружено в Qdrant: {total_uploaded} точек")

def load_already_embedded(path: str):
    embedded_titles = set()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    record = json.loads(line)
                    embedded_titles.add(record.get("title", ""))
                except json.JSONDecodeError:
                    continue
    return embedded_titles



# ───────────────────────────────
# 5. ГЛАВНЫЙ ЗАПУСК
# ───────────────────────────────
if __name__ == "__main__":

    # entries = load_entries(INPUT_PATH)
    # embedded_titles = load_already_embedded(JSONL_PATH)
    # remaining_entries = [e for e in entries if e["title"] not in embedded_titles]

    # # 5.1 Генерируем и сохраняем эмбеддинги
    # asyncio.run(embed_all(remaining_entries))

    # 5.2 Грузим всё в Qdrant
    upload_to_qdrant(JSONL_PATH)