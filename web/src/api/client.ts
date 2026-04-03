import type { ChatRequest, ChatResponse, SparkApp, YunikornQueue, Session, SessionDetail } from '../types';

const API_BASE = '/api/v1';

// ============ Chat API ============

export async function sendMessage(request: ChatRequest): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || 'Failed to send message');
  }

  return response.json();
}

export interface StreamCallbacks {
  onStart?: (sessionId: string) => void;
  onChunk?: (text: string) => void;
  onData?: (structuredData: unknown) => void;
  onDone?: (sessionId: string) => void;
  onError?: (error: string) => void;
}

export async function sendMessageStream(
  request: ChatRequest,
  callbacks: StreamCallbacks
): Promise<void> {
  const response = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    callbacks.onError?.(error.detail || 'Failed to send message');
    throw new Error(error.detail || 'Failed to send message');
  }

  const reader = response.body?.getReader();
  if (!reader) {
    callbacks.onError?.('No response body');
    return;
  }

  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // 解析 SSE 事件
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    let currentEvent = '';

    for (const line of lines) {
      if (line.startsWith('event: ')) {
        currentEvent = line.slice(7).trim();
        continue;
      }

      if (line.startsWith('data: ')) {
        const dataStr = line.slice(6);
        try {
          const data = JSON.parse(dataStr);

          // 根据事件类型处理
          if (currentEvent === 'start' && data.session_id) {
            callbacks.onStart?.(data.session_id);
          } else if (currentEvent === 'chunk' && data.text) {
            callbacks.onChunk?.(data.text);
          } else if (currentEvent === 'data' && data.structured_data) {
            callbacks.onData?.(data.structured_data);
          } else if (currentEvent === 'done' && data.session_id) {
            callbacks.onDone?.(data.session_id);
          } else if (currentEvent === 'error' && data.error) {
            callbacks.onError?.(data.error);
          }
        } catch {
          // 忽略解析错误
        }
      }
    }
  }
}

// ============ Session API ============

export async function listSessions(userId?: string): Promise<Session[]> {
  const params = userId ? `?user_id=${userId}` : '';
  const response = await fetch(`${API_BASE}/chat/sessions${params}`);

  if (!response.ok) {
    throw new Error('Failed to list sessions');
  }

  const data = await response.json();
  return data.sessions.map((s: Session) => ({
    ...s,
    created_at: new Date(s.created_at),
  }));
}

export async function getSession(sessionId: string): Promise<SessionDetail> {
  const response = await fetch(`${API_BASE}/chat/sessions/${sessionId}`);

  if (!response.ok) {
    throw new Error('Failed to get session');
  }

  const data = await response.json();
  return {
    ...data,
    created_at: new Date(data.created_at),
  };
}

export async function deleteSession(sessionId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/chat/sessions/${sessionId}`, {
    method: 'DELETE',
  });

  if (!response.ok) {
    throw new Error('Failed to delete session');
  }
}

// ============ Spark API ============

export async function getSparkApps(namespace?: string, status?: string): Promise<SparkApp[]> {
  const params = new URLSearchParams();
  if (namespace) params.append('namespace', namespace);
  if (status) params.append('status', status);

  const response = await fetch(`${API_BASE}/spark/apps?${params}`);
  if (!response.ok) throw new Error('Failed to fetch Spark apps');

  const data = await response.json();
  return data.applications;
}

export async function getSparkApp(name: string, namespace?: string): Promise<SparkApp> {
  const params = namespace ? `?namespace=${namespace}` : '';
  const response = await fetch(`${API_BASE}/spark/apps/${name}${params}`);

  if (!response.ok) throw new Error('Failed to fetch Spark app');

  return response.json();
}

export async function getSparkAppLogs(
  name: string,
  podType: 'driver' | 'executor' = 'driver',
  namespace?: string
): Promise<{ logs: string; pod_name: string }> {
  const params = new URLSearchParams({ pod_type: podType });
  if (namespace) params.append('namespace', namespace);

  const response = await fetch(`${API_BASE}/spark/apps/${name}/logs?${params}`);
  if (!response.ok) throw new Error('Failed to fetch logs');

  return response.json();
}

// ============ Queue API ============

export async function getQueues(partition: string = 'default'): Promise<YunikornQueue[]> {
  const response = await fetch(`${API_BASE}/queues?partition=${partition}`);
  if (!response.ok) throw new Error('Failed to fetch queues');

  const data = await response.json();
  return data.queues;
}

export async function getQueue(name: string, partition: string = 'default'): Promise<unknown> {
  const response = await fetch(`${API_BASE}/queues/${name}?partition=${partition}`);
  if (!response.ok) throw new Error('Failed to fetch queue');

  return response.json();
}

// ============ Health API ============

export async function getHealth(): Promise<{ status: string }> {
  const response = await fetch('/health');
  if (!response.ok) throw new Error('Health check failed');

  return response.json();
}