import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 30000
})

// 请求拦截器：自动附加 Token
request.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截器：401 自动跳转登录
request.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('userId')
      localStorage.removeItem('username')
      localStorage.removeItem('role')
      ElMessage.error('登录已过期，请重新登录')
      router.push('/login')
    }
    return Promise.reject(error)
  }
)

// ====== 认证接口 ======
export const authAPI = {
  register: (data) => request.post('/api/register', data),
  login: (data) => request.post('/api/login', data),
  profile: () => request.get('/api/profile'),
  logout: () => request.post('/api/logout')
}

// ====== 业务接口 ======
export const chatAPI = {
  createSession: () => request.post('/api/create_session'),
  getHistory: (sessionId) => request.get(`/api/history/${sessionId}`),
  clearHistory: (sessionId) => request.delete(`/api/history/${sessionId}`),
  query: (data) => request.post('/api/query', data),
  getSources: () => request.get('/api/sources')
}

export default request