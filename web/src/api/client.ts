import type { ChatRequest, ChatResponse, HealthResponse, SparkApp, YunikornQueue } from '../types';

const API_BASE = '/api/v1';

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

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch('/health');
  if (!response.ok) throw new Error('Health check failed');
  return response.json();
}

export async function getSparkApps(): Promise<SparkApp[]> {
  const response = await fetch(`${API_BASE}/spark/apps`);
  if (!response.ok) throw new Error('Failed to fetch Spark apps');
  return response.json();
}

export async function getYunikornQueues(): Promise<YunikornQueue[]> {
  const response = await fetch(`${API_BASE}/yunikorn/queues`);
  if (!response.ok) throw new Error('Failed to fetch queues');
  return response.json();
}