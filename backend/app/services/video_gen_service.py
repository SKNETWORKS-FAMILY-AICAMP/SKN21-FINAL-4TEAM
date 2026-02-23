"""비디오 생성 서비스.

LTX-Video 13B RunPod Serverless 워커에 작업을 제출하고,
상태를 추적하며, 완료된 결과를 로컬에 저장한다.
"""

import base64
import logging
import os
import uuid
from datetime import UTC, datetime

import anyio
import httpx
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.video_generation import VideoGeneration
from app.schemas.video_gen import VideoGenCreate

logger = logging.getLogger(__name__)

_RUNPOD_BASE = "https://api.runpod.ai/v2"


class VideoGenService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_job(self, user_id: uuid.UUID, data: VideoGenCreate) -> VideoGeneration:
        """비디오 생성 작업 생성 및 RunPod 제출."""
        job = VideoGeneration(
            created_by=user_id,
            prompt=data.prompt,
            negative_prompt=data.negative_prompt,
            width=data.width,
            height=data.height,
            num_frames=data.num_frames,
            frame_rate=data.frame_rate,
            num_inference_steps=data.num_inference_steps,
            guidance_scale=data.guidance_scale,
            seed=data.seed,
            model_variant=data.model_variant,
            keyframes=[kf.model_dump() for kf in data.keyframes],
            status="pending",
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)

        try:
            runpod_job_id = await self._submit_to_runpod(job)
            job.status = "submitted"
            job.runpod_job_id = runpod_job_id
            job.started_at = datetime.now(UTC)
        except Exception as exc:
            logger.error("RunPod submission failed for job %s: %s", job.id, exc)
            job.status = "failed"
            job.error_message = f"RunPod submission failed: {exc}"

        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def get_job(self, job_id: uuid.UUID) -> VideoGeneration:
        result = await self.db.execute(select(VideoGeneration).where(VideoGeneration.id == job_id))
        job = result.scalar_one_or_none()
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video generation job not found")
        return job

    async def list_jobs(self, skip: int = 0, limit: int = 20) -> dict:
        total = (await self.db.execute(select(func.count()).select_from(VideoGeneration))).scalar()
        result = await self.db.execute(
            select(VideoGeneration).order_by(VideoGeneration.created_at.desc()).offset(skip).limit(limit)
        )
        return {"items": list(result.scalars().all()), "total": total}

    async def refresh_job_status(self, job: VideoGeneration) -> VideoGeneration:
        """RunPod에서 최신 상태를 가져와 DB를 갱신."""
        if job.status in ("completed", "failed", "cancelled"):
            return job
        if not job.runpod_job_id:
            return job

        try:
            rp_status = await self._check_runpod_status(job.runpod_job_id)
        except Exception as exc:
            logger.error("RunPod status check failed for %s: %s", job.runpod_job_id, exc)
            return job

        rp_state = rp_status.get("status", "").upper()

        if rp_state == "COMPLETED":
            output = rp_status.get("output", {})
            video_url = await self._save_result(job.id, output)
            job.status = "completed"
            job.result_video_url = video_url
            job.result_metadata = output.get("metadata")
            job.completed_at = datetime.now(UTC)
        elif rp_state == "FAILED":
            job.status = "failed"
            job.error_message = rp_status.get("error", "Unknown RunPod error")
            job.completed_at = datetime.now(UTC)
        elif rp_state == "IN_PROGRESS":
            job.status = "processing"

        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def cancel_job(self, job_id: uuid.UUID) -> VideoGeneration:
        job = await self.get_job(job_id)
        if job.status in ("completed", "failed", "cancelled"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel job in '{job.status}' status",
            )
        if job.runpod_job_id:
            await self._cancel_runpod_job(job.runpod_job_id)
        job.status = "cancelled"
        job.completed_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(job)
        return job

    # ── RunPod API ──

    async def _submit_to_runpod(self, job: VideoGeneration) -> str:
        endpoint_id = settings.runpod_ltx_endpoint_id
        if not endpoint_id:
            raise ValueError("RUNPOD_LTX_ENDPOINT_ID is not configured")

        payload = {
            "input": {
                "prompt": job.prompt,
                "negative_prompt": job.negative_prompt or "",
                "width": job.width,
                "height": job.height,
                "num_frames": job.num_frames,
                "frame_rate": job.frame_rate,
                "num_inference_steps": job.num_inference_steps,
                "guidance_scale": float(job.guidance_scale),
                "seed": job.seed,
                "model_variant": job.model_variant,
                "keyframes": job.keyframes or [],
            }
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{_RUNPOD_BASE}/{endpoint_id}/run",
                headers={
                    "Authorization": f"Bearer {settings.runpod_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["id"]

    async def _check_runpod_status(self, runpod_job_id: str) -> dict:
        endpoint_id = settings.runpod_ltx_endpoint_id
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{_RUNPOD_BASE}/{endpoint_id}/status/{runpod_job_id}",
                headers={"Authorization": f"Bearer {settings.runpod_api_key}"},
            )
            response.raise_for_status()
            return response.json()

    async def _cancel_runpod_job(self, runpod_job_id: str) -> None:
        endpoint_id = settings.runpod_ltx_endpoint_id
        async with httpx.AsyncClient(timeout=15.0) as client:
            await client.post(
                f"{_RUNPOD_BASE}/{endpoint_id}/cancel/{runpod_job_id}",
                headers={"Authorization": f"Bearer {settings.runpod_api_key}"},
            )

    async def _save_result(self, job_id: uuid.UUID, output: dict) -> str:
        """RunPod 출력에서 비디오를 추출하여 로컬에 저장."""
        video_dir = os.path.join(settings.upload_dir, "videos")
        os.makedirs(video_dir, exist_ok=True)

        filename = f"{uuid.uuid4().hex}.mp4"
        filepath = os.path.join(video_dir, filename)

        if "video_base64" in output:
            video_bytes = base64.b64decode(output["video_base64"])
            await anyio.Path(filepath).write_bytes(video_bytes)
        elif "video_url" in output:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.get(output["video_url"])
                resp.raise_for_status()
                await anyio.Path(filepath).write_bytes(resp.content)
        else:
            raise ValueError("RunPod output contains neither video_base64 nor video_url")

        return f"/uploads/videos/{filename}"
