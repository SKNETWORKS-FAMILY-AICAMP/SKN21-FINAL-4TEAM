"""BatchScheduler 단위 테스트."""

import uuid
from datetime import datetime, timezone

import pytest

from app.services.batch_scheduler import BatchJob, BatchScheduler, JobStatus


class TestJobStatus:
    """JobStatus enum 값 테스트."""

    def test_pending_value(self):
        assert JobStatus.PENDING == "pending"

    def test_running_value(self):
        assert JobStatus.RUNNING == "running"

    def test_completed_value(self):
        assert JobStatus.COMPLETED == "completed"

    def test_failed_value(self):
        assert JobStatus.FAILED == "failed"

    def test_is_str_subclass(self):
        """str(Enum) 변환 시 문자열 값을 반환해야 한다."""
        assert isinstance(JobStatus.PENDING, str)


class TestBatchJob:
    """BatchJob 초기 상태 테스트."""

    def test_initial_status_is_pending(self):
        webtoon_id = uuid.uuid4()
        job = BatchJob(job_id="test-001", webtoon_id=webtoon_id)
        assert job.status == JobStatus.PENDING

    def test_initial_fields(self):
        webtoon_id = uuid.uuid4()
        job = BatchJob(job_id="test-002", webtoon_id=webtoon_id, job_type="emotions_only")

        assert job.job_id == "test-002"
        assert job.webtoon_id == webtoon_id
        assert job.job_type == "emotions_only"
        assert job.started_at is None
        assert job.completed_at is None
        assert job.result is None
        assert job.error is None

    def test_created_at_is_utc(self):
        job = BatchJob(job_id="test-003", webtoon_id=uuid.uuid4())
        assert job.created_at.tzinfo is not None
        assert job.created_at.tzinfo == timezone.utc

    def test_default_job_type_is_full(self):
        job = BatchJob(job_id="test-004", webtoon_id=uuid.uuid4())
        assert job.job_type == "full"


class TestBatchScheduler:
    """BatchScheduler 로직 테스트 (DB 의존 없음)."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """각 테스트 전에 싱글톤 인스턴스를 초기화."""
        BatchScheduler._instance = None
        yield
        BatchScheduler._instance = None

    def test_get_instance_returns_singleton(self):
        s1 = BatchScheduler.get_instance()
        s2 = BatchScheduler.get_instance()
        assert s1 is s2

    @pytest.mark.asyncio
    async def test_submit_job_creates_pending_job(self):
        scheduler = BatchScheduler()
        webtoon_id = uuid.uuid4()

        job = await scheduler.submit_job(webtoon_id=webtoon_id, job_type="full")

        assert job.status == JobStatus.PENDING
        assert job.webtoon_id == webtoon_id
        assert job.job_type == "full"
        assert job.job_id.startswith("batch-")

    @pytest.mark.asyncio
    async def test_submit_job_adds_to_internal_store(self):
        scheduler = BatchScheduler()
        webtoon_id = uuid.uuid4()

        job = await scheduler.submit_job(webtoon_id=webtoon_id)

        assert scheduler.get_job(job.job_id) is job

    @pytest.mark.asyncio
    async def test_get_job_returns_correct_job(self):
        scheduler = BatchScheduler()
        wid1, wid2 = uuid.uuid4(), uuid.uuid4()

        job1 = await scheduler.submit_job(webtoon_id=wid1)
        job2 = await scheduler.submit_job(webtoon_id=wid2)

        assert scheduler.get_job(job1.job_id) is job1
        assert scheduler.get_job(job2.job_id) is job2

    def test_get_job_returns_none_for_unknown_id(self):
        scheduler = BatchScheduler()
        assert scheduler.get_job("nonexistent-id") is None

    @pytest.mark.asyncio
    async def test_list_jobs_returns_sorted_by_creation_desc(self):
        scheduler = BatchScheduler()
        jobs = []
        for _ in range(5):
            job = await scheduler.submit_job(webtoon_id=uuid.uuid4())
            jobs.append(job)

        listed = scheduler.list_jobs()

        # 최신 작업이 먼저 와야 한다
        assert len(listed) == 5
        for i in range(len(listed) - 1):
            assert listed[i].created_at >= listed[i + 1].created_at

    @pytest.mark.asyncio
    async def test_list_jobs_respects_limit(self):
        scheduler = BatchScheduler()
        for _ in range(10):
            await scheduler.submit_job(webtoon_id=uuid.uuid4())

        listed = scheduler.list_jobs(limit=3)
        assert len(listed) == 3

    @pytest.mark.asyncio
    async def test_list_jobs_empty_scheduler(self):
        scheduler = BatchScheduler()
        listed = scheduler.list_jobs()
        assert listed == []

    @pytest.mark.asyncio
    async def test_job_status_transitions(self):
        """작업 상태가 PENDING -> RUNNING -> COMPLETED 순서로 전이된다."""
        job = BatchJob(job_id="test-transition", webtoon_id=uuid.uuid4())
        assert job.status == JobStatus.PENDING

        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        assert job.status == JobStatus.RUNNING
        assert job.started_at is not None

        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.now(timezone.utc)
        job.result = {"processed": 5, "errors": 0}
        assert job.status == JobStatus.COMPLETED
        assert job.completed_at is not None
        assert job.result == {"processed": 5, "errors": 0}

    @pytest.mark.asyncio
    async def test_job_status_transition_to_failed(self):
        """작업 실패 시 PENDING -> RUNNING -> FAILED 전이."""
        job = BatchJob(job_id="test-fail", webtoon_id=uuid.uuid4())
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)

        job.status = JobStatus.FAILED
        job.error = "Connection refused"
        job.completed_at = datetime.now(timezone.utc)

        assert job.status == JobStatus.FAILED
        assert job.error == "Connection refused"
        assert job.completed_at is not None

    @pytest.mark.asyncio
    async def test_submit_job_with_different_types(self):
        scheduler = BatchScheduler()
        webtoon_id = uuid.uuid4()

        job_full = await scheduler.submit_job(webtoon_id=webtoon_id, job_type="full")
        job_emo = await scheduler.submit_job(webtoon_id=webtoon_id, job_type="emotions_only")
        job_emb = await scheduler.submit_job(webtoon_id=webtoon_id, job_type="embeddings_only")

        assert job_full.job_type == "full"
        assert job_emo.job_type == "emotions_only"
        assert job_emb.job_type == "embeddings_only"

    @pytest.mark.asyncio
    async def test_submit_job_generates_unique_ids(self):
        scheduler = BatchScheduler()
        webtoon_id = uuid.uuid4()

        job1 = await scheduler.submit_job(webtoon_id=webtoon_id)
        job2 = await scheduler.submit_job(webtoon_id=webtoon_id)

        assert job1.job_id != job2.job_id
