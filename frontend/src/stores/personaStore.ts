import { create } from 'zustand';

type Persona = {
  id: string;
  displayName: string;
  ageRating: 'all' | '15+' | '18+';
  visibility: string;
  moderationStatus: string;
  live2dModelId?: string;
  backgroundImageUrl?: string;
};

type PersonaState = {
  personas: Persona[];
  selectedPersona: Persona | null;
  setPersonas: (personas: Persona[]) => void;
  selectPersona: (persona: Persona | null) => void;
};

export const usePersonaStore = create<PersonaState>((set) => ({
  personas: [],
  selectedPersona: null,
  setPersonas: (personas) => set({ personas }),
  selectPersona: (persona) => set({ selectedPersona: persona }),
}));
