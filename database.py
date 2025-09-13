import sqlite3
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import logging
from config import Config

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or Config.DATABASE_PATH
        self.init_database()

    def init_database(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 创建阿里云账号绑定表
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS aliyun_accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid TEXT UNIQUE NOT NULL,
                    remark TEXT NOT NULL,
                    low_balance_threshold REAL NOT NULL,
                    drop_threshold REAL NOT NULL,
                    last_balance REAL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # 创建余额历史记录表
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS balance_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid TEXT NOT NULL,
                    balance REAL NOT NULL,
                    check_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (uid) REFERENCES aliyun_accounts (uid)
                )
            """
            )

            # 创建告警记录表
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS alert_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    balance REAL NOT NULL,
                    threshold REAL NOT NULL,
                    message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (uid) REFERENCES aliyun_accounts (uid)
                )
            """
            )

            # 创建系统配置表
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS system_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            conn.commit()

    def bind_aliyun_account(
        self, uid: str, remark: str, low_threshold: float, drop_threshold: float
    ) -> bool:
        """绑定阿里云账号"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO aliyun_accounts 
                    (uid, remark, low_balance_threshold, drop_threshold, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (uid, remark, low_threshold, drop_threshold, datetime.now()),
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"绑定阿里云账号失败: {e}")
            return False

    def unbind_aliyun_account(self, uid: str) -> bool:
        """解绑阿里云账号"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM aliyun_accounts WHERE uid = ?", (uid,))
                cursor.execute("DELETE FROM balance_history WHERE uid = ?", (uid,))
                cursor.execute("DELETE FROM alert_history WHERE uid = ?", (uid,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"解绑阿里云账号失败: {e}")
            return False

    def get_aliyun_accounts(self) -> List[Dict]:
        """获取所有绑定的阿里云账号"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT uid, remark, low_balance_threshold, drop_threshold,
                           last_balance, created_at, updated_at
                    FROM aliyun_accounts
                    ORDER BY created_at DESC
                """
                )
                rows = cursor.fetchall()
                return [
                    {
                        "uid": row[0],
                        "remark": row[1],
                        "low_balance_threshold": row[2],
                        "drop_threshold": row[3],
                        "last_balance": row[4],
                        "created_at": row[5],
                        "updated_at": row[6],
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"获取阿里云账号列表失败: {e}")
            return []

    def get_aliyun_account(self, uid: str) -> Optional[Dict]:
        """获取指定的阿里云账号信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT uid, remark, low_balance_threshold, drop_threshold,
                           last_balance, created_at, updated_at
                    FROM aliyun_accounts WHERE uid = ?
                """,
                    (uid,),
                )
                row = cursor.fetchone()
                if row:
                    return {
                        "uid": row[0],
                        "remark": row[1],
                        "low_balance_threshold": row[2],
                        "drop_threshold": row[3],
                        "last_balance": row[4],
                        "created_at": row[5],
                        "updated_at": row[6],
                    }
                return None
        except Exception as e:
            logger.error(f"获取阿里云账号信息失败: {e}")
            return None

    def update_balance(self, uid: str, balance: float) -> bool:
        """更新账号余额"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # 更新账号表中的最新余额
                cursor.execute(
                    """
                    UPDATE aliyun_accounts
                    SET last_balance = ?, updated_at = ?
                    WHERE uid = ?
                """,
                    (balance, datetime.now(), uid),
                )

                # 记录余额历史
                cursor.execute(
                    """
                    INSERT INTO balance_history (uid, balance)
                    VALUES (?, ?)
                """,
                    (uid, balance),
                )

                conn.commit()
                return True
        except Exception as e:
            logger.error(f"更新余额失败: {e}")
            return False

    def update_threshold(self, uid: str, threshold_type: str, value: float) -> bool:
        """更新阈值"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                if threshold_type == "low":
                    cursor.execute(
                        """
                        UPDATE aliyun_accounts
                        SET low_balance_threshold = ?, updated_at = ?
                        WHERE uid = ?
                    """,
                        (value, datetime.now(), uid),
                    )
                elif threshold_type == "drop":
                    cursor.execute(
                        """
                        UPDATE aliyun_accounts
                        SET drop_threshold = ?, updated_at = ?
                        WHERE uid = ?
                    """,
                        (value, datetime.now(), uid),
                    )
                else:
                    return False

                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"更新阈值失败: {e}")
            return False

    def record_alert(
        self, uid: str, alert_type: str, balance: float, threshold: float, message: str
    ) -> bool:
        """记录告警"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO alert_history (uid, alert_type, balance, threshold, message)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (uid, alert_type, balance, threshold, message),
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"记录告警失败: {e}")
            return False

    def set_config(self, key: str, value: str) -> bool:
        """设置系统配置"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO system_config (key, value, updated_at)
                    VALUES (?, ?, ?)
                """,
                    (key, value, datetime.now()),
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"设置配置失败: {e}")
            return False

    def get_config(self, key: str) -> Optional[str]:
        """获取系统配置"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM system_config WHERE key = ?", (key,))
                row = cursor.fetchone()
                return row[0] if row else None
        except Exception as e:
            logger.error(f"获取配置失败: {e}")
            return None
