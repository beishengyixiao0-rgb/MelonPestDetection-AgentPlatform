"""
邮件服务 - 基于 SMTP 发送验证码邮件
使用 QQ 邮箱 SMTP 服务
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.config.settings import settings

logger = logging.getLogger(__name__)


class EmailService:
    """邮件发送服务"""

    @staticmethod
    def send_verification_code(email: str, code: str) -> bool:
        """
        发送验证码邮件

        Args:
            email: 收件人邮箱
            code: 6位验证码

        Returns:
            bool: 发送是否成功
        """
        if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            logger.error("SMTP 配置未设置，无法发送邮件")
            return False

        msg = MIMEMultipart()
        msg["From"] = settings.SMTP_USER
        msg["To"] = email
        msg["Subject"] = "【农作物病害检测系统】密码重置验证码"

        body = f"""
<html>
<body style="font-family: Arial, sans-serif; padding: 20px;">
    <h2 style="color: #333;">密码重置验证码</h2>
    <p>您好，</p>
    <p>您正在申请重置密码，验证码为：</p>
    <h1 style="color: #1a73e8; letter-spacing: 8px; font-size: 36px; text-align: center; background: #f0f7ff; padding: 20px; border-radius: 8px;">{code}</h1>
    <p>该验证码 <strong>5 分钟内有效</strong>，请勿泄露给他人。</p>
    <p>如非本人操作，请忽略此邮件。</p>
    <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
    <p style="color: #999; font-size: 12px;">此邮件由系统自动发送，请勿回复。</p>
</body>
</html>
"""
        msg.attach(MIMEText(body, "html", "utf-8"))

        try:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)
            logger.info(f"验证码邮件发送成功: {email}")
            return True
        except Exception as e:
            logger.error(f"验证码邮件发送失败: {email}, 错误: {e}")
            return False
