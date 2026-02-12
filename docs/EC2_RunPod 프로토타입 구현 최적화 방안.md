# **접속자 10명 이하 소규모 RP 챗봇 프로토타입을 위한 EC2-RunPod 하이브리드 아키텍처 및 비용 최적화 심층 분석 보고서**

## **1\. 서론: 소규모 RP 챗봇 개발의 기술적, 경제적 맥락**

### **1.1 연구 배경 및 목적**

2025년과 2026년을 기점으로 대규모 언어 모델(LLM)을 활용한 페르소나 기반의 롤플레잉(RP) 챗봇 시장은 폭발적인 성장을 거듭하고 있다. Character.ai의 성공과 한국 시장에서의 Zeta, Talkie와 같은 서비스의 급부상은 단순한 정보 제공을 넘어선 '감성적 상호작용'과 '몰입형 스토리텔링'에 대한 사용자들의 강력한 니즈를 증명한다.1 이러한 서비스들은 사용자가 직접 생성한 캐릭터와의 깊이 있는 대화, 장기 기억(Long-term Memory) 유지, 그리고 시나리오 기반의 상호작용을 핵심 가치로 삼는다.

그러나 이러한 RP 챗봇을 초기 단계의 프로토타입으로 구현하고자 하는 개발자와 스타트업에게는 심각한 인프라 딜레마가 존재한다. 상용 서비스 수준의 GPU 클러스터를 구축하는 것은 막대한 초기 비용을 요구하며, 반대로 비용을 절감하기 위해 저성능 모델을 사용할 경우 사용자 경험(UX)의 핵심인 '몰입감'이 훼손된다. 특히 동시 접속자 수가 10명 내외인 소규모 프로토타입 단계에서는 고정 비용이 발생하는 전용 GPU 인스턴스(Dedicated Pod)를 유지하는 것이 비효율적이며, 사용자의 간헐적인 트래픽 패턴에 맞춰 유동적으로 자원을 할당하는 전략이 필수적이다.

본 보고서는 이러한 배경하에, 접속자 10명 이하의 소규모 RP 챗봇 프로토타입을 구현하기 위한 최적의 아키텍처를 제안한다. 구체적으로는 AWS EC2의 안정적인 애플리케이션 호스팅 능력과 RunPod Serverless의 비용 효율적인 GPU 연산 능력을 결합한 '하이브리드 스플릿 브레인(Hybrid Split-Brain)' 아키텍처를 설계하고, 이에 대한 기술적 타당성과 비용 효율성을 심층 분석한다.

### **1.2 RP 챗봇의 특수성 및 기술적 요구사항**

일반적인 질의응답(Q\&A) 봇과 달리, RP 챗봇은 다음과 같은 기술적 특수성을 가진다.

1. **긴 컨텍스트 윈도우(Long Context Window):** RP 세션은 수백 턴 이상 지속될 수 있으며, 캐릭터의 설정값(Persona), 세계관 정보(Lorebook), 과거 대화 내역이 지속적으로 프롬프트에 포함되어야 한다. 이는 추론 엔진의 KV 캐시(Key-Value Cache) 관리 효율성이 성능의 핵심임을 시사한다.3  
2. **상태 유지(Statefulness):** 사용자의 선택이나 주사위 굴림(Dice Roll) 결과에 따라 스토리의 분기가 달라지며, 이는 단순한 텍스트 생성을 넘어선 게임 로직의 통합을 요구한다.5  
3. **지연 시간(Latency) 민감성:** 실시간 대화의 몰입감을 위해 생성 속도(Tokens per Second)와 첫 토큰 생성 시간(Time to First Token, TTFT)이 중요하지만, 동시에 비용 절감을 위해 물리적 거리가 먼 저렴한 GPU 리전(Region)을 사용해야 하는 상충 관계가 발생한다.

본 연구는 이러한 요구사항을 충족시키기 위해 추론 엔진으로 **SGLang**을, 데이터베이스 및 애플리케이션 서버로 **AWS Graviton 기반 EC2**를 선정하고, 이들의 기술적 시너지를 극대화하는 방안을 모색한다.

## **2\. 아키텍처 설계: 하이브리드 스플릿 브레인 (Hybrid Split-Brain) 모델**

본 프로젝트를 위해 제안하는 아키텍처의 핵심은 \*\*'상태 관리(State Management)와 연산(Compute)의 지리적, 논리적 분리'\*\*이다. 이를 '하이브리드 스플릿 브레인' 모델이라 칭하며, 제어 평면(Control Plane)은 사용자와 물리적으로 가까운 서울 리전에, 연산 평면(Compute Plane)은 GPU 비용이 저렴한 미국 리전에 배치하는 전략이다.

### **2.1 제어 평면 (Control Plane): AWS EC2 (서울 리전)**

사용자와의 직접적인 연결, 세션 관리, 데이터베이스 트랜잭션, 그리고 프롬프트 조립(Assembly)을 담당하는 애플리케이션 서버는 \*\*AWS 아시아 태평양(서울) 리전(ap-northeast-2)\*\*에 위치해야 한다. 이는 한국 사용자들에게 웹사이트 로딩 속도와 초기 연결 지연 시간을 최소화하기 위함이다.

#### **2.1.1 인스턴스 선정: AWS Graviton2 (t4g.small)**

소규모 프로토타입의 애플리케이션 서버로는 **t4g.small** 인스턴스가 기술적, 비용적 측면에서 압도적인 우위를 점한다.

* **아키텍처 효율성:** t4g 인스턴스는 ARM64 아키텍처 기반의 AWS Graviton2 프로세서를 탑재하고 있다. 이는 동급의 x86 기반 인스턴스(t3.small) 대비 약 40% 향상된 가격 대비 성능을 제공한다.7 Python 기반의 웹 프레임워크(FastAPI, Django)와 PostgreSQL은 ARM 아키텍처에서 네이티브로 원활하게 구동되며, 별도의 호환성 문제없이 비용 절감 효과를 누릴 수 있다.  
* **리소스 적합성:** t4g.small은 2 vCPU와 2 GiB 메모리를 제공한다. 이는 동시 접속자 10명 수준의 트래픽을 처리하기에 충분하며, 경량화된 Docker 컨테이너 환경에서 웹 서버(Nginx), 애플리케이션(FastAPI), 데이터베이스(PostgreSQL)를 동시에 구동할 수 있는 최소한의 여유 자원을 보장한다.8  
* **비용 분석:** 서울 리전 기준 t4g.small의 온디맨드 가격은 시간당 약 $0.0208이다. 이를 월간(730시간)으로 환산하면 약 **$15.18**의 비용이 발생하며, 이는 1년 예약 인스턴스(Reserved Instance) 등을 통해 더욱 절감할 수 있다.9

### **2.2 연산 평면 (Compute Plane): RunPod Serverless (미국 리전)**

LLM 추론을 담당하는 GPU 자원은 비용 효율성을 최우선으로 고려하여 **RunPod**을 활용한다. AWS EC2의 GPU 인스턴스(g4dn, p4 등)는 서울 리전에서 사용 시 비용이 매우 높으며, 프로토타입 단계에서는 불필요한 고정 비용(Idle Cost)을 유발한다.

#### **2.2.1 Serverless vs. Pods: 유휴 자원 최소화 전략**

10명의 사용자가 하루에 총 1,000회의 메시지를 주고받는 시나리오를 가정해 보자. 일반적인 RP 메시지 생성에 5초가 소요된다면, 하루 중 GPU가 실제로 작동하는 시간은 5,000초(약 1.4시간)에 불과하다. 나머지 22.6시간 동안 GPU를 켜두는 것은 막대한 낭비다.

* **RunPod Serverless:** 요청이 있을 때만 워커(Worker)를 기동하고, 추론이 끝나면 자동으로 종료(Scale-to-Zero)하는 방식이다. 사용자는 오직 '추론 시간(초 단위)'에 대해서만 비용을 지불한다.10 이는 간헐적인 트래픽이 발생하는 프로토타입에 최적화된 모델이다.  
* **RunPod Pods:** 기존의 인스턴스 임대 방식은 개발 및 디버깅에는 유리하지만, 서비스를 상시 대기시켜야 하는 챗봇 서버로 사용할 경우 유휴 시간에도 비용이 청구된다.12

#### **2.2.2 지리적 배치와 레이턴시 전략**

RunPod의 GPU 데이터센터는 주로 미국과 유럽에 집중되어 있으며, 이들 지역의 GPU 단가는 다른 지역보다 저렴하다. 서울 리전의 EC2에서 미국 서부(오레곤, 캘리포니아)의 RunPod 엔드포인트로 요청을 보낼 경우, 네트워크 왕복 지연 시간(RTT)은 약 **135ms \~ 150ms** 수준이다.13

* **지연 시간의 수용 가능성:** 실시간 액션 게임과 달리, 텍스트 생성형 AI 서비스에서는 150ms의 네트워크 지연이 치명적이지 않다. 사용자는 자신의 메시지를 입력한 후 AI가 '생각하는 시간'을 자연스럽게 받아들이며, 스트리밍(Streaming) 기술을 통해 첫 토큰이 도착하는 순간부터 체감 지연 시간을 획기적으로 줄일 수 있다. 따라서 비용 절감을 위해 미국 리전의 GPU를 사용하는 것은 합리적인 트레이드오프다.

## **3\. 추론 엔진 최적화: SGLang과 RadixAttention의 도입**

RP 챗봇의 기술적 핵심은 '이전 대화의 맥락(Context)을 얼마나 효율적으로 처리하느냐'에 있다. 사용자와 AI가 주고받은 수십 턴의 대화는 매번 새로운 입력 프롬프트의 일부로 GPU에 전송된다. 이 과정에서 발생하는 중복 연산을 제거하는 것이 성능과 비용 최적화의 열쇠다. 본 보고서는 이를 위해 **SGLang** 엔진의 도입을 강력히 권고한다.

### **3.1 vLLM 대비 SGLang의 우위성 분석**

현재 가장 널리 사용되는 오픈소스 추론 엔진인 vLLM은 PagedAttention 기술을 통해 메모리 효율성을 극대화했다. 그러나 RP 시나리오와 같은 '멀티 턴(Multi-turn) 대화'에서는 SGLang이 제공하는 **RadixAttention** 기술이 월등한 성능을 발휘한다.3

#### **3.1.1 RadixAttention의 작동 원리 및 효과**

RadixAttention은 KV 캐시(Key-Value Cache)를 단순한 LRU(Least Recently Used) 리스트가 아닌, **라딕스 트리(Radix Tree)** 구조로 관리한다.14

* **접두사 캐싱(Prefix Caching)의 자동화:** 사용자가 AI와 대화를 이어갈 때, 시스템 프롬프트(캐릭터 설정)와 이전 대화 내역은 변하지 않는 '접두사(Prefix)'가 된다. SGLang은 이 접두사에 해당하는 KV 캐시를 트리 구조에서 자동으로 찾아 재사용한다.  
* **동적 최적화:** vLLM의 접두사 캐싱은 블록 단위의 정확한 일치를 요구하며 주로 고정된 템플릿을 사용하는 배치(Batch) 처리에 최적화되어 있다. 반면, SGLang은 다양한 길이와 분기를 가지는 대화형 텍스트에서 부분적인 일치를 동적으로 찾아내 캐시를 재사용하는 데 특화되어 있다.3  
* **성능 향상:** 벤치마크 결과에 따르면, 멀티 턴 대화 시나리오에서 SGLang은 캐시 적중(Cache Hit) 시 vLLM 대비 약 **10\~20% 이상의 처리량(Throughput) 향상**과 지연 시간 단축 효과를 보인다.3

### **3.2 RunPod Serverless에서의 적용**

RunPod Serverless 환경에서는 워커가 유휴 상태일 때 종료될 수 있다. 그러나 활성 상태(Active)가 유지되는 동안, 혹은 웜 스타트(Warm Start) 상황에서는 SGLang의 캐시가 메모리에 남아 있어 후속 요청 처리가 비약적으로 빨라진다.

* **구성 전략:** RunPod 템플릿 설정 시 SGLang 기반의 도커 이미지를 사용하며, 환경 변수 DISABLE\_RADIX\_CACHE를 false로 설정하여 기능을 활성화해야 한다.17 이는 사용자가 캐릭터와 연속적으로 대화를 주고받는 RP 상황에서, 두 번째 턴부터는 '프리필(Prefill)' 단계의 연산 비용을 거의 0에 가깝게 줄여준다. 이는 초당 과금되는 서버리스 환경에서 직접적인 비용 절감으로 이어진다.

## **4\. 데이터베이스 및 상태 관리 전략**

소규모 프로토타입에서는 복잡한 관리형 서비스(예: AWS RDS)보다는 EC2 내부에서 직접 호스팅하는 방식이 비용 효율적이다. 또한, RP 챗봇의 핵심 기능인 '장기 기억'과 'Lorebook' 구현을 위해 벡터 데이터베이스의 도입이 필수적이다.

### **4.1 관계형 데이터베이스: PostgreSQL (Self-Hosted)**

EC2 t4g.small 인스턴스 내에 Docker 컨테이너로 **PostgreSQL**을 구동한다.

* **비용 절감:** AWS RDS의 최소 사양인 db.t4g.micro조차 월 $13 이상의 비용이 발생하며, 이는 EC2 인스턴스 전체 비용과 맞먹는다.18 반면, Docker로 직접 띄운 Postgres는 추가 비용이 없으며, 10명 규모의 데이터 트래픽은 t4g.small의 자원으로 충분히 감당 가능하다.  
* **관리:** Docker Volume을 EBS(Elastic Block Store)에 마운트하여 데이터 영속성을 보장한다. 주기적인 pg\_dump를 통해 S3로 백업하는 스크립트를 크론잡(Cronjob)으로 등록하면 최소한의 안전장치를 마련할 수 있다.20

### **4.2 벡터 데이터베이스와 Lorebook 구현**

RP 챗봇의 몰입감을 높이기 위해서는 캐릭터의 방대한 설정이나 과거의 사건을 적절한 시점에 상기시키는 RAG(Retrieval-Augmented Generation) 시스템이 필요하다. 이를 위해 별도의 벡터 DB(Pinecone, Milvus 등)를 구축하는 것은 과도한 오버엔지니어링이다.

#### **4.2.1 pgvector 확장 기능 활용**

가장 합리적인 선택은 PostgreSQL의 **pgvector** 확장을 사용하는 것이다.21

* **단일 인프라:** 관계형 데이터와 벡터 데이터를 하나의 DB에서 관리할 수 있어 아키텍처가 단순해진다. 사용자 정보, 채팅 로그, 그리고 임베딩 벡터가 조인(Join) 쿼리로 한 번에 처리될 수 있다.23  
* **성능:** 2,000차원 이하의 벡터, 수십만 개 단위의 데이터셋에서는 pgvector의 HNSW(Hierarchical Navigable Small World) 인덱싱 성능이 전용 벡터 DB에 뒤지지 않는다.24 10명의 사용자가 생성할 데이터 양으로는 성능 저하를 걱정할 필요가 전혀 없다.  
* **Lorebook 구현:** 캐릭터의 설정집(Lorebook)을 텍스트 청크(Chunk)로 나누어 pgvector에 저장한다. 사용자가 질문을 던지면, 해당 입력값의 임베딩과 유사도가 높은 Lorebook 청크를 검색(Retrieval)하여 시스템 프롬프트에 동적으로 삽입(Injection)한다.25 이를 통해 LLM은 제한된 컨텍스트 윈도우 내에서도 방대한 설정 정보를 참조하는 듯한 환상을 줄 수 있다.

#### **4.2.2 대안: sqlite-vss**

만약 프로젝트가 극도로 경량화되어야 한다면, 파일 기반의 SQLite에 벡터 검색 기능을 추가한 sqlite-vss도 고려할 수 있다.27 그러나 동시 쓰기 작업에 대한 제약과 추후 확장성을 고려할 때, PostgreSQL \+ pgvector 조합이 더 안정적인 선택지다.

## **5\. 비용 분석 및 손익분기점(Break-Even) 계산**

본 아키텍처의 경제성을 검증하기 위해 RunPod Serverless와 Dedicated Pod의 비용을 정량적으로 비교 분석한다.

### **5.1 사용량 시나리오 가정**

* **동시 접속자:** 최대 10명  
* **일일 총 메시지 수:** 1,000회 (사용자당 100회 가정)  
* **메시지 당 평균 처리 시간:** 5초 (입력 처리 \+ 200토큰 출력 기준)  
* **모델:** Llama-3-70B (또는 동급의 고성능 모델)  
* **필요 GPU:** NVIDIA A100 80GB (또는 2x A6000)

### **5.2 RunPod Serverless 비용 산출**

RunPod Serverless는 초 단위로 과금된다.

* **총 가동 시간:** 1,000회 × 5초 \= 5,000초/일  
* **GPU 단가 (A100 80GB 기준):** 약 $0.00076/초 29  
* **일일 비용:** 5,000 × $0.00076 \= **$3.80**  
* **월간 비용 (30일):** **$114.00**

### **5.3 Dedicated Pod (On-Demand) 비용 산출**

Dedicated Pod는 사용 여부와 관계없이 점유 시간 전체에 대해 과금된다.

* **GPU 단가 (A100 80GB 기준):** 시간당 약 $1.49 30  
* **일일 비용:** 24시간 × $1.49 \= **$35.76**  
* **월간 비용 (30일):** **$1,072.80**

### **5.4 손익분기점 분석 및 결론**

Serverless 비용과 Pod 비용이 같아지는 지점을 계산하면 다음과 같다.

![][image1]  
![][image2]  
즉, 하루에 **약 13시간 이상** GPU가 쉴 새 없이 돌아가는 상황이 아니라면, Serverless 방식이 압도적으로 유리하다. 현재 가정한 하루 1.4시간(5,000초) 가동 시나리오에서는 Serverless가 Pod 대비 **약 90%의 비용 절감** 효과를 제공한다. 이는 초기 스타트업이나 프로토타입 단계에서 자금 운용의 유연성을 확보하는 데 결정적인 역할을 한다.

## **6\. 구현 가이드 및 성능 최적화**

### **6.1 네트워크 지연 극복을 위한 스트리밍 전략**

서울-미국 간 150ms의 레이턴시를 사용자 경험에서 감추기 위해 **SSE (Server-Sent Events)** 기술을 활용해야 한다.

* **SSE vs. WebSockets:** 채팅과 같은 단방향 데이터 전송(서버 \-\> 클라이언트)에는 WebSockets보다 SSE가 훨씬 가볍고 구현이 용이하다.32 HTTP 프로토콜을 그대로 사용하므로 방화벽 문제에서 자유롭고, 재연결 처리가 브라우저 레벨에서 지원된다.  
* **구현 로직:**  
  1. EC2의 Backend(FastAPI)는 RunPod API에 stream=True 옵션으로 요청을 보낸다.  
  2. RunPod으로부터 토큰이 생성되는 즉시 EC2는 이를 받아 비동기 제너레이터(Async Generator)를 통해 클라이언트에게 SSE 이벤트로 전달한다.  
  3. 클라이언트는 첫 번째 토큰이 도착하는 즉시 화면에 렌더링을 시작한다. 이 '타자기 효과'는 사용자가 백그라운드의 네트워크 지연을 인지하지 못하게 만든다.

### **6.2 콜드 스타트(Cold Start) 관리: FlashBoot 활용**

Serverless의 가장 큰 단점은 유휴 상태 후 첫 요청 시 발생하는 '콜드 스타트' 지연이다. 모델 로딩에 수십 초가 걸리면 채팅 경험이 망가진다.

* **RunPod FlashBoot:** RunPod이 제공하는 FlashBoot 기능을 활성화하면, 도커 이미지의 레이어를 고속으로 복원하여 컨테이너 기동 시간을 획기적으로 단축(약 2초 이내)할 수 있다.34  
* **Active Worker 유지 전략:** 비용을 조금 더 지불하더라도 최상의 경험을 원한다면, min\_workers=1로 설정하여 최소 1개의 GPU를 항상 대기시킬 수 있다. 하지만 10명 규모의 프로토타입에서는 비용 최적화를 위해 기본적으로 0으로 설정하되, 트래픽이 몰리는 특정 시간대(예: 저녁 8시\~12시)에만 스케줄러를 통해 워커를 깨워두는 전략(Scheduled Ping)이 유효하다.

### **6.3 RP 게임 메카닉 구현: 주사위 굴림 (TRPG 요소)**

LLM은 확률적 텍스트 생성기이므로, "주사위를 굴려줘"라고 요청하면 무작위 숫자가 아닌, 텍스트상 그럴듯한 숫자를 '지어낸다(Hallucination)'. 공정한 게임 로직을 위해 \*\*Function Calling(도구 사용)\*\*을 구현해야 한다.5

* **구현 방식:**  
  1. 시스템 프롬프트에 roll\_dice(sides, count) 함수를 정의한다.  
  2. 사용자가 "공격하겠다"고 말하면, LLM은 텍스트 응답 대신 {"function\_call": {"name": "roll\_dice", "args": {"sides": 20, "count": 1}}} 형태의 JSON을 반환한다.  
  3. EC2 애플리케이션 서버가 이를 감지, Python의 random 모듈로 실제 난수를 생성한다.  
  4. 결과값(예: "15")을 다시 LLM의 컨텍스트에 포함시켜 최종 텍스트("주사위 15가 나왔습니다\! 공격에 성공하여...")를 생성하도록 재요청한다.

## **7\. 결론**

접속자 10명 이하의 RP 챗봇 프로토타입을 위한 최적의 아키텍처는 \*\*"서울 리전의 EC2 t4g.small 컨트롤 타워와 미국 리전의 RunPod Serverless GPU 엔진의 결합"\*\*이다.

이 구조는 다음과 같은 이점을 제공한다:

1. **비용 효율성:** 유휴 GPU 비용을 제거하여 월 유지비를 $1,000대에서 **$150 미만**으로 획기적으로 절감한다.  
2. **성능 최적화:** SGLang의 RadixAttention을 통해 멀티 턴 대화의 처리 속도를 높이고, pgvector를 통해 저비용으로 RAG를 구현한다.  
3. **사용자 경험:** SSE 스트리밍과 FlashBoot를 통해 물리적 거리로 인한 지연 시간을 효과적으로 상쇄한다.

이는 단순한 비용 절감을 넘어, 소규모 팀이 거대 자본 없이도 고품질의 AI 서비스를 실험하고 검증할 수 있는 가장 현실적이고 강력한 기술적 토대이다.

### ---

**부록: 기술 스택 요약 테이블**

| 구성 요소 | 기술 스택 | 선정 이유 | 비고 |
| :---- | :---- | :---- | :---- |
| **App Server** | AWS EC2 (t4g.small) | ARM64 가성비, 서울 리전 지연 최소화 | Ubuntu 22.04 LTS |
| **Inference Engine** | RunPod Serverless \+ SGLang | KV 캐시 재사용, 비용 절감 (초단위 과금) | FlashBoot 활성화 필수 |
| **Database** | PostgreSQL \+ pgvector | 관계형 데이터와 벡터 검색의 통합 관리 | Docker 컨테이너 구동 |
| **Network Protocol** | HTTP/2 \+ SSE | 단방향 텍스트 스트리밍 최적화 | Nginx Reverse Proxy |
| **Backend Lang** | Python (FastAPI/Django) | 비동기 처리(Asyncio) 및 AI 라이브러리 호환 |  |

#### **참고 자료**

1. Top 10 Character AI Alternatives with Apps in 2025 : r/Chatbots \- Reddit, 2월 12, 2026에 액세스, [https://www.reddit.com/r/Chatbots/comments/1hi8ajj/top\_10\_character\_ai\_alternatives\_with\_apps\_in\_2025/](https://www.reddit.com/r/Chatbots/comments/1hi8ajj/top_10_character_ai_alternatives_with_apps_in_2025/)  
2. Gen Z picks Zeta: Korean chatbot overtakes ChatGPT \- Asia News Network, 2월 12, 2026에 액세스, [https://asianews.network/gen-z-picks-zeta-korean-chatbot-overtakes-chatgpt/](https://asianews.network/gen-z-picks-zeta-korean-chatbot-overtakes-chatgpt/)  
3. When to Choose SGLang Over vLLM: Multi-Turn Conversations and KV Cache Reuse, 2월 12, 2026에 액세스, [https://www.runpod.io/blog/sglang-vs-vllm-kv-cache](https://www.runpod.io/blog/sglang-vs-vllm-kv-cache)  
4. How to Run vLLM on Runpod Serverless (Beginner-Friendly Guide), 2월 12, 2026에 액세스, [https://www.runpod.io/blog/run-vllm-on-runpod](https://www.runpod.io/blog/run-vllm-on-runpod)  
5. From Chatbots to Dice Rolls: Researchers Use D\&D to Test AI's Long-term Decision-making Abilities \- UC San Diego Today, 2월 12, 2026에 액세스, [https://today.ucsd.edu/story/from-chatbots-to-dice-rolls-researchers-use-dd-to-test-ais-long-term-decision-making-abilities](https://today.ucsd.edu/story/from-chatbots-to-dice-rolls-researchers-use-dd-to-test-ais-long-term-decision-making-abilities)  
6. I added dice rolls, stats/skills, and date and time tracking to my RP platform \- Reddit, 2월 12, 2026에 액세스, [https://www.reddit.com/r/CharacterAIrunaways/comments/1qtgd5m/i\_added\_dice\_rolls\_statsskills\_and\_date\_and\_time/](https://www.reddit.com/r/CharacterAIrunaways/comments/1qtgd5m/i_added_dice_rolls_statsskills_and_date_and_time/)  
7. Amazon EC2 T4g Instances, 2월 12, 2026에 액세스, [https://aws.amazon.com/ec2/instance-types/t4/](https://aws.amazon.com/ec2/instance-types/t4/)  
8. PostgreSQL on EC2 t4g.nano : r/aws \- Reddit, 2월 12, 2026에 액세스, [https://www.reddit.com/r/aws/comments/ldqh0a/postgresql\_on\_ec2\_t4gnano/](https://www.reddit.com/r/aws/comments/ldqh0a/postgresql_on_ec2_t4gnano/)  
9. t4g.small Pricing and Specs: AWS EC2, 2월 12, 2026에 액세스, [https://costcalc.cloudoptimo.com/aws-pricing-calculator/ec2/t4g.small](https://costcalc.cloudoptimo.com/aws-pricing-calculator/ec2/t4g.small)  
10. What's New for Serverless LLM Usage in RunPod (2025 Update), 2월 12, 2026에 액세스, [https://www.runpod.io/blog/runpod-serverless-llm-2025](https://www.runpod.io/blog/runpod-serverless-llm-2025)  
11. Unpacking Serverless GPU Pricing for AI Deployments \- Runpod, 2월 12, 2026에 액세스, [https://www.runpod.io/articles/guides/serverless-gpu-pricing](https://www.runpod.io/articles/guides/serverless-gpu-pricing)  
12. Overview \- Runpod Documentation, 2월 12, 2026에 액세스, [https://docs.runpod.io/serverless/overview](https://docs.runpod.io/serverless/overview)  
13. AWS Region Latency Matrix, 2월 12, 2026에 액세스, [https://www.cloudping.co/](https://www.cloudping.co/)  
14. SGLang: Efficient Execution of Structured Language Model Programs \- arXiv, 2월 12, 2026에 액세스, [https://arxiv.org/pdf/2312.07104](https://arxiv.org/pdf/2312.07104)  
15. SGLang: Efficient Execution of Structured Language Model Programs \- NIPS, 2월 12, 2026에 액세스, [https://proceedings.neurips.cc/paper\_files/paper/2024/file/724be4472168f31ba1c9ac630f15dec8-Paper-Conference.pdf](https://proceedings.neurips.cc/paper_files/paper/2024/file/724be4472168f31ba1c9ac630f15dec8-Paper-Conference.pdf)  
16. SGLang vs vLLM Part-1 (Benchmark performance ) | by saidinesh pola \- Medium, 2월 12, 2026에 액세스, [https://medium.com/@saidines12/sglang-vs-vllm-part-1-benchmark-performance-3231a41033ca](https://medium.com/@saidines12/sglang-vs-vllm-part-1-benchmark-performance-3231a41033ca)  
17. runpod-workers/worker-sglang: SGLang is fast serving framework for large language models and vision language models. \- GitHub, 2월 12, 2026에 액세스, [https://github.com/runpod-workers/worker-sglang](https://github.com/runpod-workers/worker-sglang)  
18. Hosting low traffic websites for cheap (on AWS) | by Nassir Al-Khishman | Medium, 2월 12, 2026에 액세스, [https://nalkhish.medium.com/hosting-very-low-traffic-web-apps-for-cheap-on-aws-3-year-66f748cd04cf](https://nalkhish.medium.com/hosting-very-low-traffic-web-apps-for-cheap-on-aws-3-year-66f748cd04cf)  
19. Postgre approach for startup : r/aws \- Reddit, 2월 12, 2026에 액세스, [https://www.reddit.com/r/aws/comments/1kwzx84/postgre\_approach\_for\_startup/](https://www.reddit.com/r/aws/comments/1kwzx84/postgre_approach_for_startup/)  
20. Setting up a self-managed PostgreSQL server on AWS EC2 for a small-scale application, 2월 12, 2026에 액세스, [https://ashutoshgngwr.github.io/self-managed-postgresql](https://ashutoshgngwr.github.io/self-managed-postgresql)  
21. Vector database options \- AWS Prescriptive Guidance, 2월 12, 2026에 액세스, [https://docs.aws.amazon.com/prescriptive-guidance/latest/choosing-an-aws-vector-database-for-rag-use-cases/vector-db-options.html](https://docs.aws.amazon.com/prescriptive-guidance/latest/choosing-an-aws-vector-database-for-rag-use-cases/vector-db-options.html)  
22. Supercharging vector search performance and relevance with pgvector 0.8.0 on Amazon Aurora PostgreSQL | AWS Database Blog, 2월 12, 2026에 액세스, [https://aws.amazon.com/blogs/database/supercharging-vector-search-performance-and-relevance-with-pgvector-0-8-0-on-amazon-aurora-postgresql/](https://aws.amazon.com/blogs/database/supercharging-vector-search-performance-and-relevance-with-pgvector-0-8-0-on-amazon-aurora-postgresql/)  
23. Why vector databases are a scam. : r/vectordatabase \- Reddit, 2월 12, 2026에 액세스, [https://www.reddit.com/r/vectordatabase/comments/1k9ai4h/why\_vector\_databases\_are\_a\_scam/](https://www.reddit.com/r/vectordatabase/comments/1k9ai4h/why_vector_databases_are_a_scam/)  
24. Postgres Vector Search with pgvector: Benchmarks, Costs, and Reality Check \- Medium, 2월 12, 2026에 액세스, [https://medium.com/@DataCraft-Innovations/postgres-vector-search-with-pgvector-benchmarks-costs-and-reality-check-f839a4d2b66f](https://medium.com/@DataCraft-Innovations/postgres-vector-search-with-pgvector-benchmarks-costs-and-reality-check-f839a4d2b66f)  
25. World Info | docs.ST.app \- SillyTavern Documentation, 2월 12, 2026에 액세스, [https://docs.sillytavern.app/usage/core-concepts/worldinfo/](https://docs.sillytavern.app/usage/core-concepts/worldinfo/)  
26. How to enhance RAG chatbot performance by refining a reranking model \- Labelbox, 2월 12, 2026에 액세스, [https://labelbox.com/guides/how-to-enhance-rag-chatbot-performance-through-by-refining-reranking-models/](https://labelbox.com/guides/how-to-enhance-rag-chatbot-performance-through-by-refining-reranking-models/)  
27. asg017/sqlite-vss: A SQLite extension for efficient vector ... \- GitHub, 2월 12, 2026에 액세스, [https://github.com/asg017/sqlite-vss](https://github.com/asg017/sqlite-vss)  
28. You may not need pg\_vector, sqlite-vss, etc. \- DEV Community, 2월 12, 2026에 액세스, [https://dev.to/nvahalik/you-may-not-need-pgvector-sqlite-vss-etc-e6j](https://dev.to/nvahalik/you-may-not-need-pgvector-sqlite-vss-etc-e6j)  
29. Pricing \- Runpod Documentation, 2월 12, 2026에 액세스, [https://docs.runpod.io/serverless/pricing](https://docs.runpod.io/serverless/pricing)  
30. Runpod GPU pricing: A complete breakdown and platform comparison | Blog \- Northflank, 2월 12, 2026에 액세스, [https://northflank.com/blog/runpod-gpu-pricing](https://northflank.com/blog/runpod-gpu-pricing)  
31. Serverless GPU Deployment vs. Pods for Your AI Workload \- Runpod, 2월 12, 2026에 액세스, [https://www.runpod.io/articles/comparison/serverless-gpu-deployment-vs-pods](https://www.runpod.io/articles/comparison/serverless-gpu-deployment-vs-pods)  
32. Building Real-Time AI Chat: Infrastructure for WebSockets, LLM Streaming, and Session Management \- Render, 2월 12, 2026에 액세스, [https://render.com/articles/real-time-ai-chat-websockets-infrastructure](https://render.com/articles/real-time-ai-chat-websockets-infrastructure)  
33. Server-Sent Events Beat WebSockets for 95% of Real-Time Apps (Here's Why), 2월 12, 2026에 액세스, [https://dev.to/polliog/server-sent-events-beat-websockets-for-95-of-real-time-apps-heres-why-a4l](https://dev.to/polliog/server-sent-events-beat-websockets-for-95-of-real-time-apps-heres-why-a4l)  
34. Introducing FlashBoot: 1-Second Serverless Cold-Start | Runpod Blog, 2월 12, 2026에 액세스, [https://www.runpod.io/blog/introducing-flashboot-serverless-cold-start](https://www.runpod.io/blog/introducing-flashboot-serverless-cold-start)  
35. Function Calling with LLMs \- Prompt Engineering Guide, 2월 12, 2026에 액세스, [https://www.promptingguide.ai/applications/function\_calling](https://www.promptingguide.ai/applications/function_calling)

[image1]: <data:image/png;base64,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>

[image2]: <data:image/png;base64,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>