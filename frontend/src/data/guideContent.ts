export type GuideSection = {
  title: string;
  body: string;
};

export type GuideContent = {
  banner: string;
  sections: GuideSection[];
};

/** 사용자 화면 가이드 */
const userGuides: Record<string, GuideContent> = {
  '/personas': {
    banner: '다양한 AI 캐릭터를 탐색하고 대화를 시작해 보세요!',
    sections: [
      {
        title: '챗봇 검색',
        body: '상단 검색바에 키워드를 입력하면 캐릭터 이름이나 소개에서 일치하는 결과를 찾아줍니다.',
      },
      {
        title: '태그 필터',
        body: '태그 칩을 클릭하면 해당 장르/성격의 캐릭터만 필터링됩니다. 여러 태그를 조합할 수 있어요.',
      },
      {
        title: '정렬',
        body: '인기순·최신순·이름순으로 정렬할 수 있습니다. 인기순은 대화 수 기준입니다.',
      },
      {
        title: '즐겨찾기',
        body: '카드의 하트 아이콘을 누르면 즐겨찾기에 추가됩니다. 사이드바의 "즐겨찾기"에서 모아볼 수 있어요.',
      },
      {
        title: '연령등급 배지',
        body: '[전체]·[15+]·[18+] 배지로 연령등급을 확인하세요. 18+ 캐릭터는 성인인증 후 이용 가능합니다.',
      },
      {
        title: '대화 시작',
        body: '카드를 클릭하면 새 대화 세션이 생성되고 채팅 화면으로 이동합니다.',
      },
    ],
  },

  '/personas/create': {
    banner: '나만의 AI 캐릭터를 만들어 보세요! 성격, 말투, 세계관을 자유롭게 설정할 수 있습니다.',
    sections: [
      {
        title: '기본 정보',
        body: '캐릭터 이름과 소개를 입력하세요. 소개는 탐색 페이지의 카드에 표시됩니다.',
      },
      {
        title: '시스템 프롬프트',
        body: '캐릭터의 성격, 말투, 행동 지침을 자유롭게 적어주세요. AI가 이 설정을 따라 대화합니다.',
      },
      {
        title: '인사말',
        body: '대화 시작 시 캐릭터가 보내는 첫 메시지입니다. 비워두면 사용자의 첫 메시지를 기다립니다.',
      },
      {
        title: '시나리오',
        body: '대화의 배경 상황을 설정하세요. 예: "조용한 카페에서 우연히 만난 상황"',
      },
      {
        title: '예시 대화',
        body: '캐릭터의 말투를 보여주는 예시 대화를 추가하면 AI가 더 자연스럽게 대화합니다.',
      },
      {
        title: '태그',
        body: '캐릭터를 설명하는 태그를 추가하세요. 다른 사용자가 태그로 검색할 수 있습니다.',
      },
      {
        title: 'Live2D & 배경',
        body: 'Live2D 모델과 배경 이미지를 선택하면 채팅 화면에서 캐릭터가 표정으로 반응합니다.',
      },
      {
        title: '연령등급',
        body: '콘텐츠 수위에 따라 전체·15+·18+를 선택하세요. 18+는 성인인증이 필요합니다.',
      },
    ],
  },

  '/personas/edit': {
    banner: '캐릭터 설정을 수정하고 저장하세요.',
    sections: [
      {
        title: '수정 방법',
        body: '각 필드를 수정한 후 하단의 "저장" 버튼을 누르세요. 변경사항은 새로운 대화부터 적용됩니다.',
      },
      {
        title: '공개 범위',
        body: 'private(나만), public(전체 공개), unlisted(링크 공유)로 설정할 수 있습니다.',
      },
    ],
  },

  '/personas/lorebook': {
    banner: '로어북으로 캐릭터의 세계관을 더 풍부하게 만들어 보세요.',
    sections: [
      {
        title: '로어북이란?',
        body: '캐릭터가 알고 있어야 할 세계관 설정, 인물 관계, 장소 정보 등을 정의하는 항목입니다.',
      },
      {
        title: '항목 추가',
        body: '"추가" 버튼으로 새 항목을 만드세요. 제목, 키워드, 본문을 입력합니다.',
      },
      {
        title: '키워드 트리거',
        body: '대화에서 키워드가 언급되면 해당 로어북 항목이 AI에게 자동으로 전달됩니다.',
      },
    ],
  },

  '/chat': {
    banner: '캐릭터와 자유롭게 대화해 보세요! 메시지 위에 마우스를 올리면 다양한 액션을 사용할 수 있어요.',
    sections: [
      {
        title: '메시지 보내기',
        body: '하단 입력창에 메시지를 입력하고 Enter를 누르세요. Shift+Enter로 줄바꿈할 수 있습니다.',
      },
      {
        title: '메시지 재생성',
        body: 'AI 메시지에 마우스를 올리면 나타나는 🔄 버튼으로 다른 응답을 받을 수 있습니다.',
      },
      {
        title: '메시지 수정',
        body: '내 메시지의 ✏️ 버튼으로 보낸 메시지를 수정할 수 있습니다.',
      },
      {
        title: '응답 탐색 (브랜칭)',
        body: '재생성한 응답들은 ◀ ▶ 버튼으로 탐색할 수 있습니다. 이전 응답도 다시 볼 수 있어요.',
      },
      {
        title: 'Live2D 캐릭터',
        body: '캐릭터가 대화 감정에 따라 표정과 모션이 변합니다.',
      },
      {
        title: '호감도',
        body: '상단의 호감도 바로 캐릭터와의 관계 진행도를 확인하세요. 대화할수록 친밀도가 올라갑니다.',
      },
    ],
  },

  '/sessions': {
    banner: '진행 중인 대화를 관리하세요. 세션을 고정하거나 제목을 변경할 수 있어요.',
    sections: [
      {
        title: '세션 목록',
        body: '가장 최근 대화가 위에 표시됩니다. 클릭하면 해당 대화로 이동합니다.',
      },
      {
        title: '세션 고정',
        body: '📌 버튼으로 중요한 대화를 상단에 고정할 수 있습니다.',
      },
      {
        title: '제목 편집',
        body: '세션 제목을 클릭하면 원하는 이름으로 변경할 수 있습니다.',
      },
      {
        title: '세션 삭제/아카이브',
        body: '필요 없는 대화는 삭제하거나 아카이브로 보관할 수 있습니다.',
      },
    ],
  },

  '/favorites': {
    banner: '즐겨찾기한 캐릭터를 한눈에 확인하세요.',
    sections: [
      {
        title: '즐겨찾기 관리',
        body: '하트 아이콘을 다시 누르면 즐겨찾기가 해제됩니다.',
      },
      {
        title: '바로 대화하기',
        body: '카드를 클릭하면 바로 새 대화를 시작할 수 있습니다.',
      },
    ],
  },

  '/relationships': {
    banner: '캐릭터들과의 관계를 확인하세요. 대화할수록 관계가 발전합니다.',
    sections: [
      {
        title: '관계 단계',
        body: '낯선 사이 → 아는 사이 → 친구 → 절친 → 썸 → 연인 → 소울메이트 순으로 발전합니다.',
      },
      {
        title: '호감도',
        body: '프로그레스 바가 0~1000 범위로 표시됩니다. 긍정적인 대화를 하면 호감도가 올라가요.',
      },
      {
        title: '관계 보기',
        body: '각 카드를 클릭하면 상세한 관계 정보와 마지막 대화 시간을 확인할 수 있습니다.',
      },
    ],
  },

  '/notifications': {
    banner: '알림을 확인하고 관리하세요.',
    sections: [
      {
        title: '알림 종류',
        body: '페르소나 승인/차단, 관계 변화, 시스템 공지 등 다양한 알림을 받을 수 있습니다.',
      },
      {
        title: '읽음 처리',
        body: '알림을 클릭하면 읽음 처리됩니다. "전체 읽음" 버튼으로 한번에 처리할 수도 있어요.',
      },
    ],
  },

  '/community': {
    banner: '다른 사용자들과 캐릭터에 대해 이야기를 나눠보세요.',
    sections: [
      {
        title: '게시글 작성',
        body: '"글쓰기" 버튼으로 새 게시글을 작성할 수 있습니다.',
      },
      {
        title: '카테고리',
        body: '카테고리별로 게시글을 필터링할 수 있습니다.',
      },
      {
        title: '좋아요 & 댓글',
        body: '게시글에 좋아요를 누르거나 댓글을 달 수 있습니다.',
      },
    ],
  },

  '/mypage': {
    banner: '프로필, 설정, 사용량 등을 한 곳에서 관리하세요.',
    sections: [
      {
        title: '내 정보',
        body: '닉네임, 프로필 이미지 등 기본 정보를 수정할 수 있습니다.',
      },
      {
        title: '설정',
        body: 'LLM 모델 선택, 성인인증 등 앱 설정을 변경할 수 있습니다.',
      },
      {
        title: '사용량',
        body: '일별·월별 토큰 사용량과 비용을 차트로 확인할 수 있습니다.',
      },
      {
        title: '내 캐릭터',
        body: '대화에서 사용할 나의 페르소나를 생성하고 관리합니다. 기본 페르소나를 설정할 수 있어요.',
      },
      {
        title: '기억',
        body: 'AI가 기억하는 정보를 확인하고 삭제하거나 직접 추가할 수 있습니다.',
      },
      {
        title: '크리에이터',
        body: '내가 만든 캐릭터의 대화 수, 좋아요 수 등 통계를 확인할 수 있습니다.',
      },
    ],
  },
};

/** 관리자 화면 가이드 */
const adminGuides: Record<string, GuideContent> = {
  '/admin': {
    banner: '관리자 대시보드에 오신 것을 환영합니다. 플랫폼 현황을 한눈에 파악하세요.',
    sections: [
      {
        title: '통계 카드',
        body: '총 사용자, 활성 세션, 페르소나 수 등 핵심 지표를 실시간으로 확인합니다.',
      },
      {
        title: '최근 활동',
        body: '최근 가입한 사용자와 생성된 페르소나를 빠르게 확인할 수 있습니다.',
      },
    ],
  },

  '/admin/users': {
    banner: '사용자 목록을 관리하세요. 역할 변경, 계정 상태 관리가 가능합니다.',
    sections: [
      {
        title: '사용자 검색',
        body: '닉네임이나 이메일로 사용자를 검색할 수 있습니다.',
      },
      {
        title: '역할 변경',
        body: '사용자의 역할을 user/admin으로 변경할 수 있습니다.',
      },
      {
        title: '계정 상태',
        body: '계정을 활성/비활성 전환하여 접근을 제어합니다.',
      },
    ],
  },

  '/admin/personas': {
    banner: '사용자가 생성한 페르소나를 검토하고 승인/차단하세요.',
    sections: [
      {
        title: '모더레이션',
        body: '대기 중인 페르소나를 검토하고 승인 또는 차단할 수 있습니다.',
      },
      {
        title: '연령등급 검수',
        body: '사용자가 설정한 연령등급이 콘텐츠에 적합한지 확인하세요.',
      },
      {
        title: '상태 필터',
        body: 'pending/approved/blocked 상태별로 필터링할 수 있습니다.',
      },
    ],
  },

  '/admin/content': {
    banner: '웹툰, Live2D 모델, 배경 에셋을 관리하세요.',
    sections: [
      {
        title: '웹툰 관리',
        body: '웹툰과 회차 데이터를 추가, 수정, 삭제할 수 있습니다.',
      },
      {
        title: 'Live2D 모델',
        body: 'Live2D 모델 에셋을 업로드하고 감정→모션 매핑을 설정합니다.',
      },
      {
        title: '배경 이미지',
        body: '채팅 화면에서 사용할 배경 이미지를 관리합니다.',
      },
    ],
  },

  '/admin/models': {
    banner: 'LLM 모델을 등록하고 비용/활성 상태를 관리하세요.',
    sections: [
      {
        title: '모델 등록',
        body: '새 LLM 모델의 provider, model_id, 비용 단가 등을 등록합니다.',
      },
      {
        title: '활성/비활성',
        body: '토글로 모델을 활성화하거나 비활성화할 수 있습니다.',
      },
      {
        title: '비용 설정',
        body: '입력/출력 토큰당 비용을 설정합니다. 사용자에게 비용이 안내됩니다.',
      },
    ],
  },

  '/admin/usage': {
    banner: '전체 토큰 사용량과 과금 현황을 모니터링하세요.',
    sections: [
      {
        title: '전체 통계',
        body: '전체 사용자의 일별/월별 토큰 사용량과 비용 합계를 확인합니다.',
      },
      {
        title: '사용자별 사용량',
        body: '개별 사용자의 사용량을 조회하고 비교할 수 있습니다.',
      },
      {
        title: '모델별 분석',
        body: '어떤 모델이 가장 많이 사용되는지 분석할 수 있습니다.',
      },
    ],
  },

  '/admin/policy': {
    banner: '플랫폼 정책을 설정하세요. 연령등급 기준, 안전 규칙, 금칙어를 관리합니다.',
    sections: [
      {
        title: '연령등급 기준',
        body: '각 연령등급의 허용 범위를 설정합니다.',
      },
      {
        title: '안전 규칙',
        body: 'AI 캐릭터가 따라야 할 기본 안전 규칙을 정의합니다.',
      },
      {
        title: '금칙어',
        body: '차단할 단어 목록을 관리합니다.',
      },
    ],
  },

  '/admin/monitoring': {
    banner: '시스템 상태와 로그를 실시간으로 모니터링하세요.',
    sections: [
      {
        title: '세션/메시지 통계',
        body: '활성 세션 수, 분당 메시지 수 등을 실시간으로 확인합니다.',
      },
      {
        title: '정책 위반 로그',
        body: '정책 위반이 감지된 요청 로그를 조회할 수 있습니다.',
      },
      {
        title: '시스템 헬스',
        body: 'DB, Redis, LLM API 연결 상태를 확인합니다.',
      },
    ],
  },
};

/**
 * 현재 경로에 맞는 가이드 콘텐츠를 반환합니다.
 * 동적 세그먼트(UUID 등)는 패턴 매칭으로 처리합니다.
 */
export function getGuideForPath(pathname: string): GuideContent | null {
  // 정확히 일치하는 경우
  const exact = { ...userGuides, ...adminGuides }[pathname];
  if (exact) return exact;

  // 동적 라우트 패턴 매칭
  if (/^\/chat\/[^/]+$/.test(pathname)) return userGuides['/chat'];
  if (/^\/personas\/[^/]+\/edit$/.test(pathname)) return userGuides['/personas/edit'];
  if (/^\/personas\/[^/]+\/lorebook$/.test(pathname)) return userGuides['/personas/lorebook'];
  if (/^\/community\/post\/[^/]+$/.test(pathname)) return userGuides['/community'];

  return null;
}
