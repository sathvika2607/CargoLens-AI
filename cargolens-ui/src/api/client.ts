import axios from 'axios'

let inMemoryToken: string | null = null

export const setAuthToken = (token: string | null) => {
  inMemoryToken = token
}

export const getAuthToken = (): string | null => {
  return inMemoryToken
}

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  timeout: 15000,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor: injects bearer token from in-memory state
apiClient.interceptors.request.use(
  (config) => {
    if (inMemoryToken && !config.headers.Authorization) {
      config.headers.Authorization = `Bearer ${inMemoryToken}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor: handles 401 and token expiration gracefully
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config
    // If 401 and not already retried and not a login/refresh request itself
    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.includes('/auth/login') &&
      !originalRequest.url?.includes('/auth/refresh')
    ) {
      originalRequest._retry = true
      try {
        const refreshRes = await axios.post(
          '/api/v1/auth/refresh',
          {},
          { withCredentials: true }
        )
        const newToken = refreshRes.data.access_token
        setAuthToken(newToken)
        originalRequest.headers.Authorization = `Bearer ${newToken}`
        return apiClient(originalRequest)
      } catch (refreshErr) {
        setAuthToken(null)
        return Promise.reject(refreshErr)
      }
    }
    return Promise.reject(error)
  }
)
