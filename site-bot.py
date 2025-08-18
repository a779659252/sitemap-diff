import asyncio
import logging
from telegram.ext import Application, CommandHandler
from services.rss.commands import rss_command, init_notifiers
from apps.email_bot import init_task as email_init_task, start_task as email_start_task, scheduled_task as email_scheduled_task


async def main():
    """主函数"""
    # 设置日志
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
    )
    
    # 初始化Telegram Bot
    from core.config import telegram_config
    telegram_token = telegram_config["token"]
    
    if telegram_token:
        application = Application.builder().token(telegram_token).build()
        
        # 初始化通知服务
        await init_notifiers(application.bot)
        
        # 设置处理器
        application.add_handler(CommandHandler("rss", rss_command))
        
        
        logging.info("Telegram Bot已启动")
    else:
        logging.warning("未配置Telegram Bot Token，跳过Telegram Bot初始化")
        # 即使没有Telegram，也要初始化Email通知服务
        await init_notifiers()
    
    # 初始化Discord Bot
    from core.config import discord_config
    discord_token = discord_config["token"]
    
    if discord_token:
        # Discord Bot的初始化逻辑
        logging.info("Discord Bot已启动")
    
    # 初始化Email Bot
    try:
        await email_init_task()
        await email_start_task()
        asyncio.create_task(email_scheduled_task())
        logging.info("Email Bot已启动")
    except Exception as e:
        logging.error(f"Email Bot初始化失败: {str(e)}")
    
    # 启动Telegram Bot（如果配置了）
    if telegram_token:
        await application.run_polling()
    else:
        # 如果没有配置Telegram Bot，保持程序运行
        logging.info("未配置Telegram Bot，程序将持续运行以支持其他服务")
        while True:
            await asyncio.sleep(3600)  # 每小时检查一次


if __name__ == "__main__":
    asyncio.run(main())

