export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  structuredData?: StructuredData;
}

export interface Session {
  id: string;
  user_id?: string;
  created_at: Date;
  message_count?: number;
  status?: string;
}

export interface SessionDetail {
  id: string;
  user_id?: string;
  created_at: Date;
  messages: Array<{ role: string; content: string }>;
  summary?: string;
  status?: string;
}

export interface ChatRequest {
  message: string;
  conversation_id?: string;
  session_id?: string;
}

export interface ChatResponse {
  response: string;
  conversation_id?: string;
  session_id?: string;
  structured_data?: StructuredData;
}

export interface HealthResponse {
  status: string;
}

export interface StructuredData {
  type: 'spark_apps' | 'yunikorn_queues' | 'k8s_resources' | 'table' | 'patrol_report' | 'error_analysis';
  data: SparkApp[] | YunikornQueue[] | PatrolReport | ErrorAnalysis | Record<string, unknown>[];
  columns?: string[];
}

export interface SparkApp {
  app_id?: string;
  app_name?: string;
  name?: string;
  namespace?: string;
  state?: string;
  status?: string;
  driver_pod?: string;
  executor_count?: number;
  start_time?: string;
  end_time?: string;
  duration?: number;
}

export interface YunikornQueue {
  queue_name?: string;
  name?: string;
  status?: string;
  capacity?: number;
  max_capacity?: number;
  used_capacity?: number;
  running_apps?: number;
  running_applications?: number;
  pending_applications?: number;
}

export interface PatrolReport {
  timestamp: string;
  summary: string;
  issues: Issue[];
  recommendations: string[];
}

export interface Issue {
  severity: 'low' | 'medium' | 'high' | 'critical';
  type: string;
  description: string;
  resource?: string;
  suggested_action?: string;
}

export interface ErrorAnalysis {
  error_type: string;
  root_cause?: string;
  affected_apps?: string[];
  suggested_fix?: string;
}