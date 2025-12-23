"""
Email utility for sending HTML emails with Jinja2 templates.
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Optional
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config.settings import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


def get_template_env() -> Environment:
    """Get Jinja2 environment for email templates"""
    templates_dir = Path(settings.EMAIL_TEMPLATES_DIR)
    
    if not templates_dir.exists():
        templates_dir.mkdir(parents=True, exist_ok=True)
        logger.warning(f"Email templates directory created: {templates_dir}")
    
    return Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html", "xml"]),
        enable_async=False,
    )


def render_email_template(template_name: str, context: Dict[str, any]) -> str:
    """
    Render HTML email from Jinja2 template.
    
    Args:
        template_name: Template filename (e.g., "password_reset.html")
        context: Template context variables
        
    Returns:
        Rendered HTML string
    """
    env = get_template_env()
    
    # Add common context
    default_context = {
        "app_name": settings.APP_NAME,
        "frontend_url": settings.FRONTEND_URL,
        "support_email": settings.EMAIL_FROM
    }
    
    full_context = {**default_context, **context}
    
    try:
        template = env.get_template(template_name)
        return template.render(**full_context)
    except Exception as e:
        logger.error(f"Failed to render email template {template_name}: {e}")
        raise


def send_email(
    to_email: str,
    subject: str,
    template_name: str,
    context: Dict[str, any]
) -> bool:
    """
    Send HTML email using SMTP.
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        template_name: Jinja2 template filename
        context: Template context variables
        
    Returns:
        True if sent successfully, False otherwise
    """
    if not settings.SMTP_HOST or not settings.EMAIL_FROM:
        logger.warning("SMTP not configured, skipping email send")
        return False
    
    try:
        # Render HTML content
        html_content = render_email_template(template_name, context)
        
        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>"
        msg["To"] = to_email
        
        # Attach HTML part
        html_part = MIMEText(html_content, "html")
        msg.attach(html_part)
        
        # Send via SMTP
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            if settings.SMTP_TLS:
                server.starttls()
            
            if settings.SMTP_USER and settings.SMTP_PASS:
                server.login(settings.SMTP_USER, settings.SMTP_PASS)
            
            server.send_message(msg)
        
        logger.info(f"Email sent successfully to {to_email}: {subject}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False


async def send_email_async(
    to_email: str,
    subject: str,
    template_name: str,
    context: Dict[str, any]
) -> bool:
    """
    Async wrapper for send_email.
    Runs email sending in executor to avoid blocking.
    """
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        send_email,
        to_email,
        subject,
        template_name,
        context
    )

