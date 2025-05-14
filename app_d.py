from fastapi import FastAPI
from app.dashboard.routes import dashboard_router

app_dash = FastAPI(title='AI Knowledge Assistant + RAG Dashboard')
app_dash.include_router(dashboard_router)
