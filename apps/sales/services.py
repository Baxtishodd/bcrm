import smtplib
import socket
from email.utils import formataddr

from django.core.mail import EmailMessage, get_connection
from django.db import transaction
from django.utils import timezone

from apps.crm.models import Activity, Lead, PipelineStage

from .models import (
    OrderLine,
    OrderLineVariant,
    Quotation,
    QuotationDelivery,
    SalesOrder,
)
from .pdf import build_quotation_pdf, quotation_pdf_filename


class QuotationEmailError(Exception):
    pass


def _email_failure_message(error):
    if isinstance(error, smtplib.SMTPAuthenticationError):
        return "Email yuborilmadi. SMTP login yoki parolini tekshiring."
    if isinstance(error, (socket.timeout, TimeoutError)):
        return "Email yuborilmadi. SMTP server belgilangan vaqtda javob bermadi."
    if isinstance(error, (ConnectionError, OSError)):
        return "Email yuborilmadi. SMTP server bilan aloqa o'rnatilmadi."
    return "Email yuborilmadi. SMTP sozlamalarini tekshiring."


def send_quotation_email(
    *,
    quotation,
    actor,
    account,
    recipient,
    subject,
    message,
    follow_up_at,
):
    organization = quotation.organization
    if account.organization_id != organization.id or account.user_id != actor.id:
        raise QuotationEmailError("Email akkaunti joriy foydalanuvchiga tegishli emas.")
    if not account.is_active:
        raise QuotationEmailError("Tanlangan email akkaunti faol emas.")
    sender_name = account.display_name or actor.get_full_name() or organization.document_name
    from_email = formataddr((sender_name, account.email))
    connection = get_connection(
        backend="django.core.mail.backends.smtp.EmailBackend",
        host=account.smtp_host,
        port=account.smtp_port,
        username=account.username,
        password=account.get_password(),
        use_tls=account.smtp_security == account.Security.STARTTLS,
        use_ssl=account.smtp_security == account.Security.SSL,
        timeout=20,
    )
    email = EmailMessage(
        subject=subject,
        body=message,
        from_email=from_email,
        to=[recipient],
        reply_to=[account.email],
        connection=connection,
    )
    filename = quotation_pdf_filename(quotation)
    try:
        email.attach(filename, build_quotation_pdf(quotation), "application/pdf")
        sent_count = email.send(fail_silently=False)
        if sent_count != 1:
            raise QuotationEmailError("Email serveri yuborishni tasdiqlamadi.")
    except Exception as error:
        failure_message = _email_failure_message(error)
        QuotationDelivery.objects.create(
            organization=organization,
            quotation=quotation,
            channel=QuotationDelivery.Channel.EMAIL,
            recipient=recipient,
            sender=account.email,
            subject=subject,
            message=message,
            status=QuotationDelivery.Status.FAILED,
            sent_by=actor,
            notes=failure_message,
        )
        account.last_tested_at = timezone.now()
        account.last_error = failure_message
        account.save(update_fields=["last_tested_at", "last_error", "updated_at"])
        if isinstance(error, QuotationEmailError):
            raise
        raise QuotationEmailError(failure_message) from error

    with transaction.atomic():
        delivery = QuotationDelivery.objects.create(
            organization=organization,
            quotation=quotation,
            channel=QuotationDelivery.Channel.EMAIL,
            recipient=recipient,
            sender=account.email,
            subject=subject,
            message=message,
            status=QuotationDelivery.Status.SENT,
            sent_at=timezone.now(),
            sent_by=actor,
            notes=f"{filename} PDF fayli ilova qilindi.",
        )
        account.last_tested_at = timezone.now()
        account.last_error = ""
        account.save(update_fields=["last_tested_at", "last_error", "updated_at"])
        if quotation.status == Quotation.Status.DRAFT:
            quotation.status = Quotation.Status.SENT
            quotation.save(update_fields=["status", "updated_at"])
        Activity.objects.create(
            organization=organization,
            lead=quotation.lead,
            customer=quotation.customer,
            activity_type=Activity.Type.TASK,
            subject=f"{quotation.number} taklifi bo'yicha bog'lanish",
            details=f"{recipient} manziliga yuborilgan taklif bo'yicha javobni aniqlash.",
            due_at=follow_up_at,
            assigned_to=quotation.assigned_to or actor,
        )
    return delivery


def next_document_number(model, organization, prefix=None):
    if not prefix:
        prefix = (
            organization.order_number_prefix
            if model is SalesOrder
            else organization.quotation_number_prefix
        )
    period = timezone.localdate().strftime("%Y%m")
    base = f"{prefix}-{period}-"
    latest = (
        model.objects.filter(organization=organization, number__startswith=base)
        .order_by("-number")
        .values_list("number", flat=True)
        .first()
    )
    try:
        sequence = int(latest.rsplit("-", 1)[1]) + 1 if latest else 1
    except (ValueError, IndexError):
        sequence = 1
    while model.objects.filter(
        organization=organization,
        number=f"{base}{sequence:04d}",
    ).exists():
        sequence += 1
    return f"{base}{sequence:04d}"


@transaction.atomic
def convert_quotation_to_order(quotation, actor):
    quotation = Quotation.objects.select_for_update().prefetch_related("lines").get(pk=quotation.pk)
    existing = SalesOrder.objects.filter(quotation=quotation).first()
    if existing:
        return existing, False
    order = SalesOrder.objects.create(
        organization=quotation.organization,
        number=next_document_number(SalesOrder, quotation.organization),
        customer=quotation.customer,
        quotation=quotation,
        status=SalesOrder.Status.CONFIRMED,
        order_date=timezone.localdate(),
        assigned_to=quotation.assigned_to or quotation.created_by,
        created_by=actor,
        notes=quotation.notes,
    )
    for line in quotation.lines.select_related("variant"):
        order_line = OrderLine.objects.create(
            organization=quotation.organization,
            order=order,
            product=line.product,
            quantity=line.quantity,
            unit_price=line.unit_price,
        )
        if line.variant_id:
            OrderLineVariant.objects.create(
                organization=quotation.organization,
                order_line=order_line,
                variant=line.variant,
                quantity=int(line.quantity),
            )
    quotation.status = Quotation.Status.ACCEPTED
    quotation.save(update_fields=["status", "updated_at"])
    if quotation.lead_id:
        lead = Lead.objects.select_for_update().get(pk=quotation.lead_id)
        lead.status = Lead.Status.WON
        lead.lost_reason = ""
        lead.stage = (
            PipelineStage.objects.filter(
                organization=quotation.organization,
                is_closed=True,
                probability=100,
            )
            .order_by("position", "name")
            .first()
        )
        lead.full_clean()
        lead.save(update_fields=["status", "stage", "lost_reason", "updated_at"])
    return order, True
