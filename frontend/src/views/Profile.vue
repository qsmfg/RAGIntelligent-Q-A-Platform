<template>
  <div class="profile-layout">
    <el-header class="profile-header">
      <el-button link @click="$router.push('/chat')">
        <el-icon><ArrowLeft /></el-icon> 返回聊天
      </el-button>
      <h2>个人信息</h2>
    </el-header>

    <el-main class="profile-main">
      <el-row :gutter="20">
        <!-- 基本信息卡片 -->
        <el-col :span="12">
          <el-card>
            <template #header><span>基本信息</span></template>
            <el-descriptions :column="1" border>
              <el-descriptions-item label="用户ID">{{ profile.user_id }}</el-descriptions-item>
              <el-descriptions-item label="用户名">{{ profile.username }}</el-descriptions-item>
              <el-descriptions-item label="角色">
                <el-tag :type="profile.role === 'admin' ? 'danger' : 'info'" size="small">
                  {{ profile.role === 'admin' ? '管理员' : '普通用户' }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="注册时间">{{ profile.created_at }}</el-descriptions-item>
            </el-descriptions>
          </el-card>
        </el-col>

        <!-- 对话统计卡片 -->
        <el-col :span="12">
          <el-card>
            <template #header><span>对话统计</span></template>
            <el-descriptions :column="1" border>
              <el-descriptions-item label="总消息数">
                {{ profile.stats?.total_messages || 0 }} 条
              </el-descriptions-item>
              <el-descriptions-item label="首次对话">
                {{ profile.stats?.first_chat || '暂无' }}
              </el-descriptions-item>
              <el-descriptions-item label="最近对话">
                {{ profile.stats?.last_chat || '暂无' }}
              </el-descriptions-item>
              <el-descriptions-item label="对话时长">
                {{ chatDuration }}
              </el-descriptions-item>
            </el-descriptions>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="20" style="margin-top: 20px">
        <!-- 修改用户名 -->
        <el-col :span="12">
          <el-card>
            <template #header>
              <span>修改用户名</span>
              <span class="card-tip">（每月限一次）</span>
            </template>
            <el-form ref="usernameFormRef" :model="usernameForm" :rules="usernameRules" label-position="top">
              <el-form-item label="新用户名" prop="new_username">
                <el-input v-model="usernameForm.new_username" placeholder="3-50字符" />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" :loading="usernameLoading" @click="handleChangeUsername">
                  修改用户名
                </el-button>
              </el-form-item>
            </el-form>
          </el-card>
        </el-col>

        <!-- 修改密码 -->
        <el-col :span="12">
          <el-card>
            <template #header><span>修改密码</span></template>
            <el-form ref="passwordFormRef" :model="passwordForm" :rules="passwordRules" label-position="top">
              <el-form-item label="原密码" prop="old_password">
                <el-input v-model="passwordForm.old_password" type="password" show-password />
              </el-form-item>
              <el-form-item label="新密码" prop="new_password">
                <el-input v-model="passwordForm.new_password" type="password" show-password placeholder="至少6位" />
              </el-form-item>
              <el-form-item label="确认新密码" prop="confirm_password">
                <el-input v-model="passwordForm.confirm_password" type="password" show-password />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" :loading="passwordLoading" @click="handleChangePassword">
                  修改密码
                </el-button>
              </el-form-item>
            </el-form>
          </el-card>
        </el-col>
      </el-row>
    </el-main>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import axios from 'axios'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

const profile = ref({ stats: {} })
const usernameLoading = ref(false)
const passwordLoading = ref(false)
const usernameFormRef = ref(null)
const passwordFormRef = ref(null)

const usernameForm = reactive({ new_username: '' })
const passwordForm = reactive({ old_password: '', new_password: '', confirm_password: '' })

const usernameRules = {
  new_username: [
    { required: true, message: '请输入新用户名', trigger: 'blur' },
    { min: 3, max: 50, message: '3-50 字符', trigger: 'blur' }
  ]
}

const validateConfirm = (rule, value, callback) => {
  if (value !== passwordForm.new_password) {
    callback(new Error('两次密码不一致'))
  } else {
    callback()
  }
}

const passwordRules = {
  old_password: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '至少 6 位', trigger: 'blur' }
  ],
  confirm_password: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    { validator: validateConfirm, trigger: 'blur' }
  ]
}

const chatDuration = computed(() => {
  const s = profile.value.stats
  if (!s || !s.first_chat) return '暂无'
  const start = new Date(s.first_chat)
  const end = s.last_chat ? new Date(s.last_chat) : new Date()
  const days = Math.floor((end - start) / (1000 * 60 * 60 * 24))
  if (days < 1) return '不足 1 天'
  if (days < 30) return `${days} 天`
  const months = Math.floor(days / 30)
  return `${months} 个月（约 ${days} 天）`
})

async function loadProfile() {
  try {
    const token = localStorage.getItem('token')
    const res = await axios.get('/api/profile', {
      headers: { Authorization: `Bearer ${token}` }
    })
    profile.value = res.data.data
  } catch {
    ElMessage.error('加载个人信息失败')
  }
}

async function handleChangeUsername() {
  const valid = await usernameFormRef.value.validate().catch(() => false)
  if (!valid) return
  usernameLoading.value = true
  try {
    const token = localStorage.getItem('token')
    const res = await axios.put('/api/profile/username',
      { new_username: usernameForm.new_username },
      { headers: { Authorization: `Bearer ${token}` } }
    )
    ElMessage.success('用户名修改成功，请重新登录')
    // 更新本地存储
    localStorage.setItem('token', res.data.data.token)
    localStorage.setItem('username', res.data.data.username)
    usernameForm.new_username = ''
    await loadProfile()
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '修改失败')
  } finally {
    usernameLoading.value = false
  }
}

async function handleChangePassword() {
  const valid = await passwordFormRef.value.validate().catch(() => false)
  if (!valid) return
  passwordLoading.value = true
  try {
    const token = localStorage.getItem('token')
    await axios.put('/api/profile/password',
      { old_password: passwordForm.old_password, new_password: passwordForm.new_password },
      { headers: { Authorization: `Bearer ${token}` } }
    )
    ElMessage.success('密码修改成功')
    passwordForm.old_password = ''
    passwordForm.new_password = ''
    passwordForm.confirm_password = ''
    passwordFormRef.value.resetFields()
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '修改失败')
  } finally {
    passwordLoading.value = false
  }
}

onMounted(loadProfile)
</script>

<style scoped>
.profile-layout {
  min-height: 100vh;
  background: #f0f2f5;
}

.profile-header {
  display: flex;
  align-items: center;
  gap: 16px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  padding: 0 24px;
  height: 60px;
}

.profile-header h2 {
  margin: 0;
  font-size: 18px;
}

.profile-main {
  padding: 24px;
  max-width: 1000px;
  margin: 0 auto;
}

.card-tip {
  font-size: 12px;
  color: #909399;
  font-weight: normal;
}
</style>