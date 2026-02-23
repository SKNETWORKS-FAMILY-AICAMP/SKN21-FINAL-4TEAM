import uuid
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.core.config import settings
from app.core.deps import require_admin, require_superadmin
from app.models.user import User
from app.services.batch_scheduler import BatchScheduler, JobStatus

router = APIRouter()


class SystemConfigResponse(BaseModel):
    app_env: str
    pipeline_device: str
    pipeline_lazy_load: bool
    emotion_model: str
    embedding_model: str
    reranker_model: str
    runpod_endpoint_configured: bool
    openai_configured: bool
    anthropic_configured: bool
    google_configured: bool
    langfuse_configured: bool
    sentry_configured: bool
    cors_origins: list[str]


@router.get("/config", response_model=SystemConfigResponse)
async def get_system_config(admin: User = Depends(require_superadmin)):
    """시스템 설정 조회. 민감 정보(API 키)는 노출하지 않고 설정 여부만 표시."""
    return SystemConfigResponse(
        app_env=settings.app_env,
        pipeline_device=settings.pipeline_device or "auto",
        pipeline_lazy_load=settings.pipeline_lazy_load,
        emotion_model=settings.emotion_model,
        embedding_model=settings.embedding_model,
        reranker_model=settings.reranker_model,
        runpod_endpoint_configured=bool(settings.runpod_api_key and settings.runpod_endpoint_id),
        openai_configured=bool(settings.openai_api_key),
        anthropic_configured=bool(settings.anthropic_api_key),
        google_configured=bool(settings.google_api_key),
        langfuse_configured=bool(settings.langfuse_public_key and settings.langfuse_secret_key),
        sentry_configured=bool(settings.sentry_dsn),
        cors_origins=settings.cors_origins,
    )


class CORSUpdateRequest(BaseModel):
    cors_origins: list[str]


@router.put("/config")
async def update_system_config(
    admin: User = Depends(require_superadmin),
    body: CORSUpdateRequest = Body(...),
):
    """시스템 설정 변경 (런타임 변경 가능 항목만).

    프로토타입 단계에서는 CORS origins만 런타임 변경 가능.
    나머지 설정은 환경 변수 + 재시작으로 관리.
    """
    # 런타임 설정 변경은 프로토타입에서 제한적으로 지원
    # CORS는 미들웨어 재설정이 필요하므로 재시작 안내
    return {
        "message": "Configuration noted. Restart required for CORS changes to take effect.",
        "updated": {
            "cors_origins": body.cors_origins,
        },
        "restart_required": True,
    }


# ── 배치 작업 관리 ──


class BatchJobRequest(BaseModel):
    webtoon_id: uuid.UUID
    job_type: str = "full"  # "full" | "emotions_only" | "embeddings_only"


class BatchJobResponse(BaseModel):
    job_id: str
    webtoon_id: uuid.UUID
    job_type: str
    status: JobStatus
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: dict | None = None
    error: str | None = None


VALID_JOB_TYPES = {"full", "emotions_only", "embeddings_only"}


@router.post("/batch/jobs", response_model=BatchJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_batch_job(
    body: BatchJobRequest = Body(...),
    admin: User = Depends(require_superadmin),
):
    """배치 파이프라인 작업 제출. 웹툰 ID와 작업 유형을 지정."""
    if body.job_type not in VALID_JOB_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid job_type. Must be one of: {', '.join(sorted(VALID_JOB_TYPES))}",
        )

    scheduler = BatchScheduler.get_instance()
    job = await scheduler.submit_job(webtoon_id=body.webtoon_id, job_type=body.job_type)
    return _job_to_response(job)


@router.get("/batch/jobs", response_model=list[BatchJobResponse])
async def list_batch_jobs(
    limit: int = Query(default=20, ge=1, le=100),
    admin: User = Depends(require_admin),
):
    """최근 배치 작업 목록 조회."""
    scheduler = BatchScheduler.get_instance()
    jobs = scheduler.list_jobs(limit=limit)
    return [_job_to_response(j) for j in jobs]


@router.get("/batch/jobs/{job_id}", response_model=BatchJobResponse)
async def get_batch_job(
    job_id: str,
    admin: User = Depends(require_admin),
):
    """배치 작업 상세 조회."""
    scheduler = BatchScheduler.get_instance()
    job = scheduler.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return _job_to_response(job)


def _job_to_response(job) -> BatchJobResponse:
    return BatchJobResponse(
        job_id=job.job_id,
        webtoon_id=job.webtoon_id,
        job_type=job.job_type,
        status=job.status,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        result=job.result,
        error=job.error,
    )
