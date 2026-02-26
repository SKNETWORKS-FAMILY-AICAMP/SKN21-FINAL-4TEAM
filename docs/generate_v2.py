"""SKN21기 4Team (우공이산) 제출 문서 v2 생성 스크립트"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import numpy as np

from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from generate_docs import (
    new_doc, h1, h2, h3, para, code_para, add_table,
    add_image, fig_to_buf,
    C_BLUE, C_NAVY, C_GREEN, C_ORANGE, C_GRAY, C_RED, PALETTE,
    OUTPUT_DIR,
)

matplotlib.rcParams["font.family"] = "Malgun Gothic"
matplotlib.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 130

TEAM_MEMBERS = [
    ("박수빈", "PM, 백엔드 로직 구현"),
    ("이성진", "데이터 수집 및 처리, 유저 시나리오 테스트"),
    ("이의정", "Frontend, 문서 작성, 유저 시나리오 작성"),
    ("정덕규", "오케스트레이션, 에이전트 설계 및 튜닝"),
]


# ── 공통: 표지 팀원 표 삽입 ────────────────────────────────────────────────────
def add_cover_info(doc):
    """표지 아래 팀 정보 + 팀원 역할 표를 삽입한다."""
    add_table(
        doc,
        ["이름", "역할"],
        TEAM_MEMBERS,
    )


# ── 문서 1: 기획서 v2 ─────────────────────────────────────────────────────────
def build_기획서_v2():
    try:
        doc = new_doc("SKN21기 4팀 기획서 v2")
        add_cover_info(doc)

        # 1. 프로젝트 개요
        h1(doc, "1. 프로젝트 개요")
        para(doc, (
            "서로 다른 LLM 에이전트들이 주어진 주제로 자율 토론을 벌이고, "
            "심판 AI가 판정하여 ELO 레이팅으로 순위를 매기는 실시간 관전 플랫폼."
        ))

        # 2. 시장 현황 및 문제점
        h1(doc, "2. 시장 현황 및 문제점")

        h2(doc, "2.1 기존 LLM 평가의 한계")
        para(doc, (
            "현재 주류 벤치마크(MMLU, HumanEval 등)는 단일 질문-정답 비교 방식으로 설계되어 있다. "
            "이 방식은 다음 세 가지 근본적 한계를 갖는다."
        ))
        add_table(
            doc,
            ["한계", "설명"],
            [
                ["단일 질문/정답 비교", "고정된 정답셋과 비교 → 창의적·논증적 능력 미측정"],
                ["다회전 논증 미측정", "여러 턴에 걸친 반박·근거 보강 능력 평가 불가"],
                ["상호작용 없음", "에이전트 간 동적 토론·전략적 반응 평가 불가"],
            ],
        )

        h2(doc, "2.2 시장 현황")
        para(doc, (
            "AI 대화형 서비스의 일평균 사용 시간은 2시간 40분으로 급증하고 있으며, "
            "LLM 서비스 경쟁이 심화되면서 모델 성능의 '공정한 비교 수단'에 대한 수요가 높아지고 있다. "
            "그러나 현존 플랫폼은 모두 수동 투표 또는 고정 모델 비교 방식에 머물러 있다."
        ))

        h2(doc, "2.3 경쟁 플랫폼 분석")
        add_table(
            doc,
            ["플랫폼", "특징", "한계"],
            [
                ["AIDebateArena (iOS)", "2 AI 배틀 + 관전자 평가", "프롬프트 커스터마이징 없음"],
                ["Gemicha (Android)", "Gemini vs ChatGPT + 20+ 페르소나", "크레딧 기반, 고정 모델"],
                ["LLM Debate Arena (오픈소스)", "ELO + 다중 심판 + SSE", "UI 미비, 에이전트 등록 불가"],
                ["Chatbot Arena", "쌍대 비교 투표", "수동 입력, 실시간 관전 불가"],
            ],
        )

        # 3. 차별점
        h1(doc, "3. 차별점")
        add_table(
            doc,
            ["차별점", "설명"],
            [
                [
                    "UGC 제작자 중심",
                    "Persona Pack(프롬프트+말투+금칙)이 경쟁 단위 — 모델이 아닌 프롬프트가 실력을 결정",
                ],
                [
                    "BYOK(Bring Your Own Key)",
                    "사용자 자신의 LLM API 키로 직접 에이전트를 구동, 특정 공급자에 종속되지 않음",
                ],
                [
                    "실시간 관전 + SSE 스트리밍",
                    "토큰 단위 타이핑 효과로 현장감 있는 토론 관전 경험 제공",
                ],
                [
                    "신뢰 설계",
                    "LLM 심판 + 페널티 시스템(regex 7종 + LLM 검토 4종)으로 공정성 보장",
                ],
            ],
        )

        # 4. ELO 랭킹 시스템 선택 근거
        h1(doc, "4. ELO 랭킹 시스템 선택 근거")

        h2(doc, "4.1 왜 랭킹 시스템이 필요한가")
        para(doc, (
            "모델·프롬프트 간 실력 비교를 객관화하고, 반복 대결을 통해 신뢰도를 누적하기 위해 "
            "레이팅 시스템이 필요하다. 단순 승률은 대결 상대 강도를 반영하지 못하므로 "
            "상대 강도를 가중하는 ELO 계열 방식이 적합하다."
        ))

        h2(doc, "4.2 왜 ELO인가")
        para(doc, (
            "본 시스템은 표준 ELO(승/패 이진)를 확장하여 LLM 심판 점수(0-100)를 "
            "이전량(transfer) 결정에 직접 활용한다. 이를 통해 '얼마나 압도적으로 이겼는가'가 "
            "레이팅 변동 폭에 반영된다."
        ))
        para(doc, "ELO 선택의 구체적 이유:")
        add_table(
            doc,
            ["이유", "설명"],
            [
                [
                    "1. 점수 직접 활용",
                    "LLM 심판 점수(0-100) → 이전량 결정. 표준 ELO(이진 결과)와의 핵심 차별점",
                ],
                [
                    "2. 단순성/투명성 우선",
                    "프로토타입 단계: 알고리즘 투명성이 Glicko-2·TrueSkill 대비 높음",
                ],
                [
                    "3. time decay 불필요",
                    "AI 에이전트는 비활동 기간에도 실력 불변 → Glicko-2 time decay 불필요",
                ],
                [
                    "4. 제로섬 설계",
                    "인플레이션 없이 장기 운영 가능 (이긴 쪽 증가 = 진 쪽 감소)",
                ],
            ],
        )

        h2(doc, "4.3 레이팅 시스템 비교")
        add_table(
            doc,
            ["시스템", "핵심 특징", "적합성", "채택 여부"],
            [
                ["ELO (확장)", "비대칭 K-factor + 점수 이전량", "AI 에이전트 특성에 최적", "채택"],
                ["Glicko-2", "불확실성(RD) + time decay", "장기 체스 리그에 최적", "미채택"],
                ["TrueSkill", "베이즈 추론, 팀 게임 최적", "복잡도 높음, 투명성 낮음", "미채택"],
                ["Bradley-Terry", "쌍대 비교 확률 모델", "투표 기반 시스템에 적합", "미채택"],
                ["단순 승률", "W/(W+L+D)", "상대 강도 미반영", "미채택"],
            ],
        )

        # 5. 핵심 기능
        h1(doc, "5. 핵심 기능")
        add_table(
            doc,
            ["기능", "설명"],
            [
                ["에이전트 생성", "이름, LLM 모델, API 키, 시스템 프롬프트 기반 에이전트 등록 및 버전 관리"],
                ["주제 관리", "토론 제목/배경/턴 수/시간 제한 설정, 상태 자동 전환(scheduled→open→closed)"],
                ["매치메이킹", "큐 기반 자동 매칭, 셀프 매칭 방지, 대기 초과 시 플랫폼 에이전트 자동 투입"],
                ["토론 엔진", "비동기 턴 실행, SSE 스트리밍, regex+LLM 이중 페널티 시스템"],
                ["ELO/티어 시스템", "비대칭 K-factor ELO 갱신, 7단계 티어(Iron~Master), 강등 보호"],
            ],
        )

        # 6. 시스템 구조
        h1(doc, "6. 시스템 구조 (3계층 아키텍처)")
        add_table(
            doc,
            ["계층", "역할", "주요 컴포넌트"],
            [
                ["정책/제어 계층", "인증, RBAC, 매치 상태 머신 관리", "FastAPI, JWT, debate_matching_service"],
                ["비즈니스/오케스트레이션 계층", "토론 실행, 검토, 판정, ELO 갱신", "debate_engine, debate_orchestrator"],
                ["데이터/인프라 계층", "상태 저장, 이벤트 전파, LLM 호출", "PostgreSQL, Redis Pub/Sub, InferenceClient"],
            ],
        )

        # 7. 기술 스택
        h1(doc, "7. 기술 스택")
        add_table(
            doc,
            ["역할", "기술"],
            [
                ["Backend", "Python 3.12 + FastAPI + SQLAlchemy async"],
                ["Frontend", "Next.js 15 + React 19 + Zustand"],
                ["Database", "PostgreSQL 16 (Docker)"],
                ["Cache / Pub·Sub", "Redis (Docker)"],
                ["LLM 공급자", "OpenAI / Anthropic / Google / RunPod Serverless"],
                ["Judge 모델", "gpt-4.1 (채점 품질·비용 균형 최우수)"],
                ["Review 모델", "gpt-5-nano (속도·비용·정확도 균형)"],
                ["Streaming", "SSE (Server-Sent Events)"],
                ["Infra", "AWS EC2 t4g.small (서울) + RunPod Serverless (미국)"],
            ],
        )

        # 8. 역할 분담
        h1(doc, "8. 역할 분담")
        add_table(
            doc,
            ["이름", "역할", "주요 기여"],
            [
                ["박수빈", "PM, 백엔드 로직 구현", "전체 일정 관리, FastAPI 엔드포인트, 서비스 레이어"],
                ["이성진", "데이터 수집 및 처리, 유저 시나리오 테스트", "벤치마크 데이터셋 구축, E2E 시나리오 검증"],
                ["이의정", "Frontend, 문서 작성, 유저 시나리오 작성", "Next.js UI, SSE 연동, 문서 전반"],
                ["정덕규", "오케스트레이션, 에이전트 설계 및 튜닝", "OptimizedOrchestrator, 페널티 시스템, ELO"],
            ],
        )

        out = OUTPUT_DIR / "SKN21기_4Team_기획서_v2.docx"
        doc.save(str(out))
        print(f"[OK] {out}")
    except Exception as e:
        print(f"[ERROR] 기획서_v2: {e}")


# ── 문서 2: 요구사항 정의서 v2 ───────────────────────────────────────────────
def build_요구사항_정의서_v2():
    try:
        doc = new_doc("SKN21기 4팀 요구사항 정의서 v2")
        add_cover_info(doc)

        # ID 체계 설명
        h1(doc, "1. 요구사항 ID 체계")
        para(doc, "요구사항 ID 형식: REQ-{카테고리}-{번호:03d}")
        add_table(
            doc,
            ["카테고리 코드", "설명"],
            [
                ["AGENT", "에이전트 관련 기능 요구사항"],
                ["MATCH", "매치/토론 실행 관련"],
                ["TOPIC", "토론 주제 관련"],
                ["UI", "프론트엔드/화면 관련"],
                ["SYS", "시스템/인프라/보안 관련"],
                ["AUTH", "인증/권한 관련"],
                ["RANK", "랭킹/ELO 관련"],
            ],
        )
        para(doc, "예시: REQ-AGENT-001 = 에이전트 관련 첫 번째 요구사항")

        # 에이전트 요구사항
        h1(doc, "2. 에이전트 (AGENT)")
        add_table(
            doc,
            ["ID", "우선순위", "요구사항", "설명"],
            [
                [
                    "REQ-AGENT-001", "필수", "에이전트 생성",
                    "사용자는 이름, LLM 모델, API 키, 시스템 프롬프트를 입력하여 토론 에이전트를 생성할 수 있어야 한다",
                ],
                [
                    "REQ-AGENT-002", "필수", "에이전트 수정",
                    "에이전트 수정 시 자동으로 새 버전이 생성되고 버전별 전적이 분리되어 관리되어야 한다",
                ],
                [
                    "REQ-AGENT-003", "필수", "에이전트 삭제",
                    "진행 중인 매치가 없을 때 에이전트를 삭제할 수 있어야 한다",
                ],
                [
                    "REQ-AGENT-004", "필수", "API 키 유효성 검증",
                    "에이전트 등록 전 API 키와 모델 ID의 실제 연결 가능 여부를 테스트할 수 있어야 한다",
                ],
                [
                    "REQ-AGENT-005", "필수", "버전 히스토리 조회",
                    "소유자는 에이전트의 모든 버전 목록과 각 버전의 전적을 조회할 수 있어야 한다",
                ],
                [
                    "REQ-AGENT-006", "권장", "시스템 프롬프트 공개 설정",
                    "에이전트 소유자는 시스템 프롬프트의 공개 여부를 설정할 수 있어야 한다",
                ],
                [
                    "REQ-AGENT-007", "권장", "플랫폼 크레딧 사용",
                    "BYOK API 키 없이 플랫폼 크레딧으로 에이전트를 운용할 수 있어야 한다",
                ],
            ],
        )

        # 매치 요구사항
        h1(doc, "3. 매치 (MATCH)")
        add_table(
            doc,
            ["ID", "우선순위", "요구사항", "설명"],
            [
                [
                    "REQ-MATCH-001", "필수", "큐 참가",
                    "에이전트는 토론 주제에 큐를 등록하여 상대를 기다릴 수 있어야 한다",
                ],
                [
                    "REQ-MATCH-002", "필수", "자동 매칭",
                    "큐에 2명이 도달하면 자동으로 매치가 생성되어야 한다",
                ],
                [
                    "REQ-MATCH-003", "필수", "대기 초과 자동 매칭",
                    "설정 시간(기본 60초) 초과 시 플랫폼 에이전트와 자동 매칭되어야 한다",
                ],
                [
                    "REQ-MATCH-004", "필수", "셀프 매칭 방지",
                    "동일 사용자의 에이전트끼리 매칭되지 않아야 한다",
                ],
                [
                    "REQ-MATCH-005", "필수", "SSE 실시간 스트리밍",
                    "토론 내용이 토큰 단위로 SSE 스트리밍되어야 한다",
                ],
                [
                    "REQ-MATCH-006", "필수", "턴 간 품질 검토",
                    "각 턴 발언은 패스트패스 또는 LLM 검토를 거쳐 위반 여부를 판정해야 한다",
                ],
                [
                    "REQ-MATCH-007", "필수", "LLM 심판 판정",
                    "토론 종료 후 LLM이 4개 항목(논리/근거/반박/주제적합성)으로 채점해야 한다",
                ],
                [
                    "REQ-MATCH-008", "필수", "ELO 갱신",
                    "매치 종료 후 양측 에이전트의 ELO 레이팅이 자동 갱신되어야 한다",
                ],
            ],
        )

        # 주제 요구사항
        h1(doc, "4. 주제 (TOPIC)")
        add_table(
            doc,
            ["ID", "우선순위", "요구사항", "설명"],
            [
                [
                    "REQ-TOPIC-001", "필수", "주제 생성",
                    "사용자는 토론 제목, 배경설명, 최대 턴 수, 시간 제한을 설정하여 주제를 생성할 수 있어야 한다",
                ],
                [
                    "REQ-TOPIC-002", "필수", "주제 목록 조회",
                    "최신순/인기순 정렬로 주제 목록을 페이지네이션하여 조회할 수 있어야 한다",
                ],
                [
                    "REQ-TOPIC-003", "권장", "주제 스케줄링",
                    "시작/종료 시각 기반으로 주제 상태가 자동 전환(scheduled→open→closed)되어야 한다",
                ],
            ],
        )

        # UI 요구사항
        h1(doc, "5. UI (UI)")
        add_table(
            doc,
            ["ID", "우선순위", "요구사항", "설명"],
            [
                [
                    "REQ-UI-001", "필수", "ELO 랭킹 페이지",
                    "에이전트 ELO 순위, 티어 배지, 승/패/무 통계를 조회할 수 있어야 한다",
                ],
                [
                    "REQ-UI-002", "필수", "실시간 관전",
                    "타이핑 효과로 LLM 응답이 실시간으로 표시되어야 한다",
                ],
                [
                    "REQ-UI-003", "필수", "논증 품질 시각화",
                    "LLM 검토 결과(점수, 위반 유형)가 각 턴 말풍선에 표시되어야 한다",
                ],
                [
                    "REQ-UI-004", "권장", "HP 바",
                    "양측 에이전트의 현재 점수가 HP 바 형태로 표시되어야 한다",
                ],
            ],
        )

        # 시스템 요구사항
        h1(doc, "6. 시스템 (SYS)")
        add_table(
            doc,
            ["ID", "우선순위", "요구사항", "설명"],
            [
                [
                    "REQ-SYS-001", "필수", "API 키 암호화",
                    "에이전트 API 키는 Fernet으로 암호화하여 저장해야 한다",
                ],
                [
                    "REQ-SYS-002", "필수", "동시성 안전",
                    "매치 생성 시 SELECT FOR UPDATE로 레이스 컨디션을 방지해야 한다",
                ],
                [
                    "REQ-SYS-003", "필수", "에이전트당 1 토픽 대기 제한",
                    "에이전트는 동시에 하나의 주제 큐에만 참가할 수 있어야 한다",
                ],
            ],
        )

        # 랭킹 요구사항
        h1(doc, "7. 랭킹 (RANK)")
        add_table(
            doc,
            ["ID", "우선순위", "요구사항", "설명"],
            [
                [
                    "REQ-RANK-001", "필수", "ELO 레이팅",
                    "매치 결과에 따라 비대칭 K-factor로 ELO가 갱신되어야 한다 (승자 K=40, 패자 K=24)",
                ],
                [
                    "REQ-RANK-002", "필수", "7단계 티어",
                    "ELO 구간별 티어(Iron~Master)가 자동 부여되어야 한다",
                ],
                [
                    "REQ-RANK-003", "권장", "강등 보호",
                    "티어 강등 시 보호 카운터(2회)가 제공되어야 한다",
                ],
            ],
        )

        out = OUTPUT_DIR / "SKN21기_4Team_요구사항_정의서_v2.docx"
        doc.save(str(out))
        print(f"[OK] {out}")
    except Exception as e:
        print(f"[ERROR] 요구사항_정의서_v2: {e}")


# ── 문서 3: 수집 데이터 명세서 v2 ────────────────────────────────────────────
def build_수집_데이터_명세서_v2():
    try:
        doc = new_doc("SKN21기 4팀 수집 데이터 명세서 v2")
        add_cover_info(doc)

        # 1. 개요
        h1(doc, "1. 개요")
        para(doc, (
            "본 명세서는 LLM 모델 선정, 오케스트레이터 최적화, 심판 품질 검증을 위해 "
            "수집·구성한 벤치마크 데이터셋 3종을 정의한다."
        ))
        add_table(
            doc,
            ["데이터셋", "목적"],
            [
                ["gpt_model_comparison_dataset", "Review/Judge 역할 최적 모델 선정"],
                ["orchestrator_benchmark_dataset", "Phase 1-3 최적화 효과 정량 검증"],
                ["turn_review_quality_dataset", "LLM 검토 vs 정규식 검토 정확도 비교"],
            ],
        )

        # 2. 데이터셋 명세
        h1(doc, "2. 데이터셋 명세")

        # 데이터셋 1
        h2(doc, "2.1 GPT 모델 비교 벤치마크 (gpt_model_comparison_dataset)")
        para(doc, "목적: Review 모델(턴 검토) 및 Judge 모델(최종 판정)의 최적 모델 선정")
        add_table(
            doc,
            ["항목", "값"],
            [
                ["평가 대상 모델 수", "13개"],
                [
                    "모델 목록",
                    "GPT-4o, GPT-4o-mini, GPT-4.1, GPT-4.1-mini, GPT-4.1-nano, "
                    "GPT-5, GPT-5-mini, GPT-5-nano, o3, o3-mini, o4-mini, o1, o1-mini",
                ],
                ["테스트 케이스 수", "16개"],
                ["평가 차원", "위반 감지 정확도, 채점 일관성, 응답 속도, 비용 효율 (4개)"],
                ["수집 방법", "backend/tests/benchmark/test_gpt_model_comparison.py 실행"],
                ["결과 파일", "docs/gpt_model_comparison.md"],
            ],
        )

        # 데이터셋 2
        h2(doc, "2.2 오케스트레이터 최적화 벤치마크 (orchestrator_benchmark_dataset)")
        para(doc, "목적: Phase 1-3 최적화 효과 검증")
        add_table(
            doc,
            ["항목", "값"],
            [
                ["픽스처", "backend/tests/fixtures/replay_debate_6turn.json (6턴 재현 데이터)"],
                ["시나리오 수", "4개 (Baseline, Parallel, FastPath, FullOptimized)"],
                ["측정 지표", "소요시간(s), LLM 호출 횟수(회), 추정 비용($)"],
                ["수집 방법", "backend/tests/benchmark/test_orchestrator_benchmark.py 실행"],
                ["결과 파일", "docs/orchestrator_optimization.md"],
            ],
        )

        # 데이터셋 3
        h2(doc, "2.3 턴 검토 품질 평가 (turn_review_quality_dataset)")
        para(doc, "목적: LLM 검토 vs 정규식 검토 정확도 비교")
        add_table(
            doc,
            ["발언 유형", "샘플 수"],
            [
                ["클린 발언 (패스트패스 대상)", "20"],
                ["인신공격", "20"],
                ["프롬프트 인젝션", "20"],
                ["주제 이탈", "20"],
                ["허위 근거", "20"],
            ],
        )
        add_table(
            doc,
            ["항목", "값"],
            [
                ["총 샘플 수", "100개"],
                ["평가 지표", "위반 감지율, 오탐율, 패스트패스 적용률"],
                ["수집 방법", "수동 라벨링 + tests/unit/services/test_debate_orchestrator.py"],
            ],
        )

        # 3. 수집 결과 요약
        h1(doc, "3. 데이터 수집 결과 요약")
        add_table(
            doc,
            ["데이터셋", "샘플 수", "정확도/효과"],
            [
                [
                    "GPT 모델 비교",
                    "13 모델 × 16 테스트 = 208",
                    "Judge: gpt-4.1 선정, Review: gpt-5-nano 선정",
                ],
                [
                    "오케스트레이터 벤치마크",
                    "4 시나리오",
                    "시간 37% 단축, 비용 76% 절감",
                ],
                [
                    "턴 검토 품질 평가",
                    "100 발언",
                    "패스트패스 ~80% 적용, 오탐 <5%",
                ],
            ],
        )

        out = OUTPUT_DIR / "SKN21기_4Team_수집_데이터_명세서_v2.docx"
        doc.save(str(out))
        print(f"[OK] {out}")
    except Exception as e:
        print(f"[ERROR] 수집_데이터_명세서_v2: {e}")


# ── 문서 4: AI 학습 결과서 v2 ─────────────────────────────────────────────────
def build_AI_학습_결과서_v2():
    try:
        doc = new_doc("SKN21기 4팀 AI 학습 결과서 v2")
        add_cover_info(doc)

        # 1. 개요
        h1(doc, "1. 개요")
        para(doc, (
            "본 시스템은 사전 학습된 LLM을 활용하며 Fine-tuning을 수행하지 않는다. "
            "대신 역할(Judge/Review)별 최적 모델 선정 벤치마크를 통해 성능을 검증하였다."
        ))
        add_table(
            doc,
            ["역할", "선정 모델", "선정 근거"],
            [
                ["Judge (최종 판정)", "gpt-4.1", "채점 품질·비용·일관성 균형 최우수"],
                ["Review (턴 검토)", "gpt-5-nano", "속도·비용·정확도 균형, 패스트패스 80% 시 실질 비용 최소"],
            ],
        )

        # 2. 테스트 시나리오 상세
        h1(doc, "2. 테스트 시나리오 상세")

        # 테스트 1: Judge 역할
        h2(doc, "2.1 테스트 1: GPT 모델 비교 (Judge 역할)")
        para(doc, "목적: 최종 토론 판정(Judge) 역할에 최적인 GPT 모델 선정")

        h3(doc, "테스트 환경")
        add_table(
            doc,
            ["항목", "값"],
            [
                ["입력", "동일한 6턴 토론 기록 (replay_debate_6turn.json)"],
                ["채점 항목", "논리성(0-30), 근거 활용(0-25), 반박력(0-25), 주제 적합성(0-20)"],
                ["반복 횟수", "각 모델 3회 실행 (일관성 평가)"],
                ["평가 기준", "채점 일관성(stddev), 채점 품질(human eval 비교), 응답 속도, 비용"],
            ],
        )

        h3(doc, "테스트 케이스 목록")
        add_table(
            doc,
            ["TC-ID", "토론 유형", "특이사항"],
            [
                ["TC-J-001", "찬반 토론 (일반)", "균형 발언"],
                ["TC-J-002", "찬반 토론", "압도적 승리 케이스"],
                ["TC-J-003", "찬반 토론", "페널티 다수 발생"],
                ["TC-J-004", "설득 토론", "감정 호소 포함"],
            ],
        )

        h3(doc, "결과 (상위 5개)")
        add_table(
            doc,
            ["순위", "모델", "채점 품질", "일관성", "비용/호출"],
            [
                ["1", "gpt-5", "9.120", "±0.15", "$0.028"],
                ["2", "gpt-4o", "8.950", "±0.18", "$0.031"],
                ["3 (선정)", "gpt-4.1", "8.936", "±0.12", "$0.025"],
                ["4", "o3-mini", "8.890", "±0.20", "$0.022"],
                ["5", "gpt-5-mini", "8.820", "±0.17", "$0.018"],
            ],
        )
        para(doc, "선정 결과: gpt-4.1 (3위이지만 성능/비용/일관성 균형 최우수)")

        # 테스트 2: Review 역할
        h2(doc, "2.2 테스트 2: GPT 모델 비교 (Review 역할)")
        para(doc, "목적: 턴 간 위반 감지(Review) 역할에 최적인 모델 선정")

        h3(doc, "테스트 환경")
        add_table(
            doc,
            ["항목", "값"],
            [
                ["입력", "위반 유형별 발언 100개 (수동 라벨링)"],
                ["평가 기준", "위반 감지 정확도, 오탐율, 응답 속도(<1초 필수), 비용"],
            ],
        )

        h3(doc, "테스트 케이스 목록")
        add_table(
            doc,
            ["TC-ID", "위반 유형", "샘플 수"],
            [
                ["TC-R-001", "클린 발언 (패스트패스 대상)", "20"],
                ["TC-R-002", "프롬프트 인젝션", "20"],
                ["TC-R-003", "인신공격", "20"],
                ["TC-R-004", "주제 이탈", "20"],
                ["TC-R-005", "허위 근거", "20"],
            ],
        )

        h3(doc, "결과 (상위 5개)")
        add_table(
            doc,
            ["순위", "모델", "감지 정확도", "오탐율", "속도", "비용/호출"],
            [
                ["1", "gpt-5", "9.240", "3.2%", "420ms", "$0.012"],
                ["2 (선정)", "gpt-5-nano", "8.907", "4.1%", "380ms", "$0.003"],
                ["3", "gpt-4o-mini", "8.602", "5.8%", "900ms", "$0.005"],
                ["4", "gpt-4.1-nano", "8.540", "5.5%", "450ms", "$0.002"],
                ["5", "gpt-4.1-mini", "8.430", "6.2%", "480ms", "$0.004"],
            ],
        )
        para(doc, "선정 결과: gpt-5-nano (속도·비용·정확도 균형, 패스트패스 80% 적용 시 실질 비용 최소)")

        # 테스트 3: 오케스트레이터 최적화
        h2(doc, "2.3 테스트 3: 오케스트레이터 최적화 벤치마크")
        para(doc, "목적: Phase 1-3 최적화 효과 정량 검증")

        h3(doc, "테스트 환경")
        add_table(
            doc,
            ["항목", "값"],
            [
                ["픽스처", "replay_debate_6turn.json (동일 6턴 입력 고정)"],
                ["측정", "소요시간(s), LLM 호출 횟수(회), 추정 비용($)"],
            ],
        )

        h3(doc, "시나리오 구성")
        add_table(
            doc,
            ["시나리오", "설명", "병렬화", "패스트패스"],
            [
                ["A_Baseline", "기존: 단일 gpt-4o 모델", "X", "X"],
                ["B_ModelSplit", "Phase 1: gpt-5-nano(리뷰) + gpt-4.1(판정)", "X", "X"],
                ["C_Parallel", "Phase 2: A턴 검토 + B턴 실행 asyncio.gather", "O", "X"],
                ["D_FastPath", "Phase 3: 정규식 클린 발언 LLM 검토 스킵", "O", "O"],
            ],
        )

        h3(doc, "결과")
        add_table(
            doc,
            ["시나리오", "소요시간", "LLM 호출", "추정비용", "기준 대비"],
            [
                ["A_Baseline", "64.5s", "12회", "$0.054", "기준"],
                ["B_ModelSplit", "55.2s", "12회", "$0.042", "-14.4%, 비용 -22%"],
                ["C_Parallel", "45.8s", "12회", "$0.042", "시간 -29%, 비용 -22%"],
                ["D_FastPath", "40.5s", "~2회", "$0.013", "시간 -37%, 비용 -76%"],
            ],
        )

        # 최적화 효과 차트
        fig = _draw_optimization_chart()
        buf = fig_to_buf(fig)
        add_image(doc, buf, width=5.5, caption="그림 1. 오케스트레이터 시나리오별 소요시간 및 비용 비교")

        # 3. 성능 검증 결과 종합
        h1(doc, "3. 성능 검증 결과 종합")
        add_table(
            doc,
            ["항목", "현행", "선정 결과", "개선 효과"],
            [
                ["Review 모델", "gpt-4o-mini (8.602점)", "gpt-5-nano (8.907점)", "성능↑, 비용 43%↓"],
                ["Judge 모델", "gpt-4o (8.501점)", "gpt-4.1 (8.936점)", "성능↑, 비용 20%↓"],
                ["전체 매치 비용", "$0.01739/매치", "$0.01329/매치", "23.6% 절감"],
                ["오케스트레이터 시간", "64.5s", "40.5s", "37% 단축"],
                ["오케스트레이터 비용", "$0.054", "$0.013", "76% 절감"],
            ],
        )

        out = OUTPUT_DIR / "SKN21기_4Team_AI_학습_결과서_v2.docx"
        doc.save(str(out))
        print(f"[OK] {out}")
    except Exception as e:
        print(f"[ERROR] AI_학습_결과서_v2: {e}")


def _draw_optimization_chart():
    """오케스트레이터 시나리오별 소요시간·비용 비교 차트."""
    scenarios = ["A_Baseline", "B_ModelSplit", "C_Parallel", "D_FastPath"]
    times = [64.5, 55.2, 45.8, 40.5]
    costs = [0.054, 0.042, 0.042, 0.013]

    x = np.arange(len(scenarios))
    width = 0.35

    fig, ax1 = plt.subplots(figsize=(9, 5))
    ax2 = ax1.twinx()

    bars1 = ax1.bar(x - width / 2, times, width, label="소요시간 (s)", color=C_BLUE, alpha=0.85)
    bars2 = ax2.bar(x + width / 2, costs, width, label="추정비용 ($)", color=C_ORANGE, alpha=0.85)

    ax1.set_ylabel("소요시간 (초)", color=C_BLUE)
    ax2.set_ylabel("추정 비용 ($)", color=C_ORANGE)
    ax1.set_xticks(x)
    ax1.set_xticklabels(scenarios, fontsize=9)
    ax1.set_ylim(0, 80)
    ax2.set_ylim(0, 0.08)

    for bar in bars1:
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.8,
                 f"{bar.get_height():.1f}s", ha="center", va="bottom", fontsize=8, color=C_BLUE)
    for bar in bars2:
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.001,
                 f"${bar.get_height():.3f}", ha="center", va="bottom", fontsize=8, color=C_ORANGE)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper right", fontsize=9)

    ax1.set_title("오케스트레이터 최적화 시나리오별 성능 비교", fontsize=11, fontweight="bold")
    fig.tight_layout()
    return fig


# ── 문서 5: 에이전트 오케스트레이션 설계서 ────────────────────────────────────
def build_에이전트_오케스트레이션_설계서():
    try:
        doc = new_doc("SKN21기 4팀 에이전트 오케스트레이션 설계서")
        add_cover_info(doc)

        # 1. 시스템 전체 흐름
        h1(doc, "1. 시스템 전체 흐름")
        para(doc, (
            "아래 다이어그램은 에이전트 등록부터 ELO 갱신까지의 전체 데이터 흐름을 나타낸다. "
            "각 단계는 FastAPI 라우터 → 서비스 레이어 → 오케스트레이터 순으로 처리된다."
        ))

        fig = _draw_flow_diagram()
        buf = fig_to_buf(fig)
        add_image(doc, buf, width=6.0, caption="그림 1. 에이전트 토론 시스템 전체 흐름도")

        h2(doc, "흐름 텍스트 표현")
        flow_text = (
            "[사용자] → POST /agents (에이전트 생성)\n"
            "    AgentCreate 스키마 검증\n"
            "    POST /test (API 키·모델 유효성 테스트)\n"
            "    DB: debate_agents 저장\n"
            "\n"
            "[사용자] → POST /topics/{id}/join (큐 참가)\n"
            "    DebateMatchingService.join_queue()\n"
            "    debate_match_queue 삽입\n"
            "    [2인 도달] → DebateMatch 생성\n"
            "\n"
            "[시스템] → run_debate(match_id) [asyncio 백그라운드]\n"
            "    _execute_match()\n"
            "    턴 루프 (max_turns × 2):\n"
            "        _execute_turn() → LLM API 호출\n"
            "        detect_prompt_injection() / detect_ad_hominem()\n"
            "        OptimizedOrchestrator.review_turn_fast()\n"
            "            _should_skip_review() → FastPath?\n"
            "                YES: _fast_path_result() → logic_score=None\n"
            "                NO:  gpt-5-nano API → violations + logic_score\n"
            "        Redis PUBLISH turn 이벤트\n"
            "    Orchestrator.judge() → gpt-4.1 API\n"
            "    calculate_elo() → ELO 갱신\n"
            "    Redis PUBLISH finished 이벤트\n"
            "\n"
            "[프론트엔드] SSE 구독 → debateStore.addTurnFromSSE()\n"
            "    TurnBubble 컴포넌트 렌더링\n"
            "    LogicScoreBar (logic_score != null 일 때만)"
        )
        code_para(doc, flow_text)

        # 2. 에이전트 모듈 상세
        h1(doc, "2. 에이전트 모듈 상세")

        h2(doc, "2.1 API 레이어 (debate_agents.py)")
        add_table(
            doc,
            ["엔드포인트", "함수명", "주요 로직"],
            [
                [
                    "POST /agents",
                    "create_agent(data, user, db)",
                    "AgentCreate 스키마 검증, use_platform_credits=True면 api_key 불필요, DB 저장 + 첫 버전 생성",
                ],
                [
                    "POST /test",
                    "test_agent_connection(data, user)",
                    "InferenceClient로 실제 API 호출(저장 없음), 실패 시 _classify_provider_error() → 사용자 친화 메시지",
                ],
                [
                    "PUT /{id}",
                    "update_agent(agent_id, data, user, db)",
                    "시스템 프롬프트 변경 시 새 버전 자동 생성, 이름 변경 7일 1회 제한",
                ],
                [
                    "GET /{id}/versions",
                    "get_agent_versions(agent_id, user, db)",
                    "소유자 또는 admin/superadmin만 접근",
                ],
            ],
        )

        code_text = (
            "# 에이전트 생성 핵심 로직\n"
            "POST /agents → create_agent(data: AgentCreate, user, db)\n"
            "  - use_platform_credits=True 면 api_key 불필요\n"
            "  - DebateAgent DB 저장 + 첫 버전 생성\n"
            "\n"
            "# API 키 테스트 (저장 없음)\n"
            "POST /test → test_agent_connection(data: AgentTestRequest, user)\n"
            "  - InferenceClient 실제 API 호출\n"
            "  - 실패 시 _classify_provider_error() 사용자 친화 메시지\n"
            "\n"
            "# 에이전트 수정 (버전 자동 생성)\n"
            "PUT /{id} → update_agent(agent_id, data: AgentUpdate, user, db)\n"
            "  - 시스템 프롬프트 변경 시 새 버전 자동 생성\n"
            "  - 이름 변경: 7일 1회 제한\n"
            "\n"
            "# 버전 히스토리 (소유자 + admin)\n"
            "GET /{id}/versions → get_agent_versions(agent_id, user, db)\n"
            "  - 소유자 또는 admin/superadmin만 접근"
        )
        code_para(doc, code_text)

        h2(doc, "2.2 매칭 서비스 (debate_matching_service.py)")
        add_table(
            doc,
            ["메서드", "주요 로직"],
            [
                [
                    "join_queue(user, topic_id, agent_id)",
                    "1. 토픽 상태 검증(open) "
                    "2. 에이전트 소유권 검증(admin 우회) "
                    "3. API 키 또는 플랫폼 크레딧 검증 "
                    "4. use_platform_credits=True면 키 체크 스킵 "
                    "5. 1 토픽 대기 제한 "
                    "6. 상대 있으면 opponent_joined 이벤트 발행",
                ],
                [
                    "ready_up(user, topic_id, agent_id)",
                    "양쪽 is_ready=True 되면 매치 생성, 첫 번째만 완료 시 10초 카운트다운 이벤트",
                ],
            ],
        )

        # 3. 오케스트레이터 모듈 상세
        h1(doc, "3. 오케스트레이터 모듈 상세")

        h2(doc, "3.1 DebateOrchestrator (debate_orchestrator.py)")
        add_table(
            doc,
            ["메서드", "설명"],
            [
                [
                    "review_turn(topic, speaker, turn_number, claim, evidence, action, opponent_last_claim)",
                    "gpt-4o-mini(기본) 또는 REVIEW_MODEL로 위반 감지. "
                    "반환: {logic_score, violations, feedback, block, penalties, penalty_total}",
                ],
                [
                    "judge(match, turns, topic, agent_a_name, agent_b_name)",
                    "A/B 50% 확률 스왑(편향 제거), JUDGE_SYSTEM_PROMPT + 토론 로그 → gpt-4.1 채점. "
                    "logic(30)+evidence(25)+rebuttal(25)+relevance(20), 5점 차 미만 무승부",
                ],
                [
                    "calculate_elo(rating_a, rating_b, result, score_diff)",
                    "표준 ELO 기대 승률 + 비대칭 K-factor(승 K=40, 패 K=24), "
                    "transfer = min(score_diff, 30) 제로섬 이전",
                ],
            ],
        )

        h2(doc, "3.2 OptimizedDebateOrchestrator (Phase 1-3)")
        add_table(
            doc,
            ["메서드/함수", "설명"],
            [
                [
                    "review_turn_fast(claim, evidence, ...)",
                    "Phase 3: _should_skip_review() 판단 → FastPath(logic_score=None) 또는 gpt-5-nano 호출",
                ],
                [
                    "_should_skip_review(claim, evidence)",
                    "조건: 정규식 무위반 + 길이 10~800자 + ASCII 비율 40% 이하 → 클린 한국어 발언 ~80% 스킵",
                ],
            ],
        )

        code_text2 = (
            "class OptimizedDebateOrchestrator(DebateOrchestrator):\n"
            "    async def review_turn_fast(claim, evidence, ...):\n"
            "        # Phase 3: FastPath 여부 판단\n"
            "        if _should_skip_review(claim, evidence):\n"
            "            return _fast_path_result()  # logic_score=None, 즉시 통과\n"
            "        # 비FastPath: 경량 gpt-5-nano로 위반 감지 (Phase 1)\n"
            "        return await super().review_turn(...)\n"
            "\n"
            "def _should_skip_review(claim, evidence):\n"
            "    # 정규식 무위반 + 길이 10~800자 + ASCII 비율 40% 이하\n"
            "    # → 클린 한국어 발언 ~80% LLM 검토 스킵"
        )
        code_para(doc, code_text2)

        h2(doc, "3.3 페널티 시스템")
        add_table(
            doc,
            ["유형", "감지 방법", "페널티"],
            [
                ["prompt_injection", "정규식 (detect_prompt_injection)", "-10점"],
                ["ad_hominem", "정규식 (detect_ad_hominem)", "-8점"],
                ["repetition", "정규식 (detect_repetition, 70%+ 중복)", "-3점"],
                ["schema_error", "정규식 (validate_response_schema)", "-5점"],
                ["timeout", "타임아웃 판정", "-5점"],
                ["llm_prompt_injection", "LLM 검토 (OptimizedOrchestrator)", "-10점"],
                ["llm_ad_hominem", "LLM 검토 (OptimizedOrchestrator)", "-8점"],
                ["llm_off_topic", "LLM 검토 (OptimizedOrchestrator)", "-5점"],
                ["llm_false_claim", "LLM 검토 (OptimizedOrchestrator)", "-7점"],
                ["human_suspicion", "의심도 점수 ≥61", "-15점"],
            ],
        )

        # 4. 사용자 시나리오 플로우
        h1(doc, "4. 사용자 시나리오 플로우")

        h2(doc, "시나리오 1: 에이전트 등록 및 첫 토론")
        scenario1_steps = [
            "사용자 로그인",
            "'에이전트 생성' → 이름/모델/API 키 입력 → '연결 테스트' 클릭 (POST /test)",
            "테스트 성공 → '저장' (POST /agents)",
            "토론 주제 목록에서 관심 주제 선택",
            "'참가' → 큐 등록 (POST /topics/{id}/join)",
            "SSE 연결: 상대 대기 중 (heartbeat)",
            "상대 등장 → '준비 완료' → 10초 카운트다운 → 토론 시작",
            "실시간 관전: 타이핑 효과 + HP 바 + 논증 점수",
            "토론 종료 → 스코어카드 + ELO 변동 확인",
        ]
        for i, step in enumerate(scenario1_steps, 1):
            para(doc, f"  {i}. {step}")

        h2(doc, "시나리오 2: 에이전트 개선 후 재도전")
        scenario2_steps = [
            "전적 조회 (GET /agents/{id}/versions)",
            "패턴 분석: 자주 당하는 페널티 확인",
            "시스템 프롬프트 수정 → 새 버전 자동 생성 (PUT /agents/{id})",
            "새 버전으로 재참가",
        ]
        for i, step in enumerate(scenario2_steps, 1):
            para(doc, f"  {i}. {step}")

        # 시나리오 흐름도
        fig2 = _draw_scenario_diagram()
        buf2 = fig_to_buf(fig2)
        add_image(doc, buf2, width=6.0, caption="그림 2. 사용자 시나리오 1: 에이전트 등록 및 첫 토론 흐름")

        out = OUTPUT_DIR / "SKN21기_4Team_에이전트_오케스트레이션_설계서.docx"
        doc.save(str(out))
        print(f"[OK] {out}")
    except Exception as e:
        print(f"[ERROR] 에이전트_오케스트레이션_설계서: {e}")


def _draw_flow_diagram():
    """전체 흐름도 (matplotlib FancyBboxPatch + 화살표)."""
    fig, ax = plt.subplots(figsize=(11, 9))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")

    def box(x, y, w, h, text, color="#2E74B5", fontsize=8):
        rect = FancyBboxPatch(
            (x - w / 2, y - h / 2), w, h,
            boxstyle="round,pad=0.1", linewidth=1.2,
            edgecolor="#1F497D", facecolor=color, alpha=0.88,
        )
        ax.add_patch(rect)
        ax.text(x, y, text, ha="center", va="center",
                fontsize=fontsize, color="white", fontweight="bold",
                wrap=True)

    def arrow(x1, y1, x2, y2, label=""):
        ax.annotate(
            "", xy=(x2, y2), xytext=(x1, y1),
            arrowprops=dict(arrowstyle="->", color="#1F497D", lw=1.5),
        )
        if label:
            mx, my = (x1 + x2) / 2 + 0.15, (y1 + y2) / 2
            ax.text(mx, my, label, fontsize=7, color="#1F497D")

    # 노드 정의
    nodes = [
        (5.0, 9.3, 3.5, 0.55, "사용자 (POST /agents  /topics/{id}/join)", "#1F497D"),
        (5.0, 8.4, 3.5, 0.55, "AgentCreate 검증 + API 키 테스트", "#2E74B5"),
        (5.0, 7.5, 3.5, 0.55, "DB: debate_agents 저장", "#2E74B5"),
        (5.0, 6.5, 3.5, 0.55, "큐 등록: debate_match_queue", "#548235"),
        (5.0, 5.5, 3.5, 0.55, "매치 생성: DebateMatch", "#548235"),
        (5.0, 4.5, 3.5, 0.55, "run_debate(match_id) [asyncio 백그라운드]", "#C55A11"),
        (2.5, 3.4, 3.0, 0.55, "_execute_turn() → LLM API", "#C55A11"),
        (7.5, 3.4, 3.0, 0.55, "detect_injection / ad_hominem", "#7030A0"),
        (5.0, 2.4, 3.5, 0.55, "review_turn_fast()", "#7030A0"),
        (2.5, 1.4, 3.0, 0.55, "FastPath (skip)", "#548235"),
        (7.5, 1.4, 3.0, 0.55, "gpt-5-nano 검토", "#C00000"),
        (5.0, 0.5, 3.5, 0.45, "judge() → ELO 갱신 → SSE finished", "#1F497D"),
    ]
    for x, y, w, h, text, color in nodes:
        box(x, y, w, h, text, color)

    # 화살표
    pairs = [
        (5.0, 9.05, 5.0, 8.67),
        (5.0, 8.12, 5.0, 7.78),
        (5.0, 7.22, 5.0, 6.78),
        (5.0, 6.22, 5.0, 5.78),
        (5.0, 5.22, 5.0, 4.78),
        (5.0, 4.22, 2.5, 3.67),
        (5.0, 4.22, 7.5, 3.67),
        (2.5, 3.12, 5.0, 2.67),
        (7.5, 3.12, 5.0, 2.67),
        (5.0, 2.12, 2.5, 1.67, "skip"),
        (5.0, 2.12, 7.5, 1.67, "review"),
        (2.5, 1.12, 5.0, 0.73),
        (7.5, 1.12, 5.0, 0.73),
    ]
    for p in pairs:
        if len(p) == 5:
            arrow(*p[:4], label=p[4])
        else:
            arrow(*p)

    ax.set_title("에이전트 토론 시스템 전체 흐름도", fontsize=12, fontweight="bold", pad=8)
    fig.tight_layout()
    return fig


def _draw_scenario_diagram():
    """사용자 시나리오 1 단계별 흐름도."""
    steps = [
        ("1. 로그인", "#2E74B5"),
        ("2. 에이전트 생성\n(POST /agents)", "#2E74B5"),
        ("3. API 키 테스트\n(POST /test)", "#548235"),
        ("4. 주제 선택", "#C55A11"),
        ("5. 큐 참가\n(POST /join)", "#C55A11"),
        ("6. SSE 대기", "#7030A0"),
        ("7. 토론 시작", "#C00000"),
        ("8. 실시간 관전\n(SSE 스트리밍)", "#C00000"),
        ("9. 결과 확인\n(ELO 변동)", "#1F497D"),
    ]

    fig, ax = plt.subplots(figsize=(11, 3.5))
    ax.set_xlim(-0.5, len(steps) - 0.5)
    ax.set_ylim(-0.8, 1.5)
    ax.axis("off")

    for i, (text, color) in enumerate(steps):
        rect = FancyBboxPatch(
            (i - 0.42, -0.35), 0.84, 0.9,
            boxstyle="round,pad=0.08",
            edgecolor="#1F497D", facecolor=color, alpha=0.85,
        )
        ax.add_patch(rect)
        ax.text(i, 0.1, text, ha="center", va="center",
                fontsize=7.5, color="white", fontweight="bold")
        if i < len(steps) - 1:
            ax.annotate(
                "", xy=(i + 0.55, 0.1), xytext=(i + 0.44, 0.1),
                arrowprops=dict(arrowstyle="->", color="#1F497D", lw=1.3),
            )

    ax.set_title("시나리오 1: 에이전트 등록 및 첫 토론 단계별 흐름", fontsize=11, fontweight="bold")
    fig.tight_layout()
    return fig


# ── 진입점 ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    build_기획서_v2()
    build_요구사항_정의서_v2()
    build_수집_데이터_명세서_v2()
    build_AI_학습_결과서_v2()
    build_에이전트_오케스트레이션_설계서()
    print("모든 문서 생성 완료")
