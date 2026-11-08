export interface HealthResponse {
  status: 'healthy' | 'unhealthy' | string
  service: string
  environment: string
  version: string
}

export interface DatabaseHealthResponse {
  status: 'healthy' | 'unhealthy' | string
  database: 'connected' | 'disconnected' | string
  dialect?: string
  latency_ms?: number
  error?: string | null
}
