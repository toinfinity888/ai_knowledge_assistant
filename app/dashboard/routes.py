import pandas as pd
import matplotlib as plt
from fastapi import APIRouter, Request, BackgroundTasks
import subprocess
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from app.config.path_config import DASHBOARD_TEMPLATES, PROCESSED_DATA_DIR, PROJ_ROOT
from app.core.logger import logger

dashboard_router = APIRouter()
templates_path = Path(DASHBOARD_TEMPLATES)
templates = Jinja2Templates(directory=templates_path)
result_path = PROCESSED_DATA_DIR / 'evaluating_result.json'


@dashboard_router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    if result_path.exists() and result_path.stat().st_size > 0:
        df = pd.read_json(result_path)
    else:
        logger.warning(f"Evaluation result missing or empty at {result_path.resolve()}")
        df = pd.DataFrame(columns=['query', 'context_recall', 'faithfulness', 'factual_correctness'])
    logger.info(f"Loaded evaluation data: {df.head()}")

    return templates.TemplateResponse('dashboard.html', {
        'request': request,
        'result': df.to_dict(orient='records'),
        'file_found': result_path.exists() and result_path.stat().st_size > 0
    })

@dashboard_router.post("/re-evaluate")
async def re_evaluate():
    evaluator_path = PROJ_ROOT / 'ragas_evaluator.py'
    try:
        subprocess.run(["python", str(evaluator_path)], check=True)
        return {"success": True}
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        return {"success": False, "error": str(e)}