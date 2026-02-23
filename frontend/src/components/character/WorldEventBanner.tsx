'use client';

import { useEffect } from 'react';
import { Globe, Sparkles, AlertTriangle, BookOpen } from 'lucide-react';
import { useWorldEventStore } from '@/stores/worldEventStore';
import type { WorldEvent } from '@/stores/worldEventStore';

const EVENT_ICONS: Record<string, typeof Globe> = {
  world_state: Globe,
  seasonal: Sparkles,
  crisis: AlertTriangle,
  lore_update: BookOpen,
};

const EVENT_COLORS: Record<string, string> = {
  world_state: 'border-primary/30 bg-primary/5',
  seasonal: 'border-yellow-400/30 bg-yellow-50/50',
  crisis: 'border-danger/30 bg-danger/5',
  lore_update: 'border-purple-400/30 bg-purple-50/50',
};

export function WorldEventBanner() {
  const { activeEvents, fetchActive } = useWorldEventStore();

  useEffect(() => {
    fetchActive();
  }, [fetchActive]);

  if (activeEvents.length === 0) return null;

  return (
    <div className="flex flex-col gap-2 mb-4">
      {activeEvents.map((event) => (
        <EventCard key={event.id} event={event} />
      ))}
    </div>
  );
}

function EventCard({ event }: { event: WorldEvent }) {
  const Icon = EVENT_ICONS[event.event_type] || Globe;
  const colorClass = EVENT_COLORS[event.event_type] || 'border-border bg-bg-surface';

  return (
    <div className={`flex items-start gap-3 p-3 rounded-lg border ${colorClass}`}>
      <Icon size={16} className="text-text-muted mt-0.5 flex-shrink-0" />
      <div className="min-w-0">
        <span className="text-xs font-bold text-text">{event.title}</span>
        <p className="text-xs text-text-secondary mt-0.5 line-clamp-2">{event.content}</p>
      </div>
    </div>
  );
}
