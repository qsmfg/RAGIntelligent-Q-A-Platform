# -*- coidng:utf-8 -*-
# 导入 MySQL 和 Redis 客户端，管理数据库和缓存
from mysql_qa import MySQLClient, RedisClient, BM25Search
# 导入 RAG 系统组件，用于知识库检索和答案生成
from rag_qa import VectorStore, RAGSystem
# 导入配置和日志工具，用于系统配置和日志记录
from base import logger, Config
# 导入 OpenAI 客户端，用于调用 DashScope API
from openai import OpenAI
# 导入时间库，用于记录处理时间
import time
# 导入 UUID 库，生成唯一会话 ID
import uuid
# 导入 pymysql 错误处理，用于数据库操作的异常捕获
import pymysql


class IntegratedQASystem:
    def __init__(self):
        # 初始化日志工具，用于记录系统运行信息
        self.logger = logger
        # 初始化配置对象，加载系统参数
        self.config = Config()
        # 初始化 MySQL 客户端，用于数据库操作
        self.mysql_client = MySQLClient()
        # 初始化 Redis 客户端，用于缓存管理
        self.redis_client = RedisClient()
        # 初始化 BM25 搜索模块，结合 MySQL 和 Redis
        self.bm25_search = BM25Search(self.redis_client, self.mysql_client)
        try:
            # 初始化 OpenAI 客户端，连接 DashScope API
            self.client = OpenAI(api_key=self.config.DASHSCOPE_API_KEY,
                                 base_url=self.config.DASHSCOPE_BASE_URL)
        except Exception as e:
            # 记录 OpenAI 初始化失败的错误日志
            self.logger.error(f"OpenAI 客户端初始化失败: {e}")
            # 抛出异常，终止初始化
            raise
        # 初始化向量存储，用于 RAG 系统的知识库管理
        self.vector_store = VectorStore()
        # 初始化 RAG 系统，传入向量存储和 DashScope API 调用函数
        self.rag_system = RAGSystem(self.vector_store, self.call_dashscope)
        # 初始化对话历史表，用于存储会话记录
        self.init_conversation_table()

    def init_conversation_table(self):
        """初始化MySQL中的conversations表，用于存储对话历史"""
        try:
            # 创建 conversations 表，包含 user_id 列用于用户隔离
            self.mysql_client.cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    session_id VARCHAR(36) NOT NULL,
                    user_id INT NOT NULL DEFAULT 0,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    INDEX idx_session_id (session_id),
                    INDEX idx_user_id (user_id)
                )
            """)
            self.mysql_client.connection.commit()

            # 容错迁移：为已有 conversations 表添加 user_id 列（如果不存在）
            try:
                self.mysql_client.cursor.execute("""
                    ALTER TABLE conversations ADD COLUMN user_id INT NOT NULL DEFAULT 0 AFTER session_id
                """)
                self.mysql_client.connection.commit()
                self.logger.info("conversations 表已添加 user_id 列")
            except pymysql.MySQLError:
                # 列已存在，忽略错误
                pass

            # 尝试添加 user_id 索引（如果不存在）
            try:
                self.mysql_client.cursor.execute("""
                    ALTER TABLE conversations ADD INDEX idx_user_id (user_id)
                """)
                self.mysql_client.connection.commit()
            except pymysql.MySQLError:
                pass

            self.logger.info("对话历史表初始化成功")
        except pymysql.MySQLError as e:
            self.logger.error(f"初始化对话历史表失败: {e}")
            raise

    def call_dashscope(self, prompt):
        """调用DashScope API生成答案（流式输出）"""
        try:
            completion = self.client.chat.completions.create(
                model=self.config.LLM_MODEL,
                messages=[
                    {"role": "system", "content": "你是一个有用的助手。"},
                    {"role": "user", "content": prompt},
                ],
                timeout=30,
                stream=True
            )
            for chunk in completion:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    yield content
        except Exception as e:
            self.logger.error(f"LLM调用失败: {e}")
            return f"错误：LLM调用失败 - {e}"

    def _fetch_recent_history(self, session_id, user_id):
        """获取最近5轮对话历史，按用户隔离"""
        try:
            self.mysql_client.cursor.execute("""
                      SELECT question, answer
                      FROM conversations
                      WHERE session_id = %s AND user_id = %s
                      ORDER BY timestamp DESC
                      LIMIT %s
                  """, (session_id, user_id, 5))
            history = [{"question": row[0], "answer": row[1]} for row in self.mysql_client.cursor.fetchall()]
            return history[::-1]

        except pymysql.MySQLError as e:
            self.logger.error(f"获取对话历史失败: {e}")
            return []

    def get_session_history(self, session_id, user_id):
        """从MySQL获取会话历史（按用户隔离）"""
        return self._fetch_recent_history(session_id, user_id)

    def update_session_history(self, session_id: str, question: str, answer: str, user_id: int) -> list:
        """更新会话历史到MySQL，保留最近5轮对话（按用户隔离）"""
        try:
            # 插入新的对话记录
            self.mysql_client.cursor.execute("""
                INSERT INTO conversations (session_id, user_id, question, answer, timestamp)
                VALUES (%s, %s, %s, %s, NOW())
            """, (session_id, user_id, question, answer))
            # 获取更新后的对话历史
            history = self._fetch_recent_history(session_id, user_id)
            # 删除超出 5 轮的旧记录（仅限该用户）
            self.mysql_client.cursor.execute("""
                DELETE FROM conversations
                WHERE session_id = %s AND user_id = %s AND id NOT IN (
                    SELECT id FROM (
                        SELECT id
                        FROM conversations
                        WHERE session_id = %s AND user_id = %s
                        ORDER BY timestamp DESC
                        LIMIT %s
                    ) AS sub
                )
            """, (session_id, user_id, session_id, user_id, 5))
            self.mysql_client.connection.commit()
            self.logger.info(f"会话 {session_id} 历史更新成功")
            return history
        except pymysql.MySQLError as e:
            self.logger.error(f"更新会话历史失败: {e}")
            self.mysql_client.connection.rollback()
            raise
        except Exception as e:
            self.logger.error(f"更新会话历史意外错误: {e}")
            self.mysql_client.connection.rollback()
            raise

    def clear_session_history(self, session_id, user_id):
        """清除指定会话的历史记录（按用户隔离）"""
        try:
            self.mysql_client.cursor.execute(
                "DELETE FROM conversations WHERE session_id = %s AND user_id = %s",
                (session_id, user_id)
            )
            self.mysql_client.connection.commit()
            self.logger.info(f"会话 {session_id} 历史已清除")
            return True
        except pymysql.MySQLError as e:
            self.logger.error(f"清除会话历史失败: {e}")
            self.mysql_client.connection.rollback()
            return False

    def query(self, query, source_filter=None, session_id=None, user_id=None):
        """查询集成系统，支持对话历史和流式输出"""
        start_time = time.time()
        self.logger.info(f"处理查询: '{query}' (会话ID: {session_id}, 用户ID: {user_id})")

        # 获取对话历史，按用户隔离
        history = self.get_session_history(session_id, user_id) if session_id and user_id else []

        # 执行 BM25 搜索，获取答案和是否需要 RAG 的标志
        answer, need_rag = self.bm25_search.search(query, threshold=0.85)

        if answer:
            self.logger.info(f"MySQL答案: {answer}")
            if session_id and user_id:
                self.update_session_history(session_id, query, answer, user_id)
            processing_time = time.time() - start_time
            self.logger.info(f"查询处理耗时 {processing_time:.2f}秒")
            yield answer, True
        elif need_rag:
            self.logger.info("无可靠MySQL答案，回退到RAG")
            collected_answer = ""
            for token in self.rag_system.generate_answer(query, source_filter=source_filter, history=history):
                collected_answer += token
                yield token, False
            if session_id and user_id:
                self.update_session_history(session_id, query, collected_answer, user_id)
            processing_time = time.time() - start_time
            self.logger.info(f"查询处理耗时 {processing_time:.2f}秒")
            yield "", True
        else:
            self.logger.info("未找到答案")
            processing_time = time.time() - start_time
            self.logger.info(f"查询处理耗时 {processing_time:.2f}秒")
            yield "未找到答案", True


if __name__ == "__main__":
    new_qa_system = IntegratedQASystem()
    results = new_qa_system._fetch_recent_history(session_id="603db0cf-cfa0-4433-9078-f37f3b29fd7c", user_id=0)
    print(results)