import typer
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance
from dotenv import load_dotenv
import requests
import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
app = typer.Typer()

load_dotenv()

# Get required Qdrant credentials from environment
qdrant_key = os.getenv('QDRANT_CLOUD_KEY')
qdrant_url = os.getenv('QDRANT_CLOUD_URL')
# Initialize Qdrant client
qdrant_client = QdrantClient(
    url=qdrant_url,
    api_key=qdrant_key
)

@app.command(help="Ask a question to knowledge base using Qdrant + Ollama")
def ask():
    model = SentenceTransformer('BAAI/bge-base-en-v1.5')

    while True:
        question = typer.prompt("Enter your question")
        if question.strip().lower() in {"exit", "quit"}:
            typer.echo("Goodbye!")
            break

        query_vector = model.encode(question).tolist()

        hits = qdrant_client.search(
            collection_name='docs',
            query_vector=query_vector,
            limit=3
        )
        if not hits:
            typer.echo("No relevant documents found.")
            continue

        context = "\n\n".join(hit.payload['text'] for hit in hits)

        prompt = f"""Use the context below to answer the question.
            Context:
            {context}

            Question: {question}
            Answer:"""

        # Call Ollama (localhost:11434)
        response = requests.post('http://localhost:11434/api/generate', json={
            'model': 'mistral',
            'prompt': prompt,
            'stream': False
        })

        if response.status_code != 200:
            typer.echo("Failed to get response from Ollama")
            continue
        
        answer = response.json()["response"]
        typer.secho("\Answer:", fg=typer.colors.GREEN, bold=True)
        typer.echo(answer)
        typer.echo('-' * 60)

if __name__ == "__main__":
    app()