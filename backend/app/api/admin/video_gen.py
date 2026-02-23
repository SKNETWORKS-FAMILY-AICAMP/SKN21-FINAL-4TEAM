import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_admin
from app.models.user import User
from app.schemas.video_gen import VideoGenCreate, VideoGenListResponse, VideoGenResponse
from app.services.video_gen_service import VideoGenService

router = APIRouter()


@router.get("", response_model=VideoGenListResponse)
async def list_video_gen_jobs(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """비디오 생성 작업 목록."""
    svc = VideoGenService(db)
    return await svc.list_jobs(skip=skip, limit=limit)


@router.post("", response_model=VideoGenResponse, status_code=status.HTTP_201_CREATED)
async def create_video_gen_job(
    data: VideoGenCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """비디오 생성 작업 제출. RunPod에 비동기 전송."""
    svc = VideoGenService(db)
    return await svc.create_job(user_id=admin.id, data=data)


@router.get("/{job_id}", response_model=VideoGenResponse)
async def get_video_gen_job(
    job_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """비디오 생성 작업 상태 조회. 미완료 시 RunPod 상태 갱신."""
    svc = VideoGenService(db)
    job = await svc.get_job(job_id)
    job = await svc.refresh_job_status(job)
    return job


@router.post("/{job_id}/cancel", response_model=VideoGenResponse)
async def cancel_video_gen_job(
    job_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """비디오 생성 작업 취소."""
    svc = VideoGenService(db)
    return await svc.cancel_job(job_id)
