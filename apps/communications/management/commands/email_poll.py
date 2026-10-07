import time

from django.core.management.base import BaseCommand

from apps.accounts.models import MailboxAccount
from apps.communications.mailbox import EmailSyncError, sync_mailbox


class Command(BaseCommand):
    help = "Faol mailboxlardan yangi email xabarlarini CRM'ga sinxronlaydi."

    def add_arguments(self, parser):
        parser.add_argument(
            "--once",
            action="store_true",
            help="Bitta sinxronlash siklidan keyin to'xtaydi.",
        )
        parser.add_argument("--interval", type=int, default=60)
        parser.add_argument("--days", type=int, default=30)
        parser.add_argument("--limit", type=int, default=200)

    def handle(self, *args, **options):
        interval = max(15, options["interval"])
        days = max(1, options["days"])
        limit = max(1, min(options["limit"], 1000))
        self.stdout.write("Email polling boshlandi. To'xtatish: Ctrl+C")
        while True:
            accounts = MailboxAccount.objects.filter(is_active=True).select_related(
                "organization",
                "user",
            )
            for account in accounts:
                try:
                    result = sync_mailbox(account, days=days, limit=limit)
                except EmailSyncError as exc:
                    self.stderr.write(self.style.ERROR(f"{account.email}: {exc}"))
                    continue
                if result["found"] or result["errors"]:
                    self.stdout.write(
                        f"{account.email}: topildi={result['found']}, "
                        f"import={result['imported']}, xato={result['errors']}"
                    )
            if options["once"]:
                return
            try:
                time.sleep(interval)
            except KeyboardInterrupt:
                self.stdout.write("\nEmail polling to'xtatildi.")
                return
