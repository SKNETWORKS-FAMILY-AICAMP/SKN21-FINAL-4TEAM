"""이미지 생성 API 엔드포인트.

사용자가 프롬프트 기반으로 AI 이미지를 생성할 수 있다.
"""

from fastapi import APIRouter, Depends

from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.image_gen import ImageGenCreate, ImageGenResponse, ImageStyleResponse
from app.services.image_gen_service import ImageGenService

router = APIRouter()


@router.post("/generate", response_model=ImageGenResponse)
async def generate_image(
    data: ImageGenCreate,
    user: User = Depends(get_current_user),
):
    """프롬프트 기반 이미지 생성."""
    svc = ImageGenService()
    result = await svc.generate(
        prompt=data.prompt,
        style=data.style,
        width=data.width,
        height=data.height,
        negative_prompt=data.negative_prompt,
        seed=data.seed,
    )
    return result


@router.get("/styles", response_model=ImageStyleResponse)
async def list_styles(
    user: User = Depends(get_current_user),
):
    """사용 가능한 이미지 스타일 목록."""
    svc = ImageGenService()
    return await svc.list_styles()
