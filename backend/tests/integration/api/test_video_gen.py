import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from tests.conftest import auth_header

VIDEO_GEN_DATA = {
    "prompt": "A beautiful sunset over the ocean, cinematic quality",
    "width": 768,
    "height": 512,
    "num_frames": 25,
    "frame_rate": 24,
    "num_inference_steps": 40,
    "guidance_scale": 3.0,
    "model_variant": "dev",
}


@pytest.mark.asyncio
async def test_create_video_gen_job_returns_201(client: AsyncClient, test_admin):
    """admin이 비디오 생성 작업을 제출하면 201 반환."""
    headers = auth_header(test_admin)
    with patch("app.services.video_gen_service.VideoGenService._submit_to_runpod", new_callable=AsyncMock, return_value="rp-job-123"):
        response = await client.post("/api/admin/video-gen", json=VIDEO_GEN_DATA, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["prompt"] == VIDEO_GEN_DATA["prompt"]
    assert data["status"] in ("submitted", "pending")
    assert data["width"] == 768


@pytest.mark.asyncio
async def test_create_video_gen_job_forbidden_for_user(client: AsyncClient, test_user):
    """일반 사용자는 비디오 생성 불가."""
    headers = auth_header(test_user)
    response = await client.post("/api/admin/video-gen", json=VIDEO_GEN_DATA, headers=headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_video_gen_invalid_num_frames(client: AsyncClient, test_admin):
    """num_frames가 8n+1이 아니면 422."""
    headers = auth_header(test_admin)
    data = {**VIDEO_GEN_DATA, "num_frames": 30}
    response = await client.post("/api/admin/video-gen", json=data, headers=headers)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_video_gen_invalid_variant(client: AsyncClient, test_admin):
    """잘못된 model_variant면 422."""
    headers = auth_header(test_admin)
    data = {**VIDEO_GEN_DATA, "model_variant": "ultra"}
    response = await client.post("/api/admin/video-gen", json=data, headers=headers)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_video_gen_jobs(client: AsyncClient, test_admin):
    """작업 목록 조회."""
    headers = auth_header(test_admin)
    with patch("app.services.video_gen_service.VideoGenService._submit_to_runpod", new_callable=AsyncMock, return_value="rp-job-456"):
        await client.post("/api/admin/video-gen", json=VIDEO_GEN_DATA, headers=headers)

    response = await client.get("/api/admin/video-gen", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_get_video_gen_job_detail(client: AsyncClient, test_admin):
    """개별 작업 상태 조회."""
    headers = auth_header(test_admin)
    with patch("app.services.video_gen_service.VideoGenService._submit_to_runpod", new_callable=AsyncMock, return_value="rp-job-789"):
        create_resp = await client.post("/api/admin/video-gen", json=VIDEO_GEN_DATA, headers=headers)
    job_id = create_resp.json()["id"]

    with patch("app.services.video_gen_service.VideoGenService._check_runpod_status", new_callable=AsyncMock, return_value={"status": "IN_QUEUE"}):
        response = await client.get(f"/api/admin/video-gen/{job_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == job_id


@pytest.mark.asyncio
async def test_get_video_gen_job_not_found(client: AsyncClient, test_admin):
    headers = auth_header(test_admin)
    response = await client.get(f"/api/admin/video-gen/{uuid.uuid4()}", headers=headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cancel_video_gen_job(client: AsyncClient, test_admin):
    """진행 중인 작업 취소."""
    headers = auth_header(test_admin)
    with patch("app.services.video_gen_service.VideoGenService._submit_to_runpod", new_callable=AsyncMock, return_value="rp-cancel-test"):
        create_resp = await client.post("/api/admin/video-gen", json=VIDEO_GEN_DATA, headers=headers)
    job_id = create_resp.json()["id"]

    with patch("app.services.video_gen_service.VideoGenService._cancel_runpod_job", new_callable=AsyncMock):
        response = await client.post(f"/api/admin/video-gen/{job_id}/cancel", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_list_video_gen_forbidden_for_user(client: AsyncClient, test_user):
    headers = auth_header(test_user)
    response = await client.get("/api/admin/video-gen", headers=headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_video_gen_with_keyframes(client: AsyncClient, test_admin):
    """키프레임 이미지 포함 작업 생성."""
    headers = auth_header(test_admin)
    data = {
        **VIDEO_GEN_DATA,
        "keyframes": [
            {"image_url": "/uploads/a.png", "frame_index": 0, "strength": 1.0},
            {"image_url": "/uploads/b.png", "frame_index": 24, "strength": 0.8},
        ],
    }
    with patch("app.services.video_gen_service.VideoGenService._submit_to_runpod", new_callable=AsyncMock, return_value="rp-kf"):
        response = await client.post("/api/admin/video-gen", json=data, headers=headers)
    assert response.status_code == 201
    assert len(response.json()["keyframes"]) == 2
