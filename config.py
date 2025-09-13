import os
from dotenv import load_dotenv
from typing import List

# 加载环境变量
load_dotenv()

class Config:
    # Telegram Bot配置
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    WEBHOOK_URL = os.getenv('WEBHOOK_URL')
    PORT = int(os.getenv('PORT', 5000))
    PROXY_URL = os.getenv('PROXY_URL')
    
    # 管理员配置
    ADMIN_CHAT_IDS = [int(id.strip()) for id in os.getenv('ADMIN_CHAT_IDS', '').split(',') if id.strip()]
    
    # 监控配置
    CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', 300))
    ENABLE_MONITORING = os.getenv('ENABLE_MONITORING', 'true').lower() == 'true'
    
    # 数据库配置
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'bot_data.db')
    
    # 阿里云配置（支持环境变量加载 + 运行时更新）
    ALIYUN_ACCESS_KEY_ID = os.getenv('ALIYUN_ACCESS_KEY_ID')
    ALIYUN_ACCESS_KEY_SECRET = os.getenv('ALIYUN_ACCESS_KEY_SECRET')
    # 可选：用于凭证验证的分销商测试UID（如果提供，将用其调用GetCreditInfo）
    ALIYUN_RESELLER_TEST_UID = os.getenv('ALIYUN_RESELLER_TEST_UID')
    
    @classmethod
    def set_aliyun_credentials(cls, access_key_id: str, access_key_secret: str):
        """设置阿里云凭证"""
        cls.ALIYUN_ACCESS_KEY_ID = access_key_id
        cls.ALIYUN_ACCESS_KEY_SECRET = access_key_secret
    
    @classmethod
    def is_admin(cls, chat_id: int) -> bool:
        """检查是否为管理员"""
        return chat_id in cls.ADMIN_CHAT_IDS
    
    @classmethod
    def validate_config(cls) -> bool:
        """验证配置是否完整"""
        required_fields = [
            cls.BOT_TOKEN,
            cls.WEBHOOK_URL,
            cls.ADMIN_CHAT_IDS
        ]
        return all(field for field in required_fields)
