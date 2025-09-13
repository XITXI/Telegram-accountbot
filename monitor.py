import asyncio
import logging
from typing import Dict, List
from datetime import datetime
from database import Database
from aliyun_client import AliyunClient
from config import Config

logger = logging.getLogger(__name__)

class BalanceMonitor:
    def __init__(self, bot, db: Database, aliyun_client: AliyunClient):
        self.bot = bot
        self.db = db
        self.aliyun_client = aliyun_client
        self.monitoring = False
        self.monitor_task = None
    
    async def start_monitoring(self):
        """启动监控"""
        if self.monitoring:
            logger.info("监控已在运行中")
            return
        
        if not self.aliyun_client.is_configured():
            logger.error("阿里云客户端未配置，无法启动监控")
            return
        
        self.monitoring = True
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("余额监控已启动")
    
    async def stop_monitoring(self):
        """停止监控"""
        if not self.monitoring:
            return
        
        self.monitoring = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("余额监控已停止")
    
    async def _monitor_loop(self):
        """监控循环"""
        while self.monitoring:
            try:
                await self._check_all_accounts()
                await asyncio.sleep(Config.CHECK_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"监控循环出错: {e}")
                await asyncio.sleep(60)  # 出错后等待1分钟再继续
    
    async def _check_all_accounts(self):
        """检查所有账号余额"""
        accounts = self.db.get_aliyun_accounts()
        if not accounts:
            return
        
        logger.info(f"开始检查 {len(accounts)} 个账号的余额")
        
        for account in accounts:
            try:
                await self._check_account_balance(account)
            except Exception as e:
                logger.error(f"检查账号 {account['uid']} 余额失败: {e}")
    
    async def _check_account_balance(self, account: Dict):
        """检查单个账号余额"""
        uid = account['uid']
        remark = account['remark']
        low_threshold = account['low_balance_threshold']
        drop_threshold = account['drop_threshold']
        last_balance = account['last_balance']
        
        # 获取当前余额
        credit_info = self.aliyun_client.get_credit_info(uid)
        if not credit_info or not credit_info.get('success'):
            logger.error(f"获取账号 {uid} 余额失败")
            return
        
        current_balance = credit_info['available_credit']
        
        # 更新数据库中的余额
        self.db.update_balance(uid, current_balance)
        
        # 检查低余额告警
        if current_balance <= low_threshold:
            await self._send_low_balance_alert(account, current_balance)
        
        # 检查余额突降告警
        if last_balance > 0 and (last_balance - current_balance) >= drop_threshold:
            await self._send_drop_alert(account, current_balance, last_balance)
        
        logger.debug(f"账号 {uid}({remark}) 余额检查完成: {current_balance}")
    
    async def _send_low_balance_alert(self, account: Dict, current_balance: float):
        """发送低余额告警"""
        uid = account['uid']
        remark = account['remark']
        threshold = account['low_balance_threshold']
        
        message = (
            f"🚨 低余额告警\n\n"
            f"账号: {remark} ({uid})\n"
            f"当前余额: ¥{current_balance:.2f}\n"
            f"告警阈值: ¥{threshold:.2f}\n"
            f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        # 记录告警
        self.db.record_alert(uid, 'low_balance', current_balance, threshold, message)
        
        # 发送给所有管理员
        for admin_id in Config.ADMIN_CHAT_IDS:
            try:
                await self.bot.send_message(chat_id=admin_id, text=message)
            except Exception as e:
                logger.error(f"发送低余额告警给管理员 {admin_id} 失败: {e}")
    
    async def _send_drop_alert(self, account: Dict, current_balance: float, last_balance: float):
        """发送余额突降告警"""
        uid = account['uid']
        remark = account['remark']
        threshold = account['drop_threshold']
        drop_amount = last_balance - current_balance
        
        message = (
            f"余额突降告警\n\n"
            f"账号: {remark} ({uid})\n"
            f"上次余额: ¥{last_balance:.2f}\n"
            f"当前余额: ¥{current_balance:.2f}\n"
            f"下降金额: ¥{drop_amount:.2f}\n"
            f"告警阈值: ¥{threshold:.2f}\n"
            f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        # 记录告警
        self.db.record_alert(uid, 'balance_drop', current_balance, threshold, message)
        
        # 发送给所有管理员
        for admin_id in Config.ADMIN_CHAT_IDS:
            try:
                await self.bot.send_message(chat_id=admin_id, text=message)
            except Exception as e:
                logger.error(f"发送余额突降告警给管理员 {admin_id} 失败: {e}")
    
    def is_monitoring(self) -> bool:
        """检查是否正在监控"""
        return self.monitoring
