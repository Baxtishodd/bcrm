from urllib.parse import urlparse

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.communications.telegram import TelegramAPIError, TelegramBotClient


class Command(BaseCommand):
    help = "Telegram webhookni o'rnatadi, holatini ko'rsatadi yoki o'chiradi."

    def add_arguments(self, parser):
        action = parser.add_mutually_exclusive_group(required=True)
        action.add_argument("--url", help="CRM'ning tashqi HTTPS bazaviy URL manzili.")
        action.add_argument("--delete", action="store_true", help="Webhookni o'chiradi.")
        action.add_argument("--info", action="store_true", help="Webhook holatini ko'rsatadi.")

    def handle(self, *args, **options):
        try:
            client = TelegramBotClient()
            if options["info"]:
                info = client.get_webhook_info()
                self.stdout.write(f"URL: {info.get('url') or 'o‘rnatilmagan'}")
                self.stdout.write(f"Navbatdagi update: {info.get('pending_update_count', 0)}")
                if info.get("last_error_message"):
                    self.stdout.write(self.style.ERROR(info["last_error_message"]))
                return
            if options["delete"]:
                client.delete_webhook()
                self.stdout.write(self.style.SUCCESS("Telegram webhook o'chirildi."))
                return

            base_url = options["url"].rstrip("/")
            parsed = urlparse(base_url)
            if parsed.scheme != "https" or not parsed.netloc:
                raise CommandError("Webhook uchun haqiqiy HTTPS URL kiriting.")
            if not settings.TELEGRAM_WEBHOOK_SECRET:
                raise CommandError(".env ichida TELEGRAM_WEBHOOK_SECRET kiritilishi shart.")
            webhook_url = f"{base_url}/messages/telegram/webhook/"
            client.set_webhook(webhook_url, settings.TELEGRAM_WEBHOOK_SECRET)
            self.stdout.write(self.style.SUCCESS(f"Webhook o'rnatildi: {webhook_url}"))
        except TelegramAPIError as exc:
            raise CommandError(str(exc)) from exc
