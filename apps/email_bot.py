from core.config import email_config
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import logging
import asyncio
from pathlib import Path
from urllib.parse import urlparse

email_clients = {}


def create_email_client():
    """创建邮件客户端连接"""
    try:
        context = ssl.create_default_context()
        server = smtplib.SMTP(email_config["smtp_server"], email_config["smtp_port"])
        
        if email_config["use_tls"]:
            server.starttls(context=context)
        
        server.login(email_config["username"], email_config["password"])
        return server
    except Exception as e:
        logging.error(f"创建邮件客户端失败: {str(e)}")
        return None


def close_email_client(server):
    """关闭邮件客户端连接"""
    try:
        if server:
            server.quit()
    except Exception as e:
        logging.error(f"关闭邮件客户端失败: {str(e)}")


async def send_email(subject: str, body: str, attachments: list = None):
    """发送邮件"""
    if not email_config["to_email"]:
        logging.error("未配置邮件接收地址，请检查EMAIL_TO环境变量")
        return False
    
    server = create_email_client()
    if not server:
        return False
    
    try:
        msg = MIMEMultipart()
        msg["From"] = email_config["from_email"] or email_config["username"]
        msg["To"] = email_config["to_email"]
        msg["Subject"] = subject
        
        # 添加正文
        msg.attach(MIMEText(body, "html"))
        
        # 添加附件
        if attachments:
            for attachment in attachments:
                if isinstance(attachment, Path) and attachment.exists():
                    with open(attachment, "rb") as f:
                        part = MIMEApplication(f.read(), Name=attachment.name)
                    part["Content-Disposition"] = f"attachment; filename=\"{attachment.name}\""
                    msg.attach(part)
        
        # 发送邮件
        server.send_message(msg)
        logging.info(f"邮件发送成功: {subject}")
        return True
    except Exception as e:
        logging.error(f"发送邮件失败: {str(e)}")
        return False
    finally:
        close_email_client(server)


async def help_command():
    """帮助命令"""
    help_text = """
    <h2>Email Bot Help</h2>
    <p>这是一个基于邮件的sitemap监控机器人。</p>
    <h3>功能：</h3>
    <ul>
        <li>监控sitemap更新</li>
        <li>发送更新通知邮件</li>
        <li>关键词汇总</li>
    </ul>
    <h3>配置：</h3>
    <p>请确保正确配置了以下环境变量：</p>
    <ul>
        <li>EMAIL_SMTP_SERVER: SMTP服务器地址</li>
        <li>EMAIL_SMTP_PORT: SMTP端口（默认587）</li>
        <li>EMAIL_USERNAME: 邮箱用户名</li>
        <li>EMAIL_PASSWORD: 邮箱密码</li>
        <li>EMAIL_FROM: 发件人邮箱（可选，默认使用用户名）</li>
        <li>EMAIL_TO: 收件人邮箱</li>
        <li>EMAIL_USE_TLS: 是否使用TLS（默认true）</li>
    </ul>
    """
    return help_text


async def init_task():
    """初始化任务"""
    logging.info("Initializing Email bot")
    
    # 发送初始化邮件
    help_text = await help_command()
    await send_email("Email Bot Initialized", help_text)


async def start_task():
    """启动任务"""
    logging.info("Email bot startup successful")
    return True


def close_all():
    """关闭所有连接"""
    logging.info("Closing Email bot")
    # 关闭所有邮件客户端连接
    for server in email_clients.values():
        close_email_client(server)
    email_clients.clear()


async def send_update_notification(
    url: str,
    new_urls: list[str],
    dated_file: Path | None,
    target_email: str = None,
) -> None:
    """发送Sitemap更新通知邮件，包括文件（如果可用）和新增URL列表。"""
    email_to = target_email or email_config["to_email"]
    if not email_to:
        logging.error("未配置邮件接收地址，请检查EMAIL_TO环境变量")
        return
    
    domain = urlparse(url).netloc
    
    try:
        # 构建HTML邮件内容
        html_content = f"""
        <html>
        <body>
            <h2>✨ {domain} ✨</h2>
            <hr>
            <p><strong>来源:</strong> {url}</p>
        """
        
        if new_urls:
            html_content += f"""
            <p><strong>发现新增内容！</strong> (共 {len(new_urls)} 条)</p>
            <ul>
            """
            for url_item in new_urls:
                html_content += f'<li><a href="{url_item}">{url_item}</a></li>'
            html_content += "</ul>"
        else:
            html_content += "<p><strong>今日sitemap无更新</strong></p>"
        
        html_content += """
            <hr>
            <p><em>自动发送 by Email Bot</em></p>
        </body>
        </html>
        """
        
        # 准备附件
        attachments = []
        if dated_file and dated_file.exists():
            attachments.append(dated_file)
        
        # 发送邮件
        subject = f"✨ {domain} Sitemap更新通知"
        success = await send_email(subject, html_content, attachments)
        
        if success:
            logging.info(f"已发送更新通知邮件 for {url}")
            # 发送成功后删除临时文件
            if dated_file and dated_file.exists():
                try:
                    dated_file.unlink()
                    logging.info(f"已删除临时sitemap文件: {dated_file}")
                except OSError as e:
                    logging.error(f"删除文件失败: {dated_file}, Error: {str(e)}")
        else:
            logging.error(f"发送更新通知邮件失败 for {url}")
            
    except Exception as e:
        logging.error(f"发送更新通知邮件失败 for {url}: {str(e)}", exc_info=True)


async def send_keywords_summary(
    all_new_urls: list[str],
    target_email: str = None,
) -> None:
    """从URL列表中提取关键词并按域名分组发送汇总邮件"""
    email_to = target_email or email_config["to_email"]
    if not email_to:
        logging.error("未配置邮件接收地址，请检查EMAIL_TO环境变量")
        return
    
    if not all_new_urls:
        return
    
    # 创建域名-关键词映射字典
    domain_keywords = {}
    
    # 从URL中提取域名和关键词
    for url in all_new_urls:
        try:
            # 解析URL获取域名和路径
            parsed_url = urlparse(url)
            domain = parsed_url.netloc
            
            # 提取路径最后部分作为关键词
            path_parts = parsed_url.path.rstrip("/").split("/")
            if path_parts and path_parts[-1]:  # 确保有路径且最后部分不为空
                keyword = path_parts[-1]
                if keyword.strip():
                    # 将关键词添加到对应域名的列表中
                    if domain not in domain_keywords:
                        domain_keywords[domain] = []
                    domain_keywords[domain].append(keyword)
        except Exception as e:
            logging.debug(f"从URL提取关键词失败: {url}, 错误: {str(e)}")
            continue
    
    # 对每个域名的关键词列表去重
    for domain in domain_keywords:
        domain_keywords[domain] = list(set(domain_keywords[domain]))
    
    # 如果有关键词，构建并发送邮件
    if domain_keywords:
        # 构建HTML邮件内容
        html_content = """
        <html>
        <body>
            <h2>🎯 #今日新增 #关键词 #速览 🎯</h2>
            <hr>
        """
        
        # 按域名分组展示关键词
        for domain, keywords in domain_keywords.items():
            if keywords:  # 确保该域名有关键词
                html_content += f"<h3>📌 {domain}:</h3><ul>"
                for i, keyword in enumerate(keywords, 1):
                    html_content += f"<li>{keyword}</li>"
                html_content += "</ul><br>"
        
        html_content += """
            <hr>
            <p><em>自动发送 by Email Bot</em></p>
        </body>
        </html>
        """
        
        # 发送汇总邮件
        subject = "🎯 今日新增关键词汇总"
        success = await send_email(subject, html_content)
        
        if success:
            logging.info("已发送关键词汇总邮件")
        else:
            logging.error("发送关键词汇总邮件失败")


async def scheduled_task():
    """定时任务"""
    await asyncio.sleep(5)
    
    # 修改导入
    from services.rss.commands import rss_manager, notification_manager
    
    while True:
        try:
            feeds = rss_manager.get_feeds()
            logging.info(f"定时任务开始检查订阅源更新，共 {len(feeds)} 个订阅")
            
            # 用于存储所有新增的URL
            all_new_urls = []
            for url in feeds:
                logging.info(f"正在检查订阅源: {url}")
                # add_feed 内部会调用 download_sitemap
                success, error_msg, dated_file, new_urls = rss_manager.add_feed(url)
                
                if success and dated_file.exists():
                    # 使用新的通知系统
                    await notification_manager.send_to_all(
                        "send_update_notification",
                        url=url,
                        new_urls=new_urls,
                        dated_file=dated_file
                    )
                    if new_urls:
                        logging.info(
                            f"订阅源 {url} 更新成功，发现 {len(new_urls)} 个新URL，已发送通知。"
                        )
                    else:
                        logging.info(f"订阅源 {url} 更新成功，无新增URL，已发送通知。")
                elif "今天已经更新过此sitemap" in error_msg:
                    logging.info(f"订阅源 {url} {error_msg}")
                else:
                    logging.warning(f"订阅源 {url} 更新失败: {error_msg}")
                # 将新URL添加到汇总列表中
                all_new_urls.extend(new_urls)
            
            # 调用新封装的函数发送关键词汇总
            await asyncio.sleep(10)  # 等待10秒，确保所有消息都发送完成
            await send_keywords_summary(all_new_urls)
            
            logging.info("所有订阅源检查完成，等待下一次检查")
            await asyncio.sleep(3600)  # 保持1小时检查间隔
        except Exception as e:
            logging.error(f"检查订阅源更新失败: {str(e)}", exc_info=True)
            await asyncio.sleep(60)  # 出错后等待1分钟再试