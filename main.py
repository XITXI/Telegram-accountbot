#!/usr/bin/env python3
"""
阿里云余额监控Telegram机器人
专为阿里云分销商设计，支持实时监控客户账户余额，低余额告警和余额突降告警
"""

import logging
import asyncio
import signal
import sys
from functools import wraps
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.request import HTTPXRequest
from aiohttp import web
from config import Config
from database import Database
from aliyun_client import AliyunClient
from monitor import BalanceMonitor
from bot_handlers import BotHandlers

import nest_asyncio
from dotenv import load_dotenv

# 嵌套异步io
nest_asyncio.apply()

# 加载环境变量
load_dotenv()

# 修复Windows下asyncio事件循环关闭问题
if sys.platform == "win32":
    from asyncio.proactor_events import _ProactorBasePipeTransport

    def silence_event_loop_closed(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except RuntimeError as e:
                if str(e) != "Event loop is closed":
                    raise

        return wrapper

    _ProactorBasePipeTransport.__del__ = silence_event_loop_closed(
        _ProactorBasePipeTransport.__del__
    )


# 配置日志
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)


class AliyunBalanceBot:
    def __init__(self):
        self.application = None
        self.db = None
        self.aliyun_client = None
        self.monitor = None
        self.handlers = None
        self.running = False

    async def initialize(self):
        """初始化机器人"""
        try:
            # 验证配置
            if not Config.validate_config():
                logger.error("配置验证失败，请检查环境变量")
                return False

            # 初始化数据库
            self.db = Database()
            logger.info("数据库初始化完成")

            # 初始化阿里云客户端
            self.aliyun_client = AliyunClient()

            # 尝试从数据库加载凭证
            saved_ak = self.db.get_config("aliyun_ak")
            saved_sk = self.db.get_config("aliyun_sk")
            if saved_ak and saved_sk:
                self.aliyun_client.set_credentials(saved_ak, saved_sk)
                logger.info("已加载保存的阿里云凭证")

            # 初始化监控器
            self.monitor = BalanceMonitor(None, self.db, self.aliyun_client)

            # 初始化处理器
            self.handlers = BotHandlers(self.db, self.aliyun_client, self.monitor)

            # 创建Telegram应用
            request = None
            if Config.PROXY_URL:
                request = HTTPXRequest(proxy=Config.PROXY_URL)

            self.application = (
                Application.builder().token(Config.BOT_TOKEN).request(request).build()
            )

            # 设置监控器的bot引用
            self.monitor.bot = self.application.bot

            # 注册命令处理器
            self._register_handlers()

            logger.info("机器人初始化完成")
            return True

        except Exception as e:
            logger.error(f"初始化失败: {e}")
            return False

    def _register_handlers(self):
        """注册命令处理器"""
        # 命令处理器
        self.application.add_handler(
            CommandHandler("start", self.handlers.start_command)
        )
        self.application.add_handler(
            CommandHandler("bind_aliyun", self.handlers.bind_aliyun_command)
        )
        self.application.add_handler(
            CommandHandler("unbind_aliyun", self.handlers.unbind_aliyun_command)
        )
        self.application.add_handler(
            CommandHandler("list_aliyun", self.handlers.list_aliyun_command)
        )
        self.application.add_handler(
            CommandHandler("aliyun_balance", self.handlers.aliyun_balance_command)
        )
        self.application.add_handler(
            CommandHandler("set_aliyun_drop", self.handlers.set_aliyun_drop_command)
        )
        self.application.add_handler(
            CommandHandler("set_aliyun_low", self.handlers.set_aliyun_low_command)
        )
        self.application.add_handler(
            CommandHandler("monitor_status", self.handlers.monitor_status_command)
        )
        self.application.add_handler(
            CommandHandler("start_monitor", self.handlers.start_monitor_command)
        )
        self.application.add_handler(
            CommandHandler("stop_monitor", self.handlers.stop_monitor_command)
        )
        self.application.add_handler(CommandHandler("help", self.handlers.help_command))

        # 消息处理器
        self.application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND, self.handlers.handle_message
            )
        )

        logger.info("命令处理器注册完成")

    async def health_check(self, request):
        """健康检查端点"""
        return web.json_response(
            {
                "status": "healthy",
                "monitoring": self.monitor.is_monitoring() if self.monitor else False,
                "aliyun_configured": (
                    self.aliyun_client.is_configured() if self.aliyun_client else False
                ),
            }
        )

    async def start_webhook(self):
        """启动Webhook模式"""
        health_runner = None
        try:
            # 设置webhook
            webhook_url = f"{Config.WEBHOOK_URL}/webhook"
            await self.application.bot.set_webhook(
                url=webhook_url, allowed_updates=Update.ALL_TYPES
            )

            # 创建健康检查服务器
            app = web.Application()
            app.router.add_get("/health", self.health_check)

            # 启动健康检查服务器（在不同端口）
            health_runner = web.AppRunner(app)
            await health_runner.setup()
            health_site = web.TCPSite(health_runner, "0.0.0.0", Config.PORT + 1)
            await health_site.start()
            logger.info(f"健康检查服务器启动在端口: {Config.PORT + 1}")

            # 使用标准的run_webhook方法
            await self.application.run_webhook(
                listen="0.0.0.0",
                port=Config.PORT,
                url_path="/webhook",
                webhook_url=webhook_url,
            )

        except Exception as e:
            logger.error(f"启动Webhook失败: {e}")
            # 清理健康检查服务器
            if health_runner:
                try:
                    await health_runner.cleanup()
                except Exception as cleanup_e:
                    logger.error(f"清理健康检查服务器失败: {cleanup_e}")
            raise

    async def start_polling(self):
        """启动轮询模式（用于开发测试）"""
        try:
            # 删除webhook
            await self.application.bot.delete_webhook()

            # 启动轮询
            await self.application.run_polling(
                allowed_updates=Update.ALL_TYPES, drop_pending_updates=True
            )

        except Exception as e:
            logger.error(f"启动轮询失败: {e}")
            raise

    async def start(self, use_webhook=True):
        """启动机器人"""
        if not await self.initialize():
            return False

        self.running = True

        try:
            # 启动自动监控（如果配置了）
            if Config.ENABLE_MONITORING and self.aliyun_client.is_configured():
                await self.monitor.start_monitoring()
                logger.info("自动监控已启动")

            # 启动机器人
            if use_webhook:
                logger.info(f"启动Webhook模式，端口: {Config.PORT}")
                await self.start_webhook()
            else:
                logger.info("启动轮询模式")
                await self.start_polling()

        except Exception as e:
            logger.error(f"启动机器人失败: {e}")
            return False

        return True

    async def stop(self):
        """停止机器人"""
        if not self.running:
            return

        logger.info("正在停止机器人...")
        self.running = False

        try:
            # 停止监控
            if self.monitor:
                try:
                    await self.monitor.stop_monitoring()
                    logger.info("监控已停止")
                except Exception as e:
                    logger.error(f"停止监控时出错: {e}")

            # 停止应用
            if self.application:
                try:
                    # 先删除webhook
                    await self.application.bot.delete_webhook()
                    logger.info("Webhook已删除")
                except Exception as e:
                    logger.error(f"删除Webhook时出错: {e}")

                try:
                    await self.application.stop()
                    await self.application.shutdown()
                    logger.info("Telegram应用已停止")
                except Exception as e:
                    logger.error(f"停止Telegram应用时出错: {e}")

        except Exception as e:
            logger.error(f"停止机器人时出错: {e}")
        finally:
            logger.info("机器人已停止")


# 全局变量
bot_instance = None


def signal_handler(signum, frame):
    """信号处理器"""
    _ = frame  # 忽略未使用的参数
    logger.info(f"收到信号 {signum}，正在关闭...")
    if bot_instance:
        # 创建一个任务来停止机器人
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(bot_instance.stop())
            else:
                asyncio.run(bot_instance.stop())
        except Exception as e:
            logger.error(f"停止机器人时出错: {e}")
    sys.exit(0)


async def main():
    """主函数"""
    global bot_instance

    try:
        # 设置信号处理器
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # 创建并启动机器人
        bot_instance = AliyunBalanceBot()

        # 根据环境变量决定使用webhook还是polling
        # 在Windows环境下，优先使用轮询模式以避免事件循环问题
        use_webhook = Config.WEBHOOK_URL is not None and sys.platform != "win32"

        logger.info("=== 阿里云余额监控机器人启动 ===")
        logger.info(f"模式: {'Webhook' if use_webhook else 'Polling'}")
        logger.info(f"管理员ID: {Config.ADMIN_CHAT_IDS}")
        logger.info(f"检查间隔: {Config.CHECK_INTERVAL}秒")

        success = await bot_instance.start(use_webhook=use_webhook)

        if not success:
            logger.error("机器人启动失败")
            return False

        return True

    except Exception as e:
        logger.error(f"主函数执行失败: {e}")
        if bot_instance:
            await bot_instance.stop()
        return False


if __name__ == "__main__":
    try:
        if sys.platform == "win32":
            # Windows环境下的特殊处理
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

            # 创建新的事件循环而不是获取现有的
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                success = loop.run_until_complete(main())
            except RuntimeError as e:
                if "Cannot close a running event loop" in str(e):
                    logger.warning("检测到事件循环关闭问题，尝试替代方案")
                    # 使用asyncio.run作为备选
                    success = asyncio.run(main())
                else:
                    raise
            finally:
                try:
                    # 安全关闭事件循环
                    if not loop.is_closed():
                        loop.close()
                except Exception as close_e:
                    logger.warning(f"关闭事件循环时出现警告: {close_e}")
        else:
            # 其他平台使用标准方式
            success = asyncio.run(main())

        if not success:
            logger.error("机器人启动失败")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("程序被用户中断")
        if bot_instance:
            try:
                # 优雅关闭
                if sys.platform == "win32":
                    loop = asyncio.get_event_loop()
                    if not loop.is_closed():
                        loop.run_until_complete(bot_instance.stop())
                else:
                    asyncio.run(bot_instance.stop())
            except Exception as stop_e:
                logger.error(f"关闭机器人时出错: {stop_e}")
    except Exception as e:
        logger.error(f"程序异常退出: {e}")
        if bot_instance:
            try:
                # 尝试优雅关闭
                asyncio.run(bot_instance.stop())
            except Exception as stop_e:
                logger.error(f"异常关闭机器人时出错: {stop_e}")
        sys.exit(1)
