"""VideoGenService unit tests. RunPod API calls and DB are mocked."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.video_gen import VideoGenCreate
from app.services.video_gen_service import VideoGenService


def _make_mock_db():
    """DB 세션 mock — commit/refresh는 no-op."""
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()
    return db


def _make_mock_job(**overrides):
    """VideoGeneration ORM 객체 mock."""
    job = MagicMock()
    job.id = overrides.get("id", uuid.uuid4())
    job.created_by = overrides.get("created_by", uuid.uuid4())
    job.prompt = overrides.get("prompt", "Test prompt")
    job.negative_prompt = overrides.get("negative_prompt", None)
    job.width = overrides.get("width", 768)
    job.height = overrides.get("height", 512)
    job.num_frames = overrides.get("num_frames", 25)
    job.frame_rate = overrides.get("frame_rate", 24)
    job.num_inference_steps = overrides.get("num_inference_steps", 40)
    job.guidance_scale = overrides.get("guidance_scale", 3.0)
    job.seed = overrides.get("seed", None)
    job.model_variant = overrides.get("model_variant", "dev")
    job.keyframes = overrides.get("keyframes", [])
    job.status = overrides.get("status", "pending")
    job.runpod_job_id = overrides.get("runpod_job_id", None)
    job.result_video_url = overrides.get("result_video_url", None)
    job.result_metadata = overrides.get("result_metadata", None)
    job.error_message = overrides.get("error_message", None)
    job.started_at = overrides.get("started_at", None)
    job.completed_at = overrides.get("completed_at", None)
    return job


@pytest.mark.asyncio
async def test_create_job_submits_to_runpod():
    db = _make_mock_db()
    svc = VideoGenService(db)
    data = VideoGenCreate(prompt="Test prompt", width=768, height=512, num_frames=25)

    user_id = uuid.uuid4()

    # VideoGeneration 생성 후 refresh 시 mock job 반환
    mock_job = _make_mock_job(prompt="Test prompt", width=768, num_frames=25)

    with patch("app.services.video_gen_service.VideoGeneration", return_value=mock_job):
        with patch.object(svc, "_submit_to_runpod", new_callable=AsyncMock, return_value="rp-123"):
            job = await svc.create_job(user_id, data)

    assert job.status == "submitted"
    assert job.runpod_job_id == "rp-123"


@pytest.mark.asyncio
async def test_create_job_marks_failed_on_runpod_error():
    db = _make_mock_db()
    svc = VideoGenService(db)
    data = VideoGenCreate(prompt="Fail test", num_frames=25)
    user_id = uuid.uuid4()
    mock_job = _make_mock_job(prompt="Fail test")

    with patch("app.services.video_gen_service.VideoGeneration", return_value=mock_job):
        with patch.object(svc, "_submit_to_runpod", new_callable=AsyncMock, side_effect=Exception("Connection refused")):
            job = await svc.create_job(user_id, data)

    assert job.status == "failed"
    assert "Connection refused" in job.error_message


@pytest.mark.asyncio
async def test_create_job_stores_keyframes():
    db = _make_mock_db()
    svc = VideoGenService(db)
    data = VideoGenCreate(
        prompt="Keyframe test",
        num_frames=25,
        keyframes=[
            {"image_url": "/uploads/a.png", "frame_index": 0, "strength": 1.0},
            {"image_url": "/uploads/b.png", "frame_index": 24, "strength": 0.8},
        ],
    )
    user_id = uuid.uuid4()
    mock_job = _make_mock_job(
        prompt="Keyframe test",
        keyframes=[
            {"image_url": "/uploads/a.png", "frame_index": 0, "strength": 1.0},
            {"image_url": "/uploads/b.png", "frame_index": 24, "strength": 0.8},
        ],
    )

    with patch("app.services.video_gen_service.VideoGeneration", return_value=mock_job):
        with patch.object(svc, "_submit_to_runpod", new_callable=AsyncMock, return_value="rp-kf"):
            job = await svc.create_job(user_id, data)

    assert len(job.keyframes) == 2
    assert job.keyframes[0]["image_url"] == "/uploads/a.png"


@pytest.mark.asyncio
async def test_refresh_job_status_completed():
    db = _make_mock_db()
    svc = VideoGenService(db)

    job = _make_mock_job(status="submitted", runpod_job_id="rp-done")

    with patch.object(svc, "_check_runpod_status", new_callable=AsyncMock, return_value={
        "status": "COMPLETED",
        "output": {"video_base64": "AAAA", "metadata": {"seed": 42}},
    }):
        with patch.object(svc, "_save_result", new_callable=AsyncMock, return_value="/uploads/videos/test.mp4"):
            updated = await svc.refresh_job_status(job)

    assert updated.status == "completed"
    assert updated.result_video_url == "/uploads/videos/test.mp4"
    assert updated.completed_at is not None


@pytest.mark.asyncio
async def test_refresh_job_status_failed():
    db = _make_mock_db()
    svc = VideoGenService(db)

    job = _make_mock_job(status="submitted", runpod_job_id="rp-fail")

    with patch.object(svc, "_check_runpod_status", new_callable=AsyncMock, return_value={
        "status": "FAILED",
        "error": "Out of VRAM",
    }):
        updated = await svc.refresh_job_status(job)

    assert updated.status == "failed"
    assert "Out of VRAM" in updated.error_message


@pytest.mark.asyncio
async def test_refresh_job_status_processing():
    db = _make_mock_db()
    svc = VideoGenService(db)

    job = _make_mock_job(status="submitted", runpod_job_id="rp-proc")

    with patch.object(svc, "_check_runpod_status", new_callable=AsyncMock, return_value={
        "status": "IN_PROGRESS",
    }):
        updated = await svc.refresh_job_status(job)

    assert updated.status == "processing"


@pytest.mark.asyncio
async def test_refresh_skips_terminal_status():
    db = _make_mock_db()
    svc = VideoGenService(db)

    job = _make_mock_job(status="completed", runpod_job_id="rp-term")

    updated = await svc.refresh_job_status(job)
    assert updated.status == "completed"


def test_num_frames_validation():
    """num_frames must be 8n+1."""
    with pytest.raises(Exception):
        VideoGenCreate(prompt="test", num_frames=30)
    with pytest.raises(Exception):
        VideoGenCreate(prompt="test", num_frames=10)
    # Valid values
    VideoGenCreate(prompt="test", num_frames=9)
    VideoGenCreate(prompt="test", num_frames=25)
    VideoGenCreate(prompt="test", num_frames=97)
    VideoGenCreate(prompt="test", num_frames=257)


def test_model_variant_validation():
    """model_variant must be dev or distilled."""
    with pytest.raises(Exception):
        VideoGenCreate(prompt="test", num_frames=25, model_variant="ultra")
    with pytest.raises(Exception):
        VideoGenCreate(prompt="test", num_frames=25, model_variant="fp8")
    VideoGenCreate(prompt="test", num_frames=25, model_variant="dev")
    VideoGenCreate(prompt="test", num_frames=25, model_variant="distilled")


def test_keyframes_max_5():
    """keyframes must have at most 5 entries."""
    with pytest.raises(Exception):
        VideoGenCreate(
            prompt="test",
            num_frames=25,
            keyframes=[{"image_url": f"/img{i}.png", "frame_index": i, "strength": 0.8} for i in range(6)],
        )
