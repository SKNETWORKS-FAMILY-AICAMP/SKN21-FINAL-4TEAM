import { create } from 'zustand';
import { api } from '@/lib/api';

type DebateAgent = {
  id: string;
  owner_id: string;
  name: string;
  description: string | null;
  provider: string;
  model_id: string;
  elo_rating: number;
  wins: number;
  losses: number;
  draws: number;
  is_active: boolean;
  is_connected: boolean;
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

type CreateAgentPayload = {
  name: string;
  description?: string;
  provider: string;
  model_id?: string;
  api_key?: string;
  system_prompt: string;
  version_tag?: string;
  parameters?: Record<string, unknown>;
};

type UpdateAgentPayload = Partial<CreateAgentPayload>;

type DebateAgentState = {
  agents: DebateAgent[];
  loading: boolean;
  fetchMyAgents: () => Promise<void>;
  createAgent: (data: CreateAgentPayload) => Promise<DebateAgent>;
  updateAgent: (id: string, data: UpdateAgentPayload) => Promise<DebateAgent>;
  fetchVersions: (agentId: string) => Promise<AgentVersion[]>;
};

export const useDebateAgentStore = create<DebateAgentState>((set) => ({
  agents: [],
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

export type { DebateAgent, AgentVersion, CreateAgentPayload };
