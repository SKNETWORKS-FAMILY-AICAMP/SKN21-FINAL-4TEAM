# RunPod Serverless LTX-Video 13B 세팅 가이드

> GPU: A40 48GB / 과금: 초 단위 (Serverless) / 예상 월 비용: ~$16~24

---

## 0. 모델 정보

| 항목 | 값 |
|---|---|
| 모델 | LTX-Video 13B (v0.9.7) |
| 아키텍처 | DiT (13B transformer) + T5-XXL (text encoder) + VAE |
| HuggingFace 레포 | `Lightricks/LTX-Video-0.9.7-dev` / `Lightricks/LTX-Video-0.9.7-distilled` |
| 레포 크기 | **~48 GB** (변형당, 별도 레포) |
| VRAM 요구 | ~48 GB (bf16, CPU offload 사용) |
| 형식 | diffusers (safetensors only) |

### 다운로드 구성 (dev 기준, ~48 GB)

```
Lightricks/LTX-Video-0.9.7-dev/
├── model_index.json                              ~0.4 KB
├── transformer/
│   ├── config.json                               ~0.5 KB
│   ├── diffusion_pytorch_model-00001~00006.safetensors  26.1 GB
│   └── diffusion_pytorch_model.safetensors.index.json
├── text_encoder/
│   ├── config.json                               ~0.8 KB
│   ├── model-00001~00004.safetensors             19.0 GB
│   └── model.safetensors.index.json
├── vae/
│   ├── config.json
│   └── diffusion_pytorch_model.safetensors       2.49 GB
├── tokenizer/
│   ├── spiece.model                              ~792 KB
│   └── tokenizer_config.json 등
└── scheduler/
    └── scheduler_config.json                     ~0.5 KB
```

### 200GB 사고 방지

핸들러에서 `snapshot_download`를 `allow_patterns` + `ignore_patterns`로 호출하여 **필요한 파일만** 다운로드합니다:

```python
# 허용 (이것만 다운로드)
allow_patterns = [
    "model_index.json",
    "transformer/*.json", "transformer/*.safetensors",
    "text_encoder/*.json", "text_encoder/*.safetensors",
    "vae/*.json", "vae/*.safetensors",
    "tokenizer/*", "scheduler/*",
]

# 차단 (절대 다운로드 안 함)
ignore_patterns = [
    "*.bin", "*.ckpt", "*.pt",    # 중복 포맷
    "*.mp4", "*.png", "*.jpg",    # 미디어
    "model-*",                     # transformers 형식 중복 웨이트
]
```

> `Lightricks/LTX-Video` (254GB 메가 레포)나 `Lightricks/LTX-2` (314GB)가 아닌
> **별도 diffusers 레포** (`LTX-Video-0.9.7-dev`, 48GB)를 사용하므로 안전합니다.

---

## 1. 사전 준비

| 항목 | 필요 여부 | 비고 |
|---|---|---|
| Docker Hub 또는 GHCR 계정 | 필수 | Docker 이미지 호스팅 |
| RunPod 계정 | 필수 | https://www.runpod.io |
| RunPod API Key | 필수 | Settings → API Keys |
| HuggingFace 토큰 | 선택 | gated 모델 접근 시 필요 |
| Docker 설치 | 필수 | 이미지 빌드/푸시용 |

---

## 2. Network Volume 생성

RunPod 대시보드 → `Storage` → `Network Volumes` → `Create Volume`

| 항목 | 값 |
|---|---|
| Name | `ltx-model-cache` |
| Region | **Serverless 워커와 같은 리전** (필수!) |
| Size | `60 GB` (모델 ~48 GB + 여유) |
| 비용 | ~$0.07/GB/월 = **~$4.2/월** |

> 최초 1회 모델 다운로드 후 Volume에 영구 캐시됩니다.

---

## 3. Docker 이미지 빌드 & 푸시

프로젝트 루트 디렉토리에서 실행:

```bash
# Docker Hub 로그인
docker login

# 이미지 빌드
docker build -t <dockerhub-username>/ltx-video-worker:latest \
  -f infra/runpod/Dockerfile.ltx .

# 푸시
docker push <dockerhub-username>/ltx-video-worker:latest
```

GHCR 사용 시:

```bash
echo $GITHUB_TOKEN | docker login ghcr.io -u <github-username> --password-stdin

docker build -t ghcr.io/<github-username>/ltx-video-worker:latest \
  -f infra/runpod/Dockerfile.ltx .

docker push ghcr.io/<github-username>/ltx-video-worker:latest
```

### 관련 파일

| 파일 | 설명 |
|---|---|
| `infra/runpod/Dockerfile.ltx` | LTX-Video 13B 워커 Docker 이미지 |
| `infra/runpod/ltx_handler.py` | RunPod Serverless 핸들러 (선택적 다운로드 내장) |
| `infra/runpod/requirements-ltx.txt` | Python 의존성 |

---

## 4. RunPod Template 생성

RunPod 대시보드: `Serverless` → `Custom Templates` → `New Template`

| 항목 | 값 |
|---|---|
| Template Name | `ltx-video-13b` |
| Container Image | `<dockerhub-username>/ltx-video-worker:latest` |
| Container Disk | `20 GB` |
| Volume | `ltx-model-cache` (위에서 만든 Network Volume) |
| Volume Mount Path | `/app/hf_cache` |

### 환경변수

| Key | Value | 설명 |
|---|---|---|
| `MODEL_VARIANT` | `dev` | `dev` (고품질, 40스텝) / `distilled` (빠름, 8스텝) |
| `TORCH_DTYPE` | `bfloat16` | A40은 bf16 지원 |
| `HF_TOKEN` | `hf_xxxxx` | HuggingFace 토큰 (필요 시) |

### 모델 변형별 특성 (A40 48GB 기준)

| 변형 | 다운로드 | 추론 VRAM (offload) | 스텝 수 | 속도 | 품질 |
|---|---|---|---|---|---|
| `dev` | ~48 GB | ~26 GB (GPU) | 40 (기본) | 보통 | 최고 |
| `distilled` | ~48 GB | ~26 GB (GPU) | 8 (기본) | **5배 빠름** | 좋음 |

> CPU offload 모드: transformer / text_encoder / VAE를 순차적으로 GPU에 올려 사용.
> A40 48GB에서 안정적으로 동작합니다.

---

## 5. RunPod Endpoint 생성

`Serverless` → `Endpoints` → `New Endpoint`

| 항목 | 값 | 설명 |
|---|---|---|
| Endpoint Name | `ltx-video-13b` | 식별용 이름 |
| Template | `ltx-video-13b` | 위에서 만든 템플릿 |
| GPU | `A40 48GB` | 48GB VRAM |
| Active Workers | `0` | 유휴 시 비용 $0 |
| Max Workers | `1` | 프로토타입 기준 |
| Idle Timeout | `5초` | 빠른 스케일다운 |
| FlashBoot | `ON` | 콜드스타트 단축 |
| Execution Timeout | `600초` | 영상 생성 최대 10분 허용 |

생성 후 **Endpoint ID** 복사 (예: `abcd1234efgh`)

### 콜드스타트 시간 예상

| 상황 | 소요 시간 |
|---|---|
| 최초 실행 (모델 다운로드) | 5~10분 (1회성) |
| Volume 캐시에서 로드 | ~30초~1분 |
| FlashBoot 스냅샷 복원 | ~3-5초 |

---

## 6. 백엔드 환경변수 설정

`.env` 파일에 추가:

```env
# RunPod (기존)
RUNPOD_API_KEY=rpa_XXXXXXXXXXXXXXXXXXXXXXXX

# LTX-Video 영상 생성 전용 엔드포인트
RUNPOD_LTX_ENDPOINT_ID=abcd1234efgh
```

> RunPod API Key 발급: RunPod 대시보드 → `Settings` → `API Keys` → `Create API Key`

---

## 7. 테스트

### 7-1. RunPod API 직접 테스트

작업 제출:

```bash
curl -X POST "https://api.runpod.ai/v2/<ENDPOINT_ID>/run" \
  -H "Authorization: Bearer rpa_XXXXX" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "prompt": "A cat walking on the beach, cinematic quality, golden hour",
      "width": 768,
      "height": 512,
      "num_frames": 25,
      "frame_rate": 24,
      "num_inference_steps": 40,
      "guidance_scale": 3.0
    }
  }'
```

응답:

```json
{"id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx", "status": "IN_QUEUE"}
```

상태 확인 (폴링):

```bash
curl "https://api.runpod.ai/v2/<ENDPOINT_ID>/status/<JOB_ID>" \
  -H "Authorization: Bearer rpa_XXXXX"
```

완료 응답:

```json
{
  "id": "...",
  "status": "COMPLETED",
  "output": {
    "video_base64": "AAAAIGZ0eXBpc29t...",
    "metadata": {
      "seed": 1234567890,
      "duration": 1.04,
      "file_size": 524288,
      "num_frames": 25,
      "resolution": "768x512",
      "model_variant": "dev",
      "elapsed_seconds": 95.3
    }
  }
}
```

### 7-2. 백엔드 통합 테스트

```bash
curl -X POST "http://localhost:8000/api/admin/video-gen" \
  -H "Authorization: Bearer <admin-jwt-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A sunset over mountains, drone shot, 4K quality",
    "width": 768,
    "height": 512,
    "num_frames": 25,
    "model_variant": "dev"
  }'
```

### 7-3. 프론트엔드 테스트

1. 관리자 로그인
2. 사이드바 → `영상 생성` 클릭
3. 프롬프트 입력 → `생성 시작` 클릭
4. 작업 내역에서 상태 자동 폴링 확인 (5초 간격)
5. 완료 시 행 클릭 → 상세 모달에서 영상 미리보기 및 다운로드

---

## 8. 운영 체크리스트

```
[ ] RunPod Network Volume 생성 (60 GB, 워커와 같은 리전)
[ ] Docker Hub/GHCR에 이미지 푸시 완료
[ ] RunPod Template 생성 (환경변수 + Volume 마운트 설정)
[ ] RunPod Endpoint 생성 (A40 48GB, FlashBoot ON)
[ ] .env에 RUNPOD_API_KEY + RUNPOD_LTX_ENDPOINT_ID 설정
[ ] curl로 RunPod API 직접 테스트 → COMPLETED 확인
[ ] 관리자 페이지에서 영상 생성 → 결과 영상 다운로드 확인
[ ] Alembic 마이그레이션 적용 (alembic upgrade head)
```

---

## 9. 비용 예측

### 단가

| 항목 | 값 |
|---|---|
| A40 Serverless | ~$0.00044/s |
| Network Volume (60 GB) | ~$4.2/월 |
| 콜드스타트 | ~3-5초 (FlashBoot ON) |
| 유휴 시 | $0 (Active Workers: 0) |

### 시나리오별 월 비용

| 사용량 | 건당 시간 | 일 비용 | 월 비용 (Compute + Volume) |
|---|---|---|---|
| 하루 5건 (25f, SD) | ~2분 | ~$0.26 | **~$12** |
| 하루 10건 (25f, SD) | ~2분 | ~$0.53 | **~$20** |
| 하루 10건 (97f, SD) | ~5분 | ~$1.32 | **~$44** |
| 하루 20건 (97f, HD) | ~8분 | ~$4.22 | **~$131** |

> `distilled` 변형 사용 시 건당 시간 ~5배 단축 → 비용도 ~5배 절감

---

## 10. 트러블슈팅

### 콜드스타트가 너무 느림

- FlashBoot이 `ON`인지 확인
- Network Volume이 워커와 **같은 리전**인지 확인 (다른 리전이면 마운트 불가)
- 최초 실행 시 모델 다운로드 (5~10분) 이후 Volume에 캐시됨

### OUT_OF_MEMORY 에러

- `MODEL_VARIANT`를 `distilled`로 변경 (스텝 8로 VRAM 피크 감소)
- 해상도를 768x512 이하로 줄이기
- `num_frames`를 25로 줄이기
- CPU offload가 활성화되어 있는지 확인 (핸들러에서 자동 설정)

### 200GB+ 다운로드 발생

- **절대 발생 안 함**: 핸들러가 `allow_patterns`로 필요한 파일만 다운로드
- 만약 발생 시 Volume을 삭제하고 재생성 후 핸들러 코드 확인

### COMPLETED인데 결과가 없음

- RunPod Execution Timeout이 너무 짧은지 확인 (600초 권장)
- RunPod 대시보드 → Endpoint → Logs에서 핸들러 에러 확인

### 백엔드에서 RunPod 호출 실패

- `RUNPOD_API_KEY`가 유효한지 확인
- `RUNPOD_LTX_ENDPOINT_ID`가 정확한지 확인
- RunPod 대시보드에서 엔드포인트 상태가 `Ready`인지 확인

---

## 11. 아키텍처 요약

```
관리자 브라우저
    │
    ▼
Next.js (프론트엔드)
    │  POST /api/admin/video-gen
    ▼
FastAPI (EC2 백엔드)
    │  1. DB에 작업 저장 (status: pending)
    │  2. RunPod API POST /v2/{endpoint}/run
    │  3. DB 갱신 (status: submitted, runpod_job_id 저장)
    ▼
RunPod Serverless (A40 48GB)
    │  워커 자동 스케일업 (0 → 1)
    │  ltx_handler.py 실행
    │  LTX-Video 13B 파이프라인으로 영상 생성
    │  결과: video_base64 + metadata
    ▼
FastAPI (폴링)
    │  GET /v2/{endpoint}/status/{job_id}
    │  COMPLETED 시 base64 디코딩 → uploads/videos/{uuid}.mp4 저장
    │  DB 갱신 (status: completed, result_video_url)
    ▼
관리자 브라우저
    │  5초 간격 자동 폴링
    │  완료 시 <video> 미리보기 + 다운로드
    ▼
    완료
```
