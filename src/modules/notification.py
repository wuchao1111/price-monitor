"""
Notification Module - send notifications through multiple channels
Supports: Terminal, WeCom (企业微信), DingTalk
"""
import json
import requests
from typing import List, Optional
from abc import ABC, abstractmethod
from logging import getLogger
from src.models.schemas import PriceCompareResult, NotificationRequest

logger = getLogger(__name__)


class BaseNotificationChannel(ABC):
    """Base interface for notification channels"""

    @abstractmethod
    def send(self, request: NotificationRequest) -> bool:
        """Send notification, return True if success"""
        pass

    @property
    @abstractmethod
    def enabled(self) -> bool:
        """Whether this channel is enabled"""
        pass


class TerminalNotification(BaseNotificationChannel):
    """Terminal notification (for development and CLI)"""

    def __init__(self, enabled: bool = True):
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    def send(self, request: NotificationRequest) -> bool:
        print("\n" + "=" * 60)
        print("🚨 PRICE ALERT: New lowest price found!")
        print("=" * 60)
        print(f"Product: {request.product_name} (ID: {request.product_id})")
        if request.old_price:
            print(f"Old lowest price: {request.old_price:.2f}")
        print(f"New lowest price: {request.new_price:.2f}")
        print(f"Source: {request.source}")
        print(f"\nTo confirm update, run: {request.confirm_command}")
        print("=" * 60 + "\n")
        return True


class WeComNotification(BaseNotificationChannel):
    """企业微信 Webhook notification"""

    def __init__(self, webhook_url: str, enabled: bool = True):
        self.webhook_url = webhook_url
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        return self._enabled and bool(self.webhook_url)

    def send(self, request: NotificationRequest) -> bool:
        if not self.enabled:
            return False

        old_price_str = f"{request.old_price:.2f}" if request.old_price else "None"
        content = (
            f"🚨 价格降价提醒\n\n"
            f"**商品**: {request.product_name}\n"
            f"**商品ID**: {request.product_id}\n"
            f"**原价**: {old_price_str}\n"
            f"**新低**: {request.new_price:.2f}\n"
            f"**来源**: {request.source}\n\n"
            f"确认更新请执行: `{request.confirm_command}`"
        )

        data = {
            "msgtype": "markdown",
            "markdown": {
                "content": content
            }
        }

        try:
            response = requests.post(self.webhook_url, json=data, timeout=10)
            result = response.json()
            if result.get('errcode') == 0:
                logger.info("WeCom notification sent successfully")
                return True
            else:
                logger.error(f"WeCom notification failed: {result}")
                return False
        except Exception as e:
            logger.error(f"Failed to send WeCom notification: {e}")
            return False


class DingTalkNotification(BaseNotificationChannel):
    """钉钉 Webhook notification"""

    def __init__(self, webhook_url: str, enabled: bool = False):
        self.webhook_url = webhook_url
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        return self._enabled and bool(self.webhook_url)

    def send(self, request: NotificationRequest) -> bool:
        if not self.enabled:
            return False

        old_price_str = f"{request.old_price:.2f}" if request.old_price else "None"
        text = (
            "🚨 价格降价提醒\n"
            f"商品: {request.product_name}\n"
            f"商品ID: {request.product_id}\n"
            f"原价: {old_price_str}\n"
            f"新低: {request.new_price:.2f}\n"
            f"来源: {request.source}\n\n"
            f"确认更新请执行: {request.confirm_command}"
        )

        data = {
            "msgtype": "text",
            "text": {
                "content": text
            }
        }

        try:
            response = requests.post(self.webhook_url, json=data, timeout=10)
            result = response.json()
            if result.get('errcode') == 0 or result.get('errorCode') == 0:
                logger.info("DingTalk notification sent successfully")
                return True
            else:
                logger.error(f"DingTalk notification failed: {result}")
                return False
        except Exception as e:
            logger.error(f"Failed to send DingTalk notification: {e}")
            return False


class NotificationManager:
    """Notification manager that manages multiple channels"""

    def __init__(self):
        self._channels: List[BaseNotificationChannel] = []

    def add_channel(self, channel: BaseNotificationChannel) -> None:
        """Add a notification channel"""
        if channel.enabled:
            self._channels.append(channel)
            logger.info(f"Added notification channel: {channel.__class__.__name__}")

    def send_new_low_alert(
        self,
        compare_result: PriceCompareResult,
        cli_path: str = "python main.py cli"
    ) -> bool:
        """
        Send notification when new lowest price found

        Args:
            compare_result: Price comparison result
            cli_path: CLI path for the confirm command

        Returns:
            True if at least one channel sent successfully
        """
        request = NotificationRequest(
            product_id=compare_result.product_id,
            product_name=compare_result.product_name,
            old_price=compare_result.current_lowest,
            new_price=compare_result.latest_price,
            source=compare_result.source,
            confirm_command=f"{cli_path} confirm {compare_result.product_id} {compare_result.latest_price}"
        )

        success_count = 0
        for channel in self._channels:
            if channel.enabled:
                if channel.send(request):
                    success_count += 1

        return success_count > 0
