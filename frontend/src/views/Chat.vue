<template>
  <div class="chat-layout">
    <!-- 顶部导航 -->
    <el-header class="chat-header">
      <div class="header-left">
        <h2>小A智能问答系统</h2>
        <el-button
          v-if="userStore.isAdmin"
          type="warning"
          size="small"
          @click="$router.push('/admin')"
        >
          后台管理
        </el-button>
      </div>
      <div class="header-right">
        <el-dropdown trigger="click" @command="handleCommand">
          <span class="user-info">
            <el-icon><UserFilled /></el-icon>
            {{ userStore.username }}
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="profile">
                <el-icon><User /></el-icon> 个人信息
              </el-dropdown-item>
              <el-dropdown-item command="logout" divided>
                <el-icon><SwitchButton /></el-icon> 退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </el-header>

    <el-container class="chat-body">
      <!-- 侧边栏 -->
      <el-aside class="chat-sidebar" width="260px">
        <el-button type="primary" class="new-session-btn" @click="createNewSession">
          <el-icon><Plus /></el-icon> 新建会话
        </el-button>

        <div class="sidebar-section">
          <div class="sidebar-title">学科筛选</div>
          <el-select v-model="sourceFilter" placeholder="全部学科" clearable class="filter-select">
            <el-option label="全部" value="" />
            <el-option
              v-for="src in sources"
              :key="src"
              :label="src"
              :value="src"
            />
          </el-select>
        </div>

        <div class="sidebar-section">
          <div class="sidebar-title">
            历史会话
            <el-button link type="danger" size="small" @click="confirmClearHistory">
              清除
            </el-button>
          </div>
          <div class="history-list">
            <div
              v-for="session in sessionList"
              :key="session.id"
              class="history-item"
              :class="{ active: session.id === currentSessionId }"
              @click="switchSession(session)"
            >
              <div class="history-question">{{ session.preview || '新会话' }}</div>
              <div class="history-meta">
                <span>{{ session.time }}</span>
                <el-button
                  link
                  type="danger"
                  size="small"
                  @click.stop="deleteSession(session.id)"
                >
                  <el-icon><Delete /></el-icon>
                </el-button>
              </div>
            </div>
            <el-empty
              v-if="sessionList.length === 0"
              description="暂无历史会话"
              :image-size="60"
            />
          </div>
        </div>
      </el-aside>

      <!-- 聊天主区域 -->
      <el-main class="chat-main">
        <!-- 消息区域 -->
        <div class="message-area" ref="messageArea">
          <div
            v-for="(msg, idx) in messages"
            :key="idx"
            class="message-row"
            :class="msg.role === 'user' ? 'msg-user' : 'msg-bot'"
          >
            <div class="message-avatar">
              <el-icon v-if="msg.role === 'bot'" :size="24"><ChatDotRound /></el-icon>
              <el-icon v-else :size="24"><UserFilled /></el-icon>
            </div>
            <div class="message-bubble" :class="msg.role">
              <!-- 机器人消息使用 markdown 渲染 -->
              <div v-if="msg.role === 'bot'" v-html="renderMarkdown(msg.content)" class="markdown-body"></div>
              <div v-else>{{ msg.content }}</div>
            </div>
          </div>

          <!-- 流式输出中的消息 -->
          <div v-if="streaming" class="message-row msg-bot">
            <div class="message-avatar">
              <el-icon :size="24"><ChatDotRound /></el-icon>
            </div>
            <div class="message-bubble bot">
              <div v-html="renderMarkdown(streamContent || '思考中...')" class="markdown-body"></div>
            </div>
          </div>

          <div ref="messageEnd" class="message-end"></div>
        </div>

        <!-- 输入区域 -->
        <div class="input-area">
          <div class="input-row">
            <el-input
              v-model="inputText"
              type="textarea"
              :rows="1"
              :autosize="{ minRows: 1, maxRows: 4 }"
              placeholder="请输入您的问题，Enter 发送，Shift+Enter 换行"
              :disabled="streaming"
              class="chat-input"
              @keydown.enter.exact.prevent="sendMessage"
            />
            <el-button
              type="primary"
              :icon="Promotion"
              :disabled="!inputText.trim() || streaming"
              class="send-btn"
              @click="sendMessage"
            >
              发送
            </el-button>
          </div>
        </div>
      </el-main>
    </el-container>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  UserFilled, ArrowDown, User, SwitchButton, Plus,
  ChatDotRound, Promotion, Delete
} from '@element-plus/icons-vue'
import { chatAPI } from '@/api'
import { useUserStore } from '@/stores/user'
import { marked } from 'marked'

const router = useRouter()
const userStore = useUserStore()
const messageArea = ref(null)
const messageEnd = ref(null)

// 配置 marked
marked.setOptions({ breaks: true, gfm: true })

const currentSessionId = ref('')
const sources = ref([])
const sourceFilter = ref('')
const messages = ref([])
const sessionList = ref([])
const inputText = ref('')
const streaming = ref(false)
const streamContent = ref('')
let ws = null

// ====== 初始化 ======
onMounted(async () => {
  await loadSources()
  await createNewSession()
})

function renderMarkdown(text) {
  try {
    return marked.parse(text || '')
  } catch {
    return text || ''
  }
}

// ====== 会话管理 ======
async function createNewSession() {
  // 保存当前会话到列表（如果有效且有内容）
  saveCurrentToSessionList()

  try {
    const res = await chatAPI.createSession()
    const newId = res.data.session_id
    // 新会话插入列表最前面（倒序排列）
    sessionList.value.unshift({
      id: newId,
      preview: '新会话',
      time: new Date().toLocaleString(),
      messageCount: 0
    })
    currentSessionId.value = newId
    messages.value = [{
      role: 'bot',
      content: '您好！我是小A智能助手，有什么我可以帮您的吗？'
    }]
  } catch (err) {
    ElMessage.error('创建会话失败')
  }
}

function saveCurrentToSessionList() {
  if (!currentSessionId.value) return
  const userMsgs = messages.value.filter(m => m.role === 'user')
  const existingIdx = sessionList.value.findIndex(s => s.id === currentSessionId.value)

  if (existingIdx >= 0) {
    // 更新已有会话的预览
    sessionList.value[existingIdx].preview = userMsgs.length > 0
      ? userMsgs[userMsgs.length - 1].content.slice(0, 30)
      : '新会话'
    sessionList.value[existingIdx].time = new Date().toLocaleString()
    sessionList.value[existingIdx].messageCount = userMsgs.length
  } else if (userMsgs.length > 0) {
    // 有内容的会话，新增到列表最前面
    sessionList.value.unshift({
      id: currentSessionId.value,
      preview: userMsgs[userMsgs.length - 1].content.slice(0, 30),
      time: new Date().toLocaleString(),
      messageCount: userMsgs.length
    })
  }
}

function switchSession(session) {
  if (session.id === currentSessionId.value) return
  // 保存当前会话状态
  saveCurrentToSessionList()
  // 切换到目标会话
  currentSessionId.value = session.id
  loadSessionMessages()
}

async function loadSessionMessages() {
  try {
    const res = await chatAPI.getHistory(currentSessionId.value)
    const history = res.data.history || []
    messages.value = []
    for (const item of history) {
      messages.value.push({ role: 'user', content: item.question })
      messages.value.push({ role: 'bot', content: item.answer })
    }
    if (messages.value.length === 0) {
      messages.value.push({
        role: 'bot',
        content: '您好！我是小A智能助手，有什么我可以帮您的吗？'
      })
    }
    scrollToBottom()
  } catch {
    // 忽略
  }
}

async function confirmClearHistory() {
  try {
    await ElMessageBox.confirm('确定要清除当前会话的所有历史记录吗？', '确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await chatAPI.clearHistory(currentSessionId.value)
    messages.value = [{
      role: 'bot',
      content: '历史记录已清除，有什么我可以帮您的吗？'
    }]
    // 更新会话列表中当前会话的预览
    const idx = sessionList.value.findIndex(s => s.id === currentSessionId.value)
    if (idx >= 0) {
      sessionList.value[idx].preview = '新会话'
      sessionList.value[idx].messageCount = 0
    }
    ElMessage.success('历史记录已清除')
  } catch {
    // 取消操作
  }
}

async function deleteSession(sessionId) {
  try {
    await chatAPI.clearHistory(sessionId)
  } catch {
    // 即使后端删除失败也从前端列表移除
  }
  sessionList.value = sessionList.value.filter(s => s.id !== sessionId)
  if (sessionId === currentSessionId.value && sessionList.value.length > 0) {
    // 如果删除的是当前会话，切换到列表第一个
    switchSession(sessionList.value[0])
  } else if (sessionList.value.length === 0) {
    // 没有会话了，创建新会话
    await createNewSession()
  }
}

// ====== 学科筛选 ======
async function loadSources() {
  try {
    const res = await chatAPI.getSources()
    const data = res.data
    // 兼容后端直接返回 {sources: [...]} 格式
    sources.value = data.sources || data.data?.sources || []
  } catch (err) {
    ElMessage.error('加载学科列表失败')
  }
}

// ====== 消息发送 ======
async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || streaming.value) return

  inputText.value = ''
  messages.value.push({ role: 'user', content: text })
  scrollToBottom()

  try {
    // 先尝试 HTTP 查询（BM25快速匹配）
    const res = await chatAPI.query({
      query: text,
      source_filter: sourceFilter.value || null,
      session_id: currentSessionId.value
    })

    if (res.data.is_streaming) {
      // 需要 WebSocket 流式输出
      await startStreaming(text)
    } else {
      // BM25 直接命中
      messages.value.push({ role: 'bot', content: res.data.answer })
      saveCurrentToSessionList()
      scrollToBottom()
    }
  } catch (err) {
    ElMessage.error('查询失败，请重试')
  }
}

async function startStreaming(query) {
  streaming.value = true
  streamContent.value = ''

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const base = import.meta.env.VITE_API_BASE_URL
    ? import.meta.env.VITE_API_BASE_URL.replace(/^https?/, protocol === 'wss:' ? 'wss' : 'ws')
    : `${protocol}//${window.location.host}`
  const wsUrl = `${base}/api/stream`
  const token = localStorage.getItem('token')

  return new Promise((resolve) => {
    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      ws.send(JSON.stringify({
        token: token,
        query: query,
        source_filter: sourceFilter.value || null,
        session_id: currentSessionId.value
      }))
    }

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      switch (data.type) {
        case 'token':
          streamContent.value += data.token
          scrollToBottom()
          break
        case 'end':
          messages.value.push({ role: 'bot', content: streamContent.value })
          streamContent.value = ''
          streaming.value = false
          ws.close()
          saveCurrentToSessionList()
          resolve()
          break
        case 'error':
          ElMessage.error(data.error || '流式请求出错')
          streamContent.value = ''
          streaming.value = false
          ws.close()
          resolve()
          break
      }
    }

    ws.onerror = () => {
      if (streaming.value) {
        ElMessage.error('网络连接异常')
        streamContent.value = ''
        streaming.value = false
      }
      resolve()
    }

    ws.onclose = () => {
      if (streaming.value) {
        streamContent.value = ''
        streaming.value = false
      }
      resolve()
    }
  })
}

// ====== 用户操作 ======
function handleCommand(command) {
  if (command === 'logout') {
    userStore.logout()
    ElMessage.success('已退出登录')
    router.push('/login')
  } else if (command === 'profile') {
    router.push('/profile')
  }
}

// ====== 滚动 ======
function scrollToBottom() {
  nextTick(() => {
    if (messageEnd.value) {
      messageEnd.value.scrollIntoView({ behavior: 'smooth' })
    }
  })
}
</script>

<style scoped>
.chat-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #f0f2f5;
}

/* Header */
.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  padding: 0 24px;
  height: 60px;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-left h2 {
  margin: 0;
  font-size: 18px;
  color: #303133;
}

.header-right .user-info {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  color: #606266;
  font-size: 14px;
  padding: 6px 12px;
  border-radius: 6px;
  transition: background 0.2s;
}

.header-right .user-info:hover {
  background: #f5f7fa;
}

/* Body */
.chat-body {
  flex: 1;
  overflow: hidden;
}

/* Sidebar */
.chat-sidebar {
  background: #fff;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  padding: 16px;
  overflow-y: auto;
}

.new-session-btn {
  width: 100%;
  margin-bottom: 16px;
}

.sidebar-section {
  margin-bottom: 16px;
}

.sidebar-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  color: #909399;
  margin-bottom: 8px;
  font-weight: 500;
}

.filter-select {
  width: 100%;
}

.history-list {
  flex: 1;
  overflow-y: auto;
}

.history-item {
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 4px;
  transition: background 0.2s;
}

.history-item:hover {
  background: #f5f7fa;
}

.history-item.active {
  background: #ecf5ff;
  border: 1px solid #d9ecff;
}

.history-question {
  font-size: 13px;
  color: #303133;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.history-meta {
  font-size: 11px;
  color: #c0c4cc;
  margin-top: 2px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* Main */
.chat-main {
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow: hidden;
  background: #f5f7fa;
}

.message-area {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.message-row {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.msg-user {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #e9eaf0;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: #909399;
}

.message-bubble {
  max-width: 70%;
  padding: 12px 16px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}

.message-bubble.user {
  background: #667eea;
  color: #fff;
  border-bottom-right-radius: 4px;
}

.message-bubble.bot {
  background: #fff;
  color: #303133;
  border-bottom-left-radius: 4px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

.message-end {
  height: 1px;
}

/* Markdown */
.markdown-body :deep(pre) {
  background: #f6f8fa;
  padding: 12px 16px;
  border-radius: 6px;
  overflow-x: auto;
  font-size: 13px;
  line-height: 1.5;
}

.markdown-body :deep(code) {
  font-family: 'Courier New', monospace;
  background: #f6f8fa;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 13px;
}

.markdown-body :deep(p) {
  margin: 0 0 8px;
}

.markdown-body :deep(p:last-child) {
  margin: 0;
}

/* Input */
.input-area {
  background: #fff;
  border-top: 1px solid #e4e7ed;
  padding: 16px 24px;
}

.input-row {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

.chat-input {
  flex: 1;
}

.send-btn {
  height: 40px;
}
</style>