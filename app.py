from fastapi import FastAPI, WebSocket, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.websockets import WebSocketDisconnect
import os
from pydantic import BaseModel, Field
import asyncio
import json
import uuid
from typing import Optional, List, Dict, Any
import time
import re

# 导入现有的系统
from new_main import IntegratedQASystem

# 导入认证模块
from base.auth import hash_password, verify_password, create_token, decode_token, get_current_user, get_admin_user
from base.user_manager import UserManager

# 创建应用实例
app = FastAPI(title="小A智能问答系统 API", description="集成MySQL和RAG的智能问答系统")

# 配置CORS，允许前端访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该限制为特定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 创建静态文件目录
os.makedirs("static", exist_ok=True)

# 创建全局QA系统实例
qa_system = IntegratedQASystem()

# 创建用户管理实例并初始化 users 表
user_manager = UserManager()
user_manager.create_users_table()

# 定义日常问候用语模式和回复
GREETING_PATTERNS = [
    {
        "pattern": r"^(你好|您好|hi|hello)",
        "response": "你好！我是小A，专注于为学生答疑解惑，很高兴为你服务！"
    },
    {
        "pattern": r"^(你是谁|您是谁|你叫什么|你的名字|who are you)",
        "response": "我是小A，你的智能学习助手，致力于提供 IT 教育相关的解答！"
    },
    {
        "pattern": r"^(在吗|在不在|有人吗)",
        "response": "我在！我是小A，随时为你解答问题！"
    },
    {
        "pattern": r"^(干嘛呢|你在干嘛|做什么)",
        "response": "我正在待命，随时为你解答 IT 学习相关的问题！有什么我可以帮你的？"
    }
]


# ========== 请求/响应模型 ==========

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="用户名，3-50字符")
    password: str = Field(..., min_length=6, description="密码，至少6位")


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6)


class ChangeUsernameRequest(BaseModel):
    new_username: str = Field(..., min_length=3, max_length=50)


class QueryRequest(BaseModel):
    query: str
    source_filter: Optional[str] = None
    session_id: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    is_streaming: bool
    session_id: str
    processing_time: float


# ========== 静态文件 ==========

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def read_root():
    return FileResponse("static/index.html")


# ========== 认证接口（公开） ==========

@app.post("/api/register")
async def register(request: RegisterRequest):
    """用户注册"""
    # 检查用户名是否已存在
    existing_user = user_manager.get_user_by_username(request.username)
    if existing_user:
        raise HTTPException(status_code=400, detail="用户名已存在")

    # 哈希密码并创建用户
    pwd_hash = hash_password(request.password)
    user_id = user_manager.create_user(request.username, pwd_hash)

    if user_id is None:
        raise HTTPException(status_code=400, detail="注册失败，用户名可能已存在")

    return {
        "code": 200,
        "message": "注册成功",
        "data": {"user_id": user_id}
    }


@app.post("/api/login")
async def login(request: LoginRequest):
    """用户登录"""
    # 查询用户
    user = user_manager.get_user_by_username(request.username)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    # 验证密码
    if not verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    # 检查是否被封禁
    if user.get("status") == "banned":
        raise HTTPException(status_code=403, detail="账号已被封禁")

    # 生成 JWT Token（含角色）
    token = create_token(user["id"], user["username"], user.get("role", "user"))

    return {
        "code": 200,
        "message": "登录成功",
        "data": {
            "token": token,
            "user_id": user["id"],
            "username": user["username"],
            "role": user.get("role", "user")
        }
    }


# ========== 认证接口（需要Token） ==========

@app.get("/api/profile")
async def profile(user: dict = Depends(get_current_user)):
    """获取当前用户个人信息"""
    user_info = user_manager.get_user_by_id(user["user_id"])
    if not user_info:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 获取对话统计
    stats = user_manager.get_conversation_stats(user["user_id"])

    return {
        "code": 200,
        "message": "获取成功",
        "data": {
            "user_id": user_info["id"],
            "username": user_info["username"],
            "role": user_info.get("role", "user"),
            "status": user_info.get("status", "active"),
            "last_username_change": user_info["last_username_change"].isoformat() if user_info["last_username_change"] else None,
            "created_at": user_info["created_at"].isoformat() if user_info["created_at"] else None,
            "stats": stats
        }
    }


@app.put("/api/profile/password")
async def change_password(request: ChangePasswordRequest, user: dict = Depends(get_current_user)):
    """修改密码（需验证原密码）"""
    user_info = user_manager.get_user_by_id(user["user_id"])
    if not verify_password(request.old_password, user_info["password_hash"]):
        raise HTTPException(status_code=400, detail="原密码错误")

    new_hash = hash_password(request.new_password)
    success = user_manager.change_password(user["user_id"], new_hash)
    if not success:
        raise HTTPException(status_code=500, detail="修改密码失败")

    return {"code": 200, "message": "密码修改成功"}


@app.put("/api/profile/username")
async def change_username(request: ChangeUsernameRequest, user: dict = Depends(get_current_user)):
    """修改用户名（一月一次限制）"""
    error = user_manager.change_username(user["user_id"], request.new_username)
    if error:
        raise HTTPException(status_code=400, detail=error)

    # 更新 JWT 中的用户名
    new_token = create_token(user["user_id"], request.new_username, user.get("role", "user"))
    return {"code": 200, "message": "用户名修改成功", "data": {"token": new_token, "username": request.new_username}}


@app.post("/api/logout")
async def logout(user: dict = Depends(get_current_user)):
    """退出登录（客户端清除 Token 即可，服务端记录日志）"""
    return {
        "code": 200,
        "message": "退出登录成功"
    }


# ========== 业务接口（需要Token） ==========

@app.post("/api/create_session")
async def create_session(user: dict = Depends(get_current_user)):
    session_id = str(uuid.uuid4())
    return {"session_id": session_id}


@app.get("/api/history/{session_id}")
async def get_history(session_id: str, user: dict = Depends(get_current_user)):
    try:
        history = qa_system.get_session_history(session_id, user["user_id"])
        return {"session_id": session_id, "history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取历史记录失败: {str(e)}")


@app.delete("/api/history/{session_id}")
async def clear_history(session_id: str, user: dict = Depends(get_current_user)):
    success = qa_system.clear_session_history(session_id, user["user_id"])
    if success:
        return {"status": "success", "message": "历史记录已清除"}
    else:
        raise HTTPException(status_code=500, detail="清除历史记录失败")


# 检查是否为日常问候用语并返回模板回复
def check_greeting(query: str) -> Optional[str]:
    query_text = query.strip()
    for pattern_info in GREETING_PATTERNS:
        if re.match(pattern_info["pattern"], query_text, re.IGNORECASE):
            return pattern_info["response"]
    return None


@app.post("/api/query")
async def query(request: QueryRequest, user: dict = Depends(get_current_user)):
    start_time = time.time()
    session_id = request.session_id or str(uuid.uuid4())

    # 检查是否为日常问候
    greeting_response = check_greeting(request.query)
    if greeting_response:
        # 保存问候对话到历史
        qa_system.update_session_history(session_id, request.query, greeting_response, user["user_id"])
        return {
            "answer": greeting_response,
            "is_streaming": False,
            "session_id": session_id,
            "processing_time": time.time() - start_time
        }

    # 执行 BM25 搜索
    answer, need_rag = qa_system.bm25_search.search(request.query, threshold=0.85)
    if need_rag:
        return {
            "answer": "请使用WebSocket接口获取流式响应",
            "is_streaming": True,
            "session_id": session_id,
            "processing_time": time.time() - start_time
        }

    # 保存 MySQL 答案到历史
    qa_system.update_session_history(session_id, request.query, answer, user["user_id"])
    return {
        "answer": answer,
        "is_streaming": False,
        "session_id": session_id,
        "processing_time": time.time() - start_time
    }


# 流式查询WebSocket接口
@app.websocket("/api/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    # WebSocket 认证：从首个消息中提取 token
    user_id = None
    token_verified = False

    try:
        while True:
            data = await websocket.receive_text()
            request_data = json.loads(data)

            # 首个消息进行 Token 认证
            if not token_verified:
                token = request_data.get("token", "")
                if not token:
                    await websocket.send_json({"type": "error", "error": "未提供Token，请先登录"})
                    await websocket.close(code=4001)
                    return
                try:
                    payload = decode_token(token)
                    user_id = payload["user_id"]
                    token_verified = True
                except HTTPException as e:
                    await websocket.send_json({"type": "error", "error": str(e.detail)})
                    await websocket.close(code=4001)
                    return

            query = request_data.get("query")
            source_filter = request_data.get("source_filter")
            session_id = request_data.get("session_id", str(uuid.uuid4()))
            start_time = time.time()

            if websocket.client_state == websocket.client_state.CONNECTED:
                await websocket.send_json({
                    "type": "start",
                    "session_id": session_id
                })

            # 检查是否为日常问候
            greeting_response = check_greeting(query)
            if greeting_response:
                if websocket.client_state == websocket.client_state.CONNECTED:
                    await websocket.send_json({
                        "type": "token",
                        "token": greeting_response,
                        "session_id": session_id
                    })
                    await websocket.send_json({
                        "type": "end",
                        "session_id": session_id,
                        "is_complete": True,
                        "processing_time": time.time() - start_time
                    })
                # 保存问候到历史
                qa_system.update_session_history(session_id, query, greeting_response, user_id)
                break

            # 调用问答系统，流式处理查询
            collected_answer = ""
            for token, is_complete in qa_system.query(
                query, source_filter=source_filter, session_id=session_id, user_id=user_id
            ):
                collected_answer += token
                if is_complete and not collected_answer:
                    if websocket.client_state == websocket.client_state.CONNECTED:
                        await websocket.send_json({
                            "type": "end",
                            "session_id": session_id,
                            "is_complete": True,
                            "processing_time": time.time() - start_time
                        })
                    break
                if token and websocket.client_state == websocket.client_state.CONNECTED:
                    await websocket.send_json({
                        "type": "token",
                        "token": token,
                        "session_id": session_id
                    })
                if is_complete:
                    if websocket.client_state == websocket.client_state.CONNECTED:
                        await websocket.send_json({
                            "type": "end",
                            "session_id": session_id,
                            "is_complete": True,
                            "processing_time": time.time() - start_time
                        })
                    break
                await asyncio.sleep(0.01)

    except WebSocketDisconnect as e:
        print(f"WebSocket disconnected: code={e.code}, reason={e.reason}")
    except Exception as e:
        print(f"WebSocket error: {str(e)}")
        if websocket.client_state == websocket.client_state.CONNECTED:
            await websocket.send_json({
                "type": "error",
                "error": str(e)
            })
    finally:
        try:
            if websocket.client_state == websocket.client_state.CONNECTED:
                await websocket.close()
        except Exception as e:
            print(f"Error closing WebSocket: {str(e)}")


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/api/sources")
async def get_sources(user: dict = Depends(get_current_user)):
    return {"sources": qa_system.config.VALID_SOURCES}


# ========== 管理员接口 ==========

@app.get("/api/admin/users")
async def admin_list_users(admin: dict = Depends(get_admin_user)):
    """管理员获取所有用户列表"""
    users = user_manager.list_all_users()
    return {"code": 200, "data": users}


@app.put("/api/admin/users/{user_id}/ban")
async def admin_ban_user(user_id: int, admin: dict = Depends(get_admin_user)):
    """封禁/解封用户"""
    if user_id == admin["user_id"]:
        raise HTTPException(status_code=400, detail="不能操作自己")
    new_status = user_manager.ban_user(user_id)
    if new_status is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    action = "解封" if new_status == "active" else "封禁"
    return {"code": 200, "message": f"用户已{action}", "data": {"status": new_status}}


@app.put("/api/admin/users/{user_id}/role")
async def admin_set_role(user_id: int, role: str = Query(..., pattern="^(admin|user)$"), admin: dict = Depends(get_admin_user)):
    """设置用户角色"""
    if user_id == admin["user_id"]:
        raise HTTPException(status_code=400, detail="不能修改自己的角色")
    success = user_manager.set_role(user_id, role)
    if not success:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"code": 200, "message": f"角色已更新为 {role}"}


@app.delete("/api/admin/users/{user_id}")
async def admin_delete_user(user_id: int, admin: dict = Depends(get_admin_user)):
    """删除用户"""
    if user_id == admin["user_id"]:
        raise HTTPException(status_code=400, detail="不能删除自己")
    success = user_manager.delete_user(user_id)
    if not success:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"code": 200, "message": "用户已删除"}


# SPA 回退：Vue Router 前端路由（/chat、/login等）由 index.html 处理
# 必须放在所有 API 路由之后，否则会拦截 API 请求
@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    if full_path.startswith("api/") or full_path.startswith("static/"):
        raise HTTPException(status_code=404)
    return FileResponse("static/index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)