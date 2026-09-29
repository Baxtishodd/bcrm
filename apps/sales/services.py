from django.db import transaction
from django.utils import timezone

from apps.crm.models import Lead, PipelineStage

from .models import OrderLine, OrderLineVariant, Quotation, SalesOrder


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
