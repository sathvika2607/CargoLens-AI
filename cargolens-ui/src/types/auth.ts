export type UserRole = 'DOCUMENTATION_EXECUTIVE' | 'DOCUMENTATION_MANAGER'

export interface User {
  id: string
  full_name: string
  email: string
  role: UserRole
  is_active: boolean
  created_at: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: User
}
