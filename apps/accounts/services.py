import imaplib
import smtplib
import ssl

from django.utils import timezone

from .models import MailboxAccount


class MailboxConnectionError(Exception):
    pass


def _test_smtp(account, password):
    context = ssl.create_default_context()
    if account.smtp_security == MailboxAccount.Security.SSL:
        server = smtplib.SMTP_SSL(
            account.smtp_host,
            account.smtp_port,
            timeout=15,
            context=context,
        )
    else:
        server = smtplib.SMTP(account.smtp_host, account.smtp_port, timeout=15)
    try:
        server.ehlo()
        if account.smtp_security == MailboxAccount.Security.STARTTLS:
            server.starttls(context=context)
            server.ehlo()
        server.login(account.username, password)
    finally:
        try:
            server.quit()
        except smtplib.SMTPException:
            server.close()


def _test_imap(account, password):
    context = ssl.create_default_context()
    if account.imap_security == MailboxAccount.Security.SSL:
        server = imaplib.IMAP4_SSL(
            account.imap_host,
            account.imap_port,
            ssl_context=context,
            timeout=15,
        )
    else:
        server = imaplib.IMAP4(
            account.imap_host,
            account.imap_port,
            timeout=15,
        )
    try:
        if account.imap_security == MailboxAccount.Security.STARTTLS:
            server.starttls(ssl_context=context)
        server.login(account.username, password)
    finally:
        try:
            server.logout()
        except (imaplib.IMAP4.error, OSError):
            server.shutdown()


def test_mailbox_connection(account):
    password = account.get_password()
    errors = []
    try:
        _test_smtp(account, password)
    except Exception as error:
        account.smtp_is_verified = False
        errors.append(f"SMTP: {str(error)[:450] or 'ulanishda xatolik'}")
    else:
        account.smtp_is_verified = True
    try:
        _test_imap(account, password)
    except Exception as error:
        account.imap_is_verified = False
        errors.append(f"IMAP: {str(error)[:450] or 'ulanishda xatolik'}")
    else:
        account.imap_is_verified = True
    account.last_tested_at = timezone.now()
    account.last_error = "\n".join(errors)
    account.save(
        update_fields=[
            "last_tested_at",
            "last_error",
            "smtp_is_verified",
            "imap_is_verified",
            "updated_at",
        ]
    )
    if errors:
        raise MailboxConnectionError(
            "Email ulanishining bir qismi ishlamadi. Holat tafsilotlarini tekshiring."
        )
