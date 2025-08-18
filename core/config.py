from dotenv import load_dotenv
import os

load_dotenv()

telegram_config = {
    "token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
    "target_chat": os.environ.get("TELEGRAM_TARGET_CHAT"),  # 不设默认值，强制要求配置
}

discord_config = {
    "token": os.environ.get("DISCORD_TOKEN", ""),
}

email_config = {
    "smtp_server": os.environ.get("EMAIL_SMTP_SERVER", ""),
    "smtp_port": int(os.environ.get("EMAIL_SMTP_PORT", "587")),
    "username": os.environ.get("EMAIL_USERNAME", ""),
    "password": os.environ.get("EMAIL_PASSWORD", ""),
    "from_email": os.environ.get("EMAIL_FROM", ""),
    "to_email": os.environ.get("EMAIL_TO", ""),
    "use_tls": os.environ.get("EMAIL_USE_TLS", "true").lower() == "true",
}
