type SSEOptions = {
  onMessage: (data: string) => void;
  onError?: (error: Event) => void;
  onClose?: () => void;
};

export function connectSSE(url: string, options: SSEOptions): () => void {
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;

  const eventSource = new EventSource(`${url}${token ? `?token=${token}` : ''}`);

  eventSource.onmessage = (event) => {
    options.onMessage(event.data);
  };

  eventSource.onerror = (event) => {
    options.onError?.(event);
    eventSource.close();
    options.onClose?.();
  };

  // 연결 종료 함수 반환
  return () => {
    eventSource.close();
    options.onClose?.();
  };
}
