import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { User } from '../types/auth'
import * as authApi from '../api/auth'
import { setAuthToken } from '../api/client'

interface AuthContextType {
  user: User | null
  isAuthenticated: boolean
  isManager: boolean
  isExecutive: boolean
  isLoading: boolean
  login: (email: string, pass: string) => Promise<User>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState<boolean>(true)

  let queryClient: ReturnType<typeof useQueryClient> | null = null
  try {
    queryClient = useQueryClient()
  } catch {
    queryClient = null
  }

  // Try silent refresh on initial mount to restore session if valid cookie exists
  useEffect(() => {
    let mounted = true
    const initAuth = async () => {
      try {
        const res = await authApi.refreshToken()
        if (mounted) {
          setUser(res.user)
          setAuthToken(res.access_token)
        }
      } catch {
        // No active refresh session; user needs to log in
        if (mounted) {
          setUser(null)
          setAuthToken(null)
        }
      } finally {
        if (mounted) {
          setIsLoading(false)
        }
      }
    }
    initAuth()
    return () => {
      mounted = false
    }
  }, [])

  const login = async (email: string, pass: string): Promise<User> => {
    setIsLoading(true)
    try {
      const res = await authApi.login(email, pass)
      if (queryClient) {
        queryClient.clear()
      }
      setUser(res.user)
      return res.user
    } finally {
      setIsLoading(false)
    }
  }

  const logout = async (): Promise<void> => {
    try {
      await authApi.logout()
    } finally {
      if (queryClient) {
        queryClient.clear()
      }
      setUser(null)
      setAuthToken(null)
    }
  }

  const isManager = user?.role === 'DOCUMENTATION_MANAGER'
  const isExecutive = user?.role === 'DOCUMENTATION_EXECUTIVE'
  const isAuthenticated = !!user

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated,
        isManager,
        isExecutive,
        isLoading,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
