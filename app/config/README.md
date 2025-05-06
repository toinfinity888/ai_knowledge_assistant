# config/

This module contains centralized configuration for all project components. It loads values from environment variables (including a `.env` file if present) and defines static project paths for consistent and reusable structure across the codebase.

## Structure

- `qdrant_config.py` — Configuration for connecting to Qdrant (host, port, API key, collection name, vector size, distance metric, etc.)
- `paths_config.py` — Common project paths such as data directories, models, and reports
- `app_config.py` — Aggregates all individual configuration classes into a single `config` object for easy access across the project

## Usage

### Example: using settings in application code

```python
from config.app_config import config
from vector_store.qdrant_vector_store import QdrantVectorStore

# Pass Qdrant settings to your vector store
store = QdrantVectorStore(settings=config.qdrant)