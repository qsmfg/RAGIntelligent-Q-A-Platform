<template>
  <div class="admin-layout">
    <el-header class="admin-header">
      <div class="header-left">
        <el-button link @click="$router.push('/chat')">
          <el-icon><ArrowLeft /></el-icon> 返回聊天
        </el-button>
        <h2>后台管理</h2>
      </div>
    </el-header>

    <el-main class="admin-main">
      <el-card>
        <template #header>
          <span>用户管理（共 {{ users.length }} 人）</span>
        </template>

        <el-table :data="users" stripe border style="width: 100%">
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="username" label="用户名" width="140" />
          <el-table-column prop="role" label="角色" width="100">
            <template #default="{ row }">
              <el-tag :type="row.role === 'admin' ? 'danger' : 'info'" size="small">
                {{ row.role === 'admin' ? '管理员' : '普通用户' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="row.status === 'active' ? 'success' : 'danger'" size="small">
                {{ row.status === 'active' ? '正常' : '已封禁' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="注册时间" min-width="170" />
          <el-table-column label="操作" width="240" fixed="right">
            <template #default="{ row }">
              <el-button
                size="small"
                :type="row.status === 'banned' ? 'success' : 'warning'"
                @click="toggleBan(row)"
              >
                {{ row.status === 'banned' ? '解封' : '封禁' }}
              </el-button>
              <el-button
                size="small"
                :type="row.role === 'admin' ? 'info' : 'primary'"
                @click="toggleRole(row)"
              >
                {{ row.role === 'admin' ? '降级' : '提升' }}
              </el-button>
              <el-button
                size="small"
                type="danger"
                @click="deleteUser(row)"
              >
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </el-main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import axios from 'axios'

const users = ref([])

async function loadUsers() {
  try {
    const token = localStorage.getItem('token')
    const res = await axios.get('/api/admin/users', {
      headers: { Authorization: `Bearer ${token}` }
    })
    users.value = res.data.data
  } catch (err) {
    ElMessage.error('加载用户列表失败')
  }
}

async function toggleBan(row) {
  const action = row.status === 'banned' ? '解封' : '封禁'
  try {
    await ElMessageBox.confirm(`确定要${action}用户 "${row.username}" 吗？`, '确认操作', {
      type: 'warning'
    })
    const token = localStorage.getItem('token')
    await axios.put(`/api/admin/users/${row.id}/ban`, null, {
      headers: { Authorization: `Bearer ${token}` }
    })
    ElMessage.success(`已${action}`)
    await loadUsers()
  } catch { /* 取消 */ }
}

async function toggleRole(row) {
  const newRole = row.role === 'admin' ? 'user' : 'admin'
  const action = newRole === 'admin' ? '提升为管理员' : '降级为普通用户'
  try {
    await ElMessageBox.confirm(`确定将 "${row.username}" ${action}吗？`, '确认操作', {
      type: 'warning'
    })
    const token = localStorage.getItem('token')
    await axios.put(`/api/admin/users/${row.id}/role?role=${newRole}`, null, {
      headers: { Authorization: `Bearer ${token}` }
    })
    ElMessage.success('操作成功')
    await loadUsers()
  } catch { /* 取消 */ }
}

async function deleteUser(row) {
  try {
    await ElMessageBox.confirm(`确定要永久删除用户 "${row.username}" 吗？此操作不可恢复！`, '危险操作', {
      type: 'error',
      confirmButtonText: '确认删除'
    })
    const token = localStorage.getItem('token')
    await axios.delete(`/api/admin/users/${row.id}`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    ElMessage.success('已删除')
    await loadUsers()
  } catch { /* 取消 */ }
}

onMounted(loadUsers)
</script>

<style scoped>
.admin-layout {
  min-height: 100vh;
  background: #f0f2f5;
}

.admin-header {
  display: flex;
  align-items: center;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  padding: 0 24px;
  height: 60px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-left h2 {
  margin: 0;
  font-size: 18px;
}

.admin-main {
  padding: 24px;
  max-width: 1100px;
  margin: 0 auto;
}
</style>