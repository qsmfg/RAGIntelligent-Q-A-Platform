import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authAPI } from '@/api'

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('token') || '')
  const userId = ref(localStorage.getItem('userId') || '')
  const username = ref(localStorage.getItem('username') || '')
  const role = ref(localStorage.getItem('role') || '')

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => role.value === 'admin')

  async function login(form) {
    const res = await authAPI.login(form)
    const payload = res.data.data  // 后端返回 {code, message, data: {token, user_id, username}}
    token.value = payload.token
    userId.value = String(payload.user_id)
    username.value = payload.username
    role.value = payload.role || 'user'
    localStorage.setItem('token', payload.token)
    localStorage.setItem('userId', String(payload.user_id))
    localStorage.setItem('username', payload.username)
    localStorage.setItem('role', payload.role || 'user')
    return res
  }

  async function register(form) {
    return await authAPI.register(form)
  }

  function logout() {
    token.value = ''
    userId.value = ''
    username.value = ''
    role.value = ''
    localStorage.removeItem('token')
    localStorage.removeItem('userId')
    localStorage.removeItem('username')
    localStorage.removeItem('role')
  }

  return { token, userId, username, role, isLoggedIn, isAdmin, login, register, logout }
})