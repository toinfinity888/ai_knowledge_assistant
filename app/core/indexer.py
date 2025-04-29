from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, Distance, VectorParams
from flask import Flask, request
from loguru import logger
import uuid
import typer

app = Flask(__name__)
cli = typer.Typer()

@cli.command(help="Agregation of data and stock them on the data base")
def main():
    model = SentenceTransformer('all-MiniLM-L6-v2')

    texts = ["The weather is lovely today.",
    "It's so sunny outside!",
    "He drove to the stadium.",]

    embeddings = model.encode(texts)

    client = QdrantClient(url="https://94795b07-482f-417e-8e62-b298c5163df0.eu-central-1-0.aws.cloud.qdrant.io:6333",
                        port=6333,
                        api_key=)

    if not client.collection_exists("docs"):
        client.recreate_collection(
            collection_name="docs",
            vectors_config=VectorParams(size=embeddings.shape[1], distance=Distance.COSINE),
        )

    client.upload_points(
        collection_name="docs",
        points=[
            PointStruct(id=uuid.uuid4().int>>64, vector=vec.tolist(), payload={"text":text})
            for text, vec in zip(texts, embeddings)
        ]
    )

    query = "What's the weather like today?"
    query_vector = model.encode(query).tolist()

    hits = client.search(
        collection_name="docs",
        query_vector=query_vector,
        limit=3
    )

    for hit in hits:
        logger.info(f"{hit.payload['text']}, '→', {hit.score}")

if __name__ == "__main__":
    cli()