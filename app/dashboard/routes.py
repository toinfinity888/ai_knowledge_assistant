import subprocess
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from app.config.path_config import DASHBOARD_TEMPLATES, PROCESSED_DATA_DIR, PROJ_ROOT
from app.logging.logger import logger
from app.dashboard.log_history import EvaluationLogs
from app.database.postgresql_session import SessionLocal

json_path: Path = PROCESSED_DATA_DIR

dashboard_router = APIRouter()
templates_path = Path(DASHBOARD_TEMPLATES)
templates = Jinja2Templates(directory=templates_path)
result_path = PROCESSED_DATA_DIR / 'evaluating_result.json'


@dashboard_router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    session = SessionLocal()
    try:
        logs = session.query(EvaluationLogs).all()
        if logs:
            result = [{
                'user_input': log.query,
                'context_recall': float(log.context_recall),
                'faithfulness': float(log.faithfulness),
                'factual_correctness': float(log.factual_correctness)
            } for log in logs]
            file_found = True
        else:
            result = []
            file_found = False
    except Exception as e:
        logger.error(f'Error fetching data from PostgeSQL: {e}')
        result = []
        file_found = False
    finally:
        session.close()

    return templates.TemplateResponse('dashboard.html', {
        'request': request,
        'result': result,
        'file_found': file_found
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