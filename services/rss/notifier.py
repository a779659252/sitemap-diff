import logging
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod


class NotificationService(ABC):
    """通知服务抽象基类"""
    
    @abstractmethod
    async def send_update_notification(
        self,
        url: str,
        new_urls: List[str],
        dated_file: Optional[Path],
        target: Optional[str] = None
    ) -> None:
        """发送更新通知"""
        pass
    
    @abstractmethod
    async def send_message(self, message: str, target: Optional[str] = None) -> None:
        """发送普通消息"""
        pass


class TelegramNotifier(NotificationService):
    """Telegram通知服务"""
    
    def __init__(self, bot):
        self.bot = bot
        from core.config import telegram_config
        self.config = telegram_config
    
    async def send_update_notification(
        self,
        url: str,
        new_urls: List[str],
        dated_file: Optional[Path],
        target: Optional[str] = None
    ) -> None:
        """发送Sitemap更新通知到Telegram"""
        from telegram import Bot
        import asyncio
        
        chat_id = target or self.config["target_chat"]
        if not chat_id:
            logging.error("未配置发送目标，请检查TELEGRAM_TARGET_CHAT环境变量")
            return
        
        domain = urlparse(url).netloc
        
        try:
            if dated_file and dated_file.exists():
                # 根据是否有新增URL，分别构造美化后的标题
                if new_urls:
                    header_message = (
                        f"✨ {domain} ✨\n"
                        f"------------------------------------\n"
                        f"发现新增内容！ (共 {len(new_urls)} 条)\n"
                        f"来源: {url}\n"
                    )
                else:
                    header_message = (
                        f"✅ {domain}\n"
                        f"------------------------------------\n"
                        f"{domain} 今日sitemap无更新\n"
                        f"来源: {url}\n"
                        f"------------------------------------"
                    )
                await self.bot.send_document(
                    chat_id=chat_id,
                    document=dated_file,
                    caption=header_message,
                )
                logging.info(f"已发送sitemap文件: {dated_file} for {url}")
                try:
                    dated_file.unlink()  # 发送成功后删除
                    logging.info(f"已删除临时sitemap文件: {dated_file}")
                except OSError as e:
                    logging.error(f"删除文件失败: {dated_file}, Error: {str(e)}")
            else:
                # 没有文件时，发送美化标题文本
                if not new_urls:
                    message = f"✅ {domain} 今日没有更新"
                    await self.bot.send_message(
                        chat_id=chat_id, text=message, disable_web_page_preview=True
                    )
                else:
                    header_message = (
                        f"✨ {domain} ✨\n"
                        f"------------------------------------\n"
                        f"发现新增内容！ (共 {len(new_urls)} 条)\n"
                        f"来源: {url}\n"
                    )
                    await self.bot.send_message(
                        chat_id=chat_id, text=header_message, disable_web_page_preview=True
                    )
            
            await asyncio.sleep(1)
            if new_urls:
                logging.info(f"开始发送 {len(new_urls)} 个新URL for {domain}")
                for u in new_urls:
                    await self.bot.send_message(
                        chat_id=chat_id, text=u, disable_web_page_preview=False
                    )
                    logging.info(f"已发送URL: {u}")
                    await asyncio.sleep(1)
                logging.info(f"已发送 {len(new_urls)} 个新URL for {domain}")
                
                # 发送更新结束的消息
                await asyncio.sleep(1)
                end_message = (
                    f"✨ {domain} 更新推送完成 ✨\n------------------------------------"
                )
                await self.bot.send_message(
                    chat_id=chat_id, text=end_message, disable_web_page_preview=True
                )
                logging.info(f"已发送更新结束消息 for {domain}")
        except Exception as e:
            logging.error(f"发送URL更新消息失败 for {url}: {str(e)}", exc_info=True)
    
    async def send_message(self, message: str, target: Optional[str] = None) -> None:
        """发送普通消息到Telegram"""
        chat_id = target or self.config["target_chat"]
        if not chat_id:
            logging.error("未配置发送目标，请检查TELEGRAM_TARGET_CHAT环境变量")
            return
        
        try:
            await self.bot.send_message(
                chat_id=chat_id, text=message, disable_web_page_preview=True
            )
        except Exception as e:
            logging.error(f"发送Telegram消息失败: {str(e)}", exc_info=True)


class EmailNotifier(NotificationService):
    """Email通知服务"""
    
    def __init__(self):
        from core.config import email_config
        self.config = email_config
    
    async def send_update_notification(
        self,
        url: str,
        new_urls: List[str],
        dated_file: Optional[Path],
        target: Optional[str] = None
    ) -> None:
        """发送Sitemap更新通知邮件"""
        from apps.email_bot import send_update_notification as email_send_notification
        
        email_to = target or self.config["to_email"]
        if not email_to:
            logging.error("未配置邮件接收地址，请检查EMAIL_TO环境变量")
            return
        
        await email_send_notification(url, new_urls, dated_file, email_to)
    
    async def send_message(self, message: str, target: Optional[str] = None) -> None:
        """发送普通邮件"""
        from apps.email_bot import send_email
        
        email_to = target or self.config["to_email"]
        if not email_to:
            logging.error("未配置邮件接收地址，请检查EMAIL_TO环境变量")
            return
        
        # 将纯文本消息转换为HTML格式
        html_message = f"""
        <html>
        <body>
            <pre>{message}</pre>
            <hr>
            <p><em>自动发送 by Email Bot</em></p>
        </body>
        </html>
        """
        
        await send_email("RSS通知", html_message)


class NotificationManager:
    """通知管理器"""
    
    def __init__(self):
        self.notifiers: Dict[str, NotificationService] = {}
    
    def register_notifier(self, name: str, notifier: NotificationService):
        """注册通知服务"""
        self.notifiers[name] = notifier
        logging.info(f"已注册通知服务: {name}")
    
    def get_notifier(self, name: str) -> Optional[NotificationService]:
        """获取通知服务"""
        return self.notifiers.get(name)
    
    async def send_to_all(
        self,
        method: str,
        *args,
        **kwargs
    ) -> None:
        """向所有注册的通知服务发送消息"""
        for name, notifier in self.notifiers.items():
            try:
                if hasattr(notifier, method):
                    await getattr(notifier, method)(*args, **kwargs)
                    logging.info(f"已通过 {name} 发送通知")
            except Exception as e:
                logging.error(f"通过 {name} 发送通知失败: {str(e)}", exc_info=True)


# 全局通知管理器实例
notification_manager = NotificationManager()