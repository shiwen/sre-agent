export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
}

export interface ChatRequest {
  message: string
  session_id?: string
  context?: Record<string, unknown>
}

export interface ChatResponse {
  response: string
  session_id: string
  actions?: Action[]
}

export interface Action {
  type: string
  description: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  result?: Record<string, unknown>
}

export interface SparkApplication {
  name: string
  namespace: string
  status: string
  driver_pod?: string
  executor_count?: number
  start_time?: string
  end_time?: string
}

export interface QueueInfo {
  name: string
  capacity: number
  used_capacity: number
  running_applications: number
  pending_applications: number
}

export interface PatrolReport {
  timestamp: string
  summary: string
  issues: Issue[]
  recommendations: string[]
}

export interface Issue {
  severity: 'low' | 'medium' | 'high' | 'critical'
  type: string
  description: string
  resource?: string
  suggested_action?: string
}