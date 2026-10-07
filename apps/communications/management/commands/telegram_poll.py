import time

from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError

from apps.communications.models import TelegramUpdate
from apps.communications.telegram import (
    TelegramAPIError,
    TelegramBotClient,
    get_telegram_organization,
    process_telegram_update,
)


class Command(BaseCommand):
    help = "Telegram xabarlarini long polling orqali CRM'ga qabul qiladi."

    def add_arguments(self, parser):
        parser.add_argument(
            "--once",
            action="store_true",
            help="Bitta polling so'rovidan keyin to'xtaydi.",
        )
        parser.add_argument("--timeout", type=int, default=25)

    def handle(self, *args, **options):
        try:
            organization = get_telegram_organization()
            client = TelegramBotClient()
            webhook = client.get_webhook_info()
        except (TelegramAPIError, ImproperlyConfigured) as exc:
            raise CommandError(str(exc)) from exc
        if webhook.get("url"):
            raise CommandError(
                "Telegram webhook faol. Pollingni boshlashdan oldin webhookni o'chiring."
            )

        last_update_id = TelegramUpdate.objects.order_by("-update_id").values_list(
            "update_id", flat=True
        ).first()
        offset = last_update_id + 1 if last_update_id is not None else None
        self.stdout.write(
            self.style.SUCCESS(
                f"Telegram polling boshlandi: {organization.name}. To'xtatish: Ctrl+C"
            )
        )
        while True:
            try:
                updates = client.get_updates(offset=offset, timeout=options["timeout"])
                for update in updates:
                    process_telegram_update(
                        update,
                        organization=organization,
                        client=client,
                    )
                    offset = update["update_id"] + 1
            except TelegramAPIError as exc:
                self.stderr.write(self.style.ERROR(str(exc)))
                if options["once"]:
                    raise CommandError(str(exc)) from exc
                time.sleep(3)
            except KeyboardInterrupt:
                self.stdout.write("\nTelegram polling to'xtatildi.")
                return
            if options["once"]:
                return
