# -*- coding:utf-8 -*-
"""
用户管理模块 — 封装 users 表的数据库操作
"""
import pymysql
import sys
import os

# 确保能导入 base 模块
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

from base import Config, logger


class UserManager:
    """用户管理类，负责 users 表的 CRUD 操作"""

    def __init__(self):
        self.logger = logger
        self.config = Config()
        try:
            self.connection = pymysql.connect(
                host=self.config.MYSQL_HOST,
                user=self.config.MYSQL_USER,
                port=3307,
                password=self.config.MYSQL_PASSWORD,
                database=self.config.MYSQL_DATABASE,
                autocommit=True
            )
            self.cursor = self.connection.cursor()
            self.logger.info("UserManager MySQL 连接成功")
        except pymysql.MySQLError as e:
            self.logger.error(f"UserManager MySQL 连接失败: {e}")
            raise

    def create_users_table(self):
        """创建 users 表（如果不存在）"""
        create_sql = """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_username (username)
        );
        """
        try:
            self.cursor.execute(create_sql)
            self.connection.commit()
            self.logger.info("users 表初始化成功")
        except pymysql.MySQLError as e:
            self.logger.error(f"创建 users 表失败: {e}")
            raise

    def create_user(self, username: str, password_hash: str) -> int:
        """创建新用户，返回 user_id；用户名重复时返回 None"""
        try:
            self.cursor.execute(
                "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
                (username, password_hash)
            )
            self.connection.commit()
            user_id = self.cursor.lastrowid
            self.logger.info(f"用户 '{username}' 注册成功，user_id={user_id}")
            return user_id
        except pymysql.IntegrityError:
            self.logger.warning(f"用户名 '{username}' 已存在")
            return None
        except pymysql.MySQLError as e:
            self.logger.error(f"创建用户失败: {e}")
            raise

    def get_user_by_username(self, username: str):
        """按用户名查询用户，返回字典或 None"""
        try:
            self.cursor.execute(
                "SELECT id, username, password_hash, role, status, last_username_change, created_at FROM users WHERE username = %s",
                (username,)
            )
            row = self.cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "username": row[1],
                    "password_hash": row[2],
                    "role": row[3],
                    "status": row[4],
                    "last_username_change": row[5],
                    "created_at": row[6]
                }
            return None
        except pymysql.MySQLError as e:
            self.logger.error(f"查询用户失败: {e}")
            return None

    def get_user_by_id(self, user_id: int):
        """按用户 ID 查询用户，返回字典或 None"""
        try:
            self.cursor.execute(
                "SELECT id, username, password_hash, role, status, last_username_change, created_at FROM users WHERE id = %s",
                (user_id,)
            )
            row = self.cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "username": row[1],
                    "password_hash": row[2],
                    "role": row[3],
                    "status": row[4],
                    "last_username_change": row[5],
                    "created_at": row[6]
                }
            return None
        except pymysql.MySQLError as e:
            self.logger.error(f"查询用户失败: {e}")
            return None

    def list_all_users(self):
        """获取所有用户列表（管理员用）"""
        try:
            self.cursor.execute(
                "SELECT id, username, role, status, created_at FROM users ORDER BY id"
            )
            rows = self.cursor.fetchall()
            return [{
                "id": r[0],
                "username": r[1],
                "role": r[2],
                "status": r[3],
                "created_at": r[4].isoformat() if r[4] else None
            } for r in rows]
        except pymysql.MySQLError as e:
            self.logger.error(f"获取用户列表失败: {e}")
            return []

    def ban_user(self, user_id: int):
        """封禁/解封用户"""
        try:
            self.cursor.execute("SELECT status FROM users WHERE id = %s", (user_id,))
            row = self.cursor.fetchone()
            if not row:
                return None
            new_status = "active" if row[0] == "banned" else "banned"
            self.cursor.execute("UPDATE users SET status = %s WHERE id = %s", (new_status, user_id))
            self.connection.commit()
            return new_status
        except pymysql.MySQLError as e:
            self.logger.error(f"封禁/解封失败: {e}")
            return None

    def set_role(self, user_id: int, role: str):
        """设置用户角色"""
        try:
            self.cursor.execute("UPDATE users SET role = %s WHERE id = %s", (role, user_id))
            self.connection.commit()
            return self.cursor.rowcount > 0
        except pymysql.MySQLError as e:
            self.logger.error(f"设置角色失败: {e}")
            return False

    def delete_user(self, user_id: int):
        """删除用户"""
        try:
            self.cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
            self.connection.commit()
            return self.cursor.rowcount > 0
        except pymysql.MySQLError as e:
            self.logger.error(f"删除用户失败: {e}")
            return False

    def change_password(self, user_id: int, new_password_hash: str):
        """修改密码"""
        try:
            self.cursor.execute(
                "UPDATE users SET password_hash = %s WHERE id = %s",
                (new_password_hash, user_id)
            )
            self.connection.commit()
            return self.cursor.rowcount > 0
        except pymysql.MySQLError as e:
            self.logger.error(f"修改密码失败: {e}")
            return False

    def change_username(self, user_id: int, new_username: str) -> str:
        """
        修改用户名（一月一次限制）
        返回 None 表示成功，否则返回错误信息字符串
        """
        try:
            # 检查重复
            self.cursor.execute("SELECT id FROM users WHERE username = %s", (new_username,))
            if self.cursor.fetchone():
                return "用户名已存在"

            # 检查一月一次限制
            self.cursor.execute(
                "SELECT last_username_change FROM users WHERE id = %s", (user_id,)
            )
            row = self.cursor.fetchone()
            if row and row[0]:
                from datetime import datetime, timedelta
                last_change = row[0]
                if datetime.now() - last_change < timedelta(days=30):
                    days_left = 30 - (datetime.now() - last_change).days
                    return f"用户名修改限制为每月一次，还需等待 {days_left} 天"

            self.cursor.execute(
                "UPDATE users SET username = %s, last_username_change = NOW() WHERE id = %s",
                (new_username, user_id)
            )
            self.connection.commit()
            return None  # 成功
        except pymysql.MySQLError as e:
            self.logger.error(f"修改用户名失败: {e}")
            return f"数据库错误: {e}"

    def get_conversation_stats(self, user_id: int):
        """获取用户对话统计"""
        try:
            self.cursor.execute(
                """SELECT COUNT(*) as total_msgs,
                   MIN(timestamp) as first_chat,
                   MAX(timestamp) as last_chat
                   FROM conversations WHERE user_id = %s""",
                (user_id,)
            )
            row = self.cursor.fetchone()
            return {
                "total_messages": row[0] or 0,
                "first_chat": row[1].isoformat() if row[1] else None,
                "last_chat": row[2].isoformat() if row[2] else None
            }
        except pymysql.MySQLError as e:
            self.logger.error(f"获取对话统计失败: {e}")
            return {"total_messages": 0, "first_chat": None, "last_chat": None}

    def close(self):
        """关闭数据库连接"""
        try:
            self.connection.close()
            self.logger.info("UserManager MySQL 连接已关闭")
        except pymysql.MySQLError as e:
            self.logger.error(f"关闭连接失败: {e}")