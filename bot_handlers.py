import logging
from telegram import Update
from telegram.ext import ContextTypes
from database import Database
from aliyun_client import AliyunClient
from monitor import BalanceMonitor
from config import Config
from datetime import datetime
import re

logger = logging.getLogger(__name__)


class BotHandlers:
    def __init__(
        self, db: Database, aliyun_client: AliyunClient, monitor: BalanceMonitor
    ):
        self.db = db
        self.aliyun_client = aliyun_client
        self.monitor = monitor
        self.waiting_for_credentials = {}  # 存储等待输入凭证的用户

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /start 命令"""
        chat_id = update.effective_chat.id

        if not Config.is_admin(chat_id):
            await update.message.reply_text(" 您没有权限使用此机器人")
            return

        if not self.aliyun_client.is_configured():
            await update.message.reply_text(
                " 欢迎使用阿里云余额监控机器人！\n\n"
                "首次使用需要配置阿里云凭证。\n"
                "请发送您的阿里云 Access Key ID 和 Access Key Secret，格式如下：\n\n"
                "`AK:您的AccessKeyID`\n"
                "`SK:您的AccessKeySecret`\n\n"
                "例如：\n"
                "`AK:LTAI4GxxxxxxxxxxxxxxxxxxxxG`\n"
                "`SK:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`\n\n"
                " 请确保在私聊中发送，避免泄露凭证！",
                parse_mode="Markdown",
            )
            self.waiting_for_credentials[chat_id] = True
        else:
            await self._show_main_menu(update)

    async def handle_credentials(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """处理凭证输入"""
        chat_id = update.effective_chat.id
        text = update.message.text

        if chat_id not in self.waiting_for_credentials:
            return

        # 解析AK和SK
        ak_match = re.search(r"AK:([A-Za-z0-9]+)", text)
        sk_match = re.search(r"SK:([A-Za-z0-9]+)", text)

        if not ak_match or not sk_match:
            await update.message.reply_text(
                " 格式错误！请按照以下格式发送：\n\n"
                "`AK:您的AccessKeyID`\n"
                "`SK:您的AccessKeySecret`",
                parse_mode="Markdown",
            )
            return

        access_key_id = ak_match.group(1)
        access_key_secret = sk_match.group(1)

        # 设置凭证
        self.aliyun_client.set_credentials(access_key_id, access_key_secret)

        # 测试连接
        if self.aliyun_client.test_connection():
            await update.message.reply_text(" 阿里云凭证配置成功！")
            del self.waiting_for_credentials[chat_id]

            # 保存凭证到数据库（加密存储）
            self.db.set_config("aliyun_ak", access_key_id)
            self.db.set_config("aliyun_sk", access_key_secret)

            await self._show_main_menu(update)

            # 如果配置了自动启动监控，则启动
            if Config.ENABLE_MONITORING:
                await self.monitor.start_monitoring()
                await update.message.reply_text(" 自动监控已启动")
        else:
            await update.message.reply_text(" 阿里云凭证验证失败，请检查后重新输入")

    async def _show_main_menu(self, update: Update):
        """显示主菜单"""
        menu_text = (
            " 阿里云余额监控机器人\n\n"
            " 可用命令：\n"
            "/bind_aliyun [UID] [备注] [低余额阈值] [突降阈值] - 绑定阿里云账号\n"
            "/unbind_aliyun [UID] - 解绑阿里云账号\n"
            "/list_aliyun - 查看绑定列表\n"
            "/aliyun_balance - 查询所有账号余额\n"
            "/set_aliyun_drop [UID] [新突降阈值] - 设置突降阈值\n"
            "/set_aliyun_low [UID] [新低余额阈值] - 设置低余额阈值\n"
            "/monitor_status - 查看监控状态\n"
            "/start_monitor - 启动监控\n"
            "/stop_monitor - 停止监控\n"
            "/help - 显示帮助信息"
        )
        await update.message.reply_text(menu_text)

    async def bind_aliyun_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """处理 /bind_aliyun 命令"""
        chat_id = update.effective_chat.id

        if not Config.is_admin(chat_id):
            await update.message.reply_text(" 您没有权限使用此命令")
            return

        if not self.aliyun_client.is_configured():
            await update.message.reply_text(" 请先配置阿里云凭证")
            return

        args = context.args
        if len(args) != 4:
            await update.message.reply_text(
                " 参数错误！\n\n"
                "正确格式：\n"
                "/bind_aliyun [UID] [备注] [低余额阈值] [突降阈值]\n\n"
                "例如：\n"
                "/bind_aliyun 123456789 客户A 1000 500"
            )
            return

        uid, remark, low_threshold_str, drop_threshold_str = args

        try:
            low_threshold = float(low_threshold_str)
            drop_threshold = float(drop_threshold_str)
        except ValueError:
            await update.message.reply_text(" 阈值必须是数字")
            return

        # 验证UID是否有效
        credit_info = self.aliyun_client.get_credit_info(uid)
        if not credit_info or not credit_info.get("success"):
            await update.message.reply_text(
                f" 无法获取UID {uid} 的信息，请检查UID是否正确"
            )
            return

        # 绑定账号
        if self.db.bind_aliyun_account(uid, remark, low_threshold, drop_threshold):
            # 更新初始余额
            current_balance = credit_info["available_credit"]
            self.db.update_balance(uid, current_balance)

            await update.message.reply_text(
                f" 绑定成功！\n\n"
                f"UID: {uid}\n"
                f"备注: {remark}\n"
                f"当前余额: ¥{current_balance:.2f}\n"
                f"低余额阈值: ¥{low_threshold:.2f}\n"
                f"突降阈值: ¥{drop_threshold:.2f}"
            )
        else:
            await update.message.reply_text(" 绑定失败，请稍后重试")

    async def unbind_aliyun_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """处理 /unbind_aliyun 命令"""
        chat_id = update.effective_chat.id

        if not Config.is_admin(chat_id):
            await update.message.reply_text(" 您没有权限使用此命令")
            return

        args = context.args
        if len(args) != 1:
            await update.message.reply_text(
                " 参数错误！\n\n"
                "正确格式：\n"
                "/unbind_aliyun [UID]\n\n"
                "例如：\n"
                "/unbind_aliyun 123456789"
            )
            return

        uid = args[0]

        if self.db.unbind_aliyun_account(uid):
            await update.message.reply_text(f" 已解绑UID: {uid}")
        else:
            await update.message.reply_text(f" 解绑失败，UID {uid} 可能不存在")

    async def list_aliyun_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """处理 /list_aliyun 命令"""
        chat_id = update.effective_chat.id

        if not Config.is_admin(chat_id):
            await update.message.reply_text(" 您没有权限使用此命令")
            return

        accounts = self.db.get_aliyun_accounts()

        if not accounts:
            await update.message.reply_text(" 暂无绑定的阿里云账号")
            return

        message_lines = [" 阿里云账号列表：\n"]

        for i, account in enumerate(accounts, 1):
            message_lines.append(
                f"{i}. {account['remark']} ({account['uid']})\n"
                f"   余额: ¥{account['last_balance']:.2f}\n"
                f"   低余额阈值: ¥{account['low_balance_threshold']:.2f}\n"
                f"   突降阈值: ¥{account['drop_threshold']:.2f}\n"
                f"   更新时间: {account['updated_at']}\n"
            )

        message = "\n".join(message_lines)
        await update.message.reply_text(message)

    async def aliyun_balance_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """处理 /aliyun_balance 命令"""
        chat_id = update.effective_chat.id

        if not Config.is_admin(chat_id):
            await update.message.reply_text(" 您没有权限使用此命令")
            return

        if not self.aliyun_client.is_configured():
            await update.message.reply_text(" 请先配置阿里云凭证")
            return

        accounts = self.db.get_aliyun_accounts()

        if not accounts:
            await update.message.reply_text(" 暂无绑定的阿里云账号")
            return

        await update.message.reply_text(" 正在查询余额，请稍候...")

        message_lines = [" 阿里云账号余额：\n"]

        for i, account in enumerate(accounts, 1):
            uid = account["uid"]
            remark = account["remark"]

            credit_info = self.aliyun_client.get_credit_info(uid)

            if credit_info and credit_info.get("success"):
                balance = credit_info["available_credit"]
                # 更新数据库中的余额
                self.db.update_balance(uid, balance)

                status = "🟢"
                if balance <= account["low_balance_threshold"]:
                    status = "🔴"
                elif balance <= account["low_balance_threshold"] * 1.5:
                    status = "🟡"

                message_lines.append(
                    f"{status} {i}. {remark} ({uid})\n"
                    f"   余额: ¥{balance:.2f}\n"
                    f"   信用额度: ¥{credit_info.get('credit_line', 0):.2f}\n"
                )
            else:
                message_lines.append(
                    f" {i}. {remark} ({uid})\n"
                    f"   查询失败: {credit_info.get('error', '未知错误') if credit_info else '网络错误'}\n"
                )

        message = "\n".join(message_lines)
        await update.message.reply_text(message)

    async def set_aliyun_drop_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """处理 /set_aliyun_drop 命令"""
        chat_id = update.effective_chat.id

        if not Config.is_admin(chat_id):
            await update.message.reply_text(" 您没有权限使用此命令")
            return

        args = context.args
        if len(args) != 2:
            await update.message.reply_text(
                " 参数错误！\n\n"
                "正确格式：\n"
                "/set_aliyun_drop [UID] [新突降阈值]\n\n"
                "例如：\n"
                "/set_aliyun_drop 123456789 800"
            )
            return

        uid, threshold_str = args

        try:
            threshold = float(threshold_str)
        except ValueError:
            await update.message.reply_text(" 阈值必须是数字")
            return

        if self.db.update_threshold(uid, "drop", threshold):
            await update.message.reply_text(
                f" 已更新UID {uid} 的突降阈值为 ¥{threshold:.2f}"
            )
        else:
            await update.message.reply_text(f" 更新失败，UID {uid} 可能不存在")

    async def set_aliyun_low_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """处理 /set_aliyun_low 命令"""
        chat_id = update.effective_chat.id

        if not Config.is_admin(chat_id):
            await update.message.reply_text(" 您没有权限使用此命令")
            return

        args = context.args
        if len(args) != 2:
            await update.message.reply_text(
                " 参数错误！\n\n"
                "正确格式：\n"
                "/set_aliyun_low [UID] [新低余额阈值]\n\n"
                "例如：\n"
                "/set_aliyun_low 123456789 1200"
            )
            return

        uid, threshold_str = args

        try:
            threshold = float(threshold_str)
        except ValueError:
            await update.message.reply_text(" 阈值必须是数字")
            return

        if self.db.update_threshold(uid, "low", threshold):
            await update.message.reply_text(
                f" 已更新UID {uid} 的低余额阈值为 ¥{threshold:.2f}"
            )
        else:
            await update.message.reply_text(f" 更新失败，UID {uid} 可能不存在")

    async def monitor_status_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """处理 /monitor_status 命令"""
        chat_id = update.effective_chat.id

        if not Config.is_admin(chat_id):
            await update.message.reply_text(" 您没有权限使用此命令")
            return

        status = "🟢 运行中" if self.monitor.is_monitoring() else "🔴 已停止"
        accounts_count = len(self.db.get_aliyun_accounts())

        message = (
            f"监控状态\n\n"
            f"状态: {status}\n"
            f"监控账号数: {accounts_count}\n"
            f"检查间隔: {Config.CHECK_INTERVAL}秒\n"
            f"阿里云连接: {' 正常' if self.aliyun_client.is_configured() else ' 未配置'}"
        )

        await update.message.reply_text(message)

    async def start_monitor_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """处理 /start_monitor 命令"""
        chat_id = update.effective_chat.id

        if not Config.is_admin(chat_id):
            await update.message.reply_text(" 您没有权限使用此命令")
            return

        if not self.aliyun_client.is_configured():
            await update.message.reply_text(" 请先配置阿里云凭证")
            return

        if self.monitor.is_monitoring():
            await update.message.reply_text(" 监控已在运行中")
            return

        await self.monitor.start_monitoring()
        await update.message.reply_text(" 监控已启动")

    async def stop_monitor_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """处理 /stop_monitor 命令"""
        chat_id = update.effective_chat.id

        if not Config.is_admin(chat_id):
            await update.message.reply_text(" 您没有权限使用此命令")
            return

        if not self.monitor.is_monitoring():
            await update.message.reply_text(" 监控已停止")
            return

        await self.monitor.stop_monitoring()
        await update.message.reply_text(" 监控已停止")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /help 命令"""
        await self._show_main_menu(update)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理普通消息"""
        chat_id = update.effective_chat.id

        # 如果用户正在等待输入凭证
        if chat_id in self.waiting_for_credentials:
            await self.handle_credentials(update, context)
            return

        # 其他情况显示帮助
        if Config.is_admin(chat_id):
            await update.message.reply_text("请使用 /help 查看可用命令")
        else:
            await update.message.reply_text(" 您没有权限使用此机器人")
