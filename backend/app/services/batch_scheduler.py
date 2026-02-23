"""배치 파이프라인 스케줄러.

관리자가 수동 트리거하거나, 주기적으로 미처리 에피소드를 자동 처리.
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from enum import Enum

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class BatchJob:
    """배치 작업 상태 추적."""

    def __init__(self, job_id: str, webtoon_id: uuid.UUID, job_type: str = "full"):
        self.job_id = job_id
        self.webtoon_id = webtoon_id
        self.job_type = job_type  # "full", "emotions_only", "embeddings_only"
        self.status = JobStatus.PENDING
        self.created_at = datetime.now(UTC)
        self.started_at: datetime | None = None
        self.completed_at: datetime | None = None
        self.result: dict | None = None
        self.error: str | None = None


class BatchScheduler:
    """인메모리 배치 작업 스케줄러. 프로토타입: 큐잉 + asyncio.create_task로 비동기 실행."""

    _instance = None

    def __init__(self):
        self._jobs: dict[str, BatchJob] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None
        self._running = False

    @classmethod
    def get_instance(cls) -> "BatchScheduler":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def start(self):
        """워커 태스크 시작 (lifespan에서 호출)."""
        if not self._running:
            self._running = True
            self._worker_task = asyncio.create_task(self._worker_loop())
            logger.info("BatchScheduler worker started")

    def stop(self):
        """워커 태스크 중지."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            logger.info("BatchScheduler worker stopped")

    async def submit_job(self, webtoon_id: uuid.UUID, job_type: str = "full") -> BatchJob:
        """배치 작업 제출."""
        job_id = f"batch-{uuid.uuid4().hex[:12]}"
        job = BatchJob(job_id=job_id, webtoon_id=webtoon_id, job_type=job_type)
        self._jobs[job_id] = job
        await self._queue.put(job_id)
        logger.info("Job %s submitted for webtoon %s (type=%s)", job_id, webtoon_id, job_type)
        return job

    def get_job(self, job_id: str) -> BatchJob | None:
        return self._jobs.get(job_id)

    def list_jobs(self, limit: int = 20) -> list[BatchJob]:
        jobs = sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]

    async def _worker_loop(self):
        """작업 큐를 소비하는 워커 루프."""
        while self._running:
            try:
                job_id = await asyncio.wait_for(self._queue.get(), timeout=5.0)
                await self._execute_job(job_id)
            except TimeoutError:
                continue  # 큐가 비어있으면 다시 대기
            except asyncio.CancelledError:
                break
            except Exception:
                logger.error("Worker loop error", exc_info=True)

    async def _execute_job(self, job_id: str):
        """단일 작업 실행."""
        job = self._jobs.get(job_id)
        if not job:
            return

        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(UTC)

        try:
            from app.core.database import async_session
            from app.pipeline.batch import BatchPipeline

            async with async_session() as db:
                pipeline = BatchPipeline(db)
                result = await pipeline.process_webtoon(
                    job.webtoon_id,
                    skip_emotions=(job.job_type == "embeddings_only"),
                    skip_embeddings=(job.job_type == "emotions_only"),
                )

            job.status = JobStatus.COMPLETED
            job.result = result
            logger.info("Job %s completed: %s", job_id, result)
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
            logger.error("Job %s failed: %s", job_id, e, exc_info=True)
        finally:
            job.completed_at = datetime.now(UTC)
