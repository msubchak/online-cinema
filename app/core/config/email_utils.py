import os

from django.conf import Settings
from fastapi import Depends

from app.core.config.settings import BaseAppSettings, TestingSettings
from app.core.notifications.emails import EmailSender
from app.core.notifications.interfaces import EmailSenderInterface


def get_settings() -> BaseAppSettings:
    environment = os.getenv("ENVIRONMENT", "development")
    if environment == "testing":
        return TestingSettings()
    return Settings


def get_accounts_email_notificator(
    settings: BaseAppSettings = Depends(get_settings)
) -> EmailSenderInterface:
    return EmailSender(
        hostname=settings.EMAIL_HOST,
        port=settings.EMAIL_PORT,
        email=settings.EMAIL_HOST_USER,
        password=settings.EMAIL_HOST_PASSWORD,
        use_tls=settings.EMAIL_USE_TLS,
        template_dir=settings.PATH_TO_EMAIL_TEMPLATES_DIR,
        activation_email_template_name=settings.ACTIVATION_EMAIL_TEMPLATE_NAME,
        activation_complete_email_template_name=settings.ACTIVATION_COMPLETE_EMAIL_TEMPLATE_NAME,
        password_email_template_name=settings.PASSWORD_RESET_TEMPLATE_NAME,
        password_complete_email_template_name=settings.PASSWORD_RESET_COMPLETE_TEMPLATE_NAME
    )
