"""
Direct test of the RAG system with language parameter
"""
import asyncio
from app.core.rag_singleton import rag_engine

async def test():
    # Test query about camera subscription issue
    query = "My 10 camera subscription is not showing and cameras stopped recording"

    print("Testing RAG Engine directly...")
    print(f"Query: {query}")
    print("="*80)

    # Test in English
    print("\n[ENGLISH TEST]")
    result_en = rag_engine.ask(query, language="en")
    print(f"Answer: {result_en['answer'][:500]}...")
    print(f"Context chunks found: {len(result_en['context_chunks'])}")

    # Test in French
    print("\n[FRENCH TEST]")
    result_fr = rag_engine.ask(query, language="fr")
    print(f"Réponse: {result_fr['answer'][:500]}...")
    print(f"Chunks de contexte trouvés: {len(result_fr['context_chunks'])}")

if __name__ == "__main__":
    asyncio.run(test())
