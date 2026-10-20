# -*- coding:utf-8 -*-
"""
认证模块 — JWT 令牌生成/验证 + 密码哈希 + FastAPI 认证依赖
"""
import jwt
import datetime
from typing import Optional
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

from base.config import Config
from werkzeug.security import generate_password_hash, check_password_hash

conf = Config()

# JWT 配置
SECRET_KEY = conf.JWT_SECRET_KEY
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7

# FastAPI HTTPBearer 安全方案（auto_error=False 避免返回403，手动返回401）
security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """对明文密码进行哈希处理"""
    return generate_password_hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """验证明文密码与哈希值是否匹配"""
    return check_password_hash(password_hash, password)


def create_token(user_id: int, username: str, role: str = "user") -> str:
    """
    生成 JWT Token（7天有效）
    """
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=TOKEN_EXPIRE_DAYS),
        "iat": datetime.datetime.utcnow()
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token


def decode_token(token: str) -> dict:
    """
    解码并验证 JWT Token

    Args:
        token: JWT 字符串

    Returns:
        解码后的 payload 字典

    Raises:
        HTTPException(401): Token 过期或无效
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token已过期，请重新登录")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="无效的Token")


async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> dict:
    """
    FastAPI 依赖函数 — 从 Authorization Header 中提取并验证 JWT Token

    用法：
        @app.get("/api/protected")
        async def protected_route(user: dict = Depends(get_current_user)):
            user_id = user["user_id"]
            ...

    Returns:
        {"user_id": int, "username": str, "exp": int, "iat": int}

    Raises:
        HTTPException(401): 未提供 Token 或 Token 无效
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="未提供认证Token")
    return decode_token(credentials.credentials)


async def get_admin_user(user: dict = Depends(get_current_user)) -> dict:
    """仅允许管理员访问"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user