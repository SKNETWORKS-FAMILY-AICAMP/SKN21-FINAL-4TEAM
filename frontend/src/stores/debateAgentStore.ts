import { create } from 'zustand';
import { api } from '@/lib/api';

type DebateAgent = {
  id: string;
  owner_id: string;
  name: string;
  description: string | null;
  provider: string;
  model_id: string;
  image_url: string | null;
  elo_rating: number;
  wins: number;
  losses: number;
  draws: number;
  is_active: boolean;
  is_connected: boolean;
  template_id: string | null;
  customizations: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

type AgentVersion = {
  id: string;
  version_number: number;
  version_tag: string | null;
  system_prompt: string;
  parameters: Record<string, unknown> | null;
  wins: number;
  losses: number;
  draws: number;
  created_at: string;
};

// 템플릿 커스터마이징 스키마 타입
type SliderField = {
  key: string;
  label: string;
  min: number;
  max: number;
  default: number;
  description: string;
};

type SelectOption = { value: string; label: string };

type SelectField = {
  key: string;
  label: string;
  options: SelectOption[];
  default: string;
};

type FreeTextField = {
  key: string;
  label: string;
  placeholder: string;
  max_length: number;
};

type CustomizationSchema = {
  sliders: SliderField[];
  selects: SelectField[];
  free_text?: FreeTextField;
};

type AgentTemplate = {
  id: string;
  slug: string;
  display_name: string;
  description: string | null;
  icon: string | null;
  customization_schema: CustomizationSchema;
  default_values: Record<string, unknown>;
  sort_order: number;
  is_active: boolean;
};

type CreateAgentPayload = {
  name: string;
  description?: string;
  provider: string;
  model_id?: string;
  api_key?: string;
  system_prompt?: string;
  version_tag?: string;
  parameters?: Record<string, unknown>;
  image_url?: string;
  // 템플릿 기반 생성 필드
  template_id?: string;
  customizations?: Record<string, unknown>;
  enable_free_text?: boolean;
};

type UpdateAgentPayload = Partial<CreateAgentPayload>;

type DebateAgentState = {
  agents: DebateAgent[];
  templates: AgentTemplate[];
  loading: boolean;
  fetchMyAgents: () => Promise<void>;
  fetchTemplates: () => Promise<void>;
  createAgent: (data: CreateAgentPayload) => Promise<DebateAgent>;
  updateAgent: (id: string, data: UpdateAgentPayload) => Promise<DebateAgent>;
  fetchVersions: (agentId: string) => Promise<AgentVersion[]>;
};

export const useDebateAgentStore = create<DebateAgentState>((set) => ({
  agents: [],
  templates: [],
  loading: false,
  fetchMyAgents: async () => {
    set({ loading: true });
    try {
      const data = await api.get<DebateAgent[]>('/agents/me');
      set({ agents: data });
    } catch (err) {
      console.error('Failed to fetch agents:', err);
    } finally {
      set({ loading: false });
    }
  },
  fetchTemplates: async () => {
    try {
      const data = await api.get<AgentTemplate[]>('/agents/templates');
      set({ templates: data });
    } catch (err) {
      console.error('Failed to fetch templates:', err);
    }
  },
  createAgent: async (data) => {
    const agent = await api.post<DebateAgent>('/agents', data);
    set((s) => ({ agents: [agent, ...s.agents] }));
    return agent;
  },
  updateAgent: async (id, data) => {
    const agent = await api.put<DebateAgent>(`/agents/${id}`, data);
    set((s) => ({ agents: s.agents.map((a) => (a.id === id ? agent : a)) }));
    return agent;
  },
  fetchVersions: async (agentId) => {
    return api.get<AgentVersion[]>(`/agents/${agentId}/versions`);
  },
}));

export type {
  DebateAgent,
  AgentVersion,
  AgentTemplate,
  CustomizationSchema,
  SliderField,
  SelectField,
  FreeTextField,
  CreateAgentPayload,
};
