from django.db import transaction
from django.utils import timezone

from .models import OrderLine, Quotation, SalesOrder


def next_document_number(model, organization, prefix):
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
    quotation = (
        Quotation.objects.select_for_update()
        .prefetch_related("lines")
        .get(pk=quotation.pk)
    )
    existing = SalesOrder.objects.filter(quotation=quotation).first()
    if existing:
        return existing, False
    order = SalesOrder.objects.create(
        organization=quotation.organization,
        number=next_document_number(SalesOrder, quotation.organization, "SO"),
        customer=quotation.customer,
        quotation=quotation,
        status=SalesOrder.Status.CONFIRMED,
        order_date=timezone.localdate(),
        assigned_to=quotation.created_by,
        created_by=actor,
        notes=quotation.notes,
    )
    OrderLine.objects.bulk_create(
        [
            OrderLine(
                organization=quotation.organization,
                order=order,
                product=line.product,
                quantity=line.quantity,
                unit_price=line.unit_price,
            )
            for line in quotation.lines.all()
        ]
    )
    quotation.status = Quotation.Status.ACCEPTED
    quotation.save(update_fields=["status", "updated_at"])
    return order, True
