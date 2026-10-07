from django.db.models import Case, IntegerField, Q, Value, When
from django.utils import timezone

from .models import PriceList, PriceListLine


def find_active_price(*, organization, product, currency, quantity=None, on_date=None):
    """Return the best currently active price-list line for a product."""

    effective_date = on_date or timezone.localdate()
    lines = PriceListLine.objects.select_related("price_list").filter(
        organization=organization,
        product=product,
        unit_price__isnull=False,
        price_list__document_type=PriceList.DocumentType.PRICE_LIST,
        price_list__status=PriceList.Status.ACTIVE,
        price_list__currency=currency,
        price_list__issue_date__lte=effective_date,
    ).filter(
        Q(price_list__valid_until__isnull=True)
        | Q(price_list__valid_until__gte=effective_date),
        Q(price_list__category="") | Q(price_list__category=product.category),
    )
    if quantity is not None:
        lines = lines.filter(
            Q(minimum_order_quantity__isnull=True)
            | Q(minimum_order_quantity__lte=quantity)
        )

    return (
        lines.annotate(
            category_priority=Case(
                When(price_list__category=product.category, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        )
        .order_by(
            "category_priority",
            "-minimum_order_quantity",
            "-price_list__issue_date",
            "-price_list__version",
            "-price_list__created_at",
        )
        .first()
    )
