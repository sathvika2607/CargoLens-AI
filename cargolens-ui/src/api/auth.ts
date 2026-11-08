import { apiClient, setAuthToken } from './client'
import { LoginResponse, User } from '../types/auth'

export const login = async (email: string, password: string): Promise<LoginResponse> => {
  const response = await apiClient.post<LoginResponse>('/api/v1/auth/login', {
    email,
    password,
  })
  setAuthToken(response.data.access_token)
  return response.data
}

export const refreshToken = async (): Promise<LoginResponse> => {
  const response = await apiClient.post<LoginResponse>('/api/v1/auth/refresh', {})
  setAuthToken(response.data.access_token)
  return response.data
}

export const logout = async (): Promise<void> => {
  try {
    await apiClient.post('/api/v1/auth/logout')
  } finally {
    setAuthToken(null)
  }
}

export const getMe = async (): Promise<User> => {
  const response = await apiClient.get<User>('/api/v1/auth/me')
  return response.data
}

export const register = async (payload: {
  full_name: string
  email: string
  password: string
  confirm_password?: string
}): Promise<User> => {
  const response = await apiClient.post<User>('/api/v1/auth/register', payload)
  return response.data
}

export const bootstrapManager = async (payload: {
  full_name: string
  email: string
  password: string
  bootstrap_secret: string
}): Promise<User> => {
  const response = await apiClient.post<User>('/api/v1/auth/bootstrap-manager', payload)
  return response.data
}
