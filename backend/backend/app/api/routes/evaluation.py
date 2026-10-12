from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.database import get_db, SessionLocal
from app.core.auth import get_current_user
from app.models.user import User
from app.models.evaluation import EvaluationRun
from app.schemas.evaluation import (
    EvaluationRunRequest,
    EvaluationRunResponse,
    EvaluationStatusResponse,
    EvaluationResultsResponse,
)
from app.services.evaluation.evaluator import get_evaluation_engine, EvaluationEngine
from app.core.logging_config import logger

router = APIRouter(prefix="/evaluation", tags=["Evaluation"])

def _run_eval_background(eval_id: str, request_data: dict):
    """Background task worker for evaluation runs."""
    from app.services.evaluation.eval_lock import get_evaluation_lock_manager
    lock_mgr = get_evaluation_lock_manager()
    db = SessionLocal()
    try:
        run = db.query(EvaluationRun).filter(EvaluationRun.id == eval_id).first()
        if not run:
            return
        engine = get_evaluation_engine()
        req = EvaluationRunRequest.model_validate(request_data)
        engine.run_evaluation(db=db, request=req, existing_run_id=eval_id)
    except Exception as e:
        logger.error(f"Background evaluation error for run '{eval_id}': {e}", exc_info=True)
        try:
            failed_run = db.query(EvaluationRun).filter(EvaluationRun.id == eval_id).first()
            if failed_run and failed_run.status in ("running", "pending"):
                from datetime import datetime, timezone
                failed_run.status = "failed"
                err_msg = str(e)
                if "429" in err_msg or "rate limit" in err_msg.lower() or "temporarily busy" in err_msg.lower():
                    failed_run.error_message = "Evaluation failed: AI service rate limit reached (HTTP 429). Please try again later."
                else:
                    failed_run.error_message = err_msg
                failed_run.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            pass
    finally:
        lock_mgr.release(eval_id)
        db.close()


@router.post("/run", response_model=EvaluationRunResponse, status_code=status.HTTP_201_CREATED)
def start_evaluation_run(
    payload: EvaluationRunRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Launch an evaluation run.
    Evaluates RAG retrieval, grounded answer generation, citation correctness,
    off-material rejection, cross-course isolation, assessment question quality,
    duplicate rates, and simulated learner model personalization.
    Only authenticated users may launch an evaluation.
    """
    import uuid
    from datetime import datetime, timezone
    from app.services.evaluation.eval_lock import get_evaluation_lock_manager

    lock_mgr = get_evaluation_lock_manager()

    # Step 4: Prevent multiple concurrent evaluations
    is_active, active_id = lock_mgr.is_running(db=db)
    if is_active:
        logger.warning(f"Rejecting evaluation run request: another evaluation ('{active_id}') is already active.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An evaluation is already running. Please wait for it to finish."
        )

    engine = get_evaluation_engine()
    run_id = str(uuid.uuid4())

    if not lock_mgr.acquire(run_id, db=db):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An evaluation is already running. Please wait for it to finish."
        )

    if payload.sync:
        try:
            # Run synchronously to completion
            run = engine.run_evaluation(db=db, request=payload, existing_run_id=run_id)
            run.user_id = current_user.id
            db.commit()
            return EvaluationRunResponse(
                evaluation_id=run.id,
                status=run.status
            )
        finally:
            lock_mgr.release(run_id)
    else:
        # Run asynchronously in background task
        run = EvaluationRun(
            id=run_id,
            name=payload.name,
            user_id=current_user.id,
            status="pending",
            dataset_size=len(payload.dataset) if payload.dataset else 0,
            started_at=datetime.now(timezone.utc)
        )
        db.add(run)
        db.commit()

        background_tasks.add_task(_run_eval_background, run_id, payload.model_dump())
        return EvaluationRunResponse(
            evaluation_id=run.id,
            status="started"
        )


@router.get("/{evaluation_id}", response_model=EvaluationStatusResponse)
def get_evaluation_status(
    evaluation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve execution status and progress of an evaluation run belonging to current user."""
    run = db.query(EvaluationRun).filter(EvaluationRun.id == evaluation_id).first()
    if not run or (run.user_id is not None and run.user_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation run with ID '{evaluation_id}' not found."
        )

    return EvaluationStatusResponse(
        evaluation_id=run.id,
        status=run.status,
        dataset_size=run.dataset_size,
        started_at=run.started_at,
        completed_at=run.completed_at,
        failure_reason=run.error_message
    )


@router.get("/{evaluation_id}/results", response_model=EvaluationResultsResponse)
def get_evaluation_results(
    evaluation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve detailed results, metric summary, and failure analyses for a completed evaluation run."""
    run = db.query(EvaluationRun).filter(EvaluationRun.id == evaluation_id).first()
    if not run or (run.user_id is not None and run.user_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation run with ID '{evaluation_id}' not found."
        )

    if run.status == "failed":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Evaluation run failed: {run.error_message or 'Unknown error'}"
        )

    if run.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Evaluation run is still in progress (status: '{run.status}'). Partial results are not returned."
        )

    engine = get_evaluation_engine()
    return engine.get_results_response(run)
