import calendar
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Product
from apps.customers.models import CustomerCompany
from apps.organizations.models import Membership, Organization
from apps.sales.models import (
    Payment,
    PaymentPlan,
    Quotation,
    QuotationLine,
    SalesOrder,
)
from apps.sales.services import sync_order_paid_amount

DEMO_ROWS = (
    ("USD", Decimal("4800"), Decimal("7200"), Decimal("12500")),
    ("EUR", Decimal("3100"), Decimal("5600"), Decimal("9400")),
    ("RUB", Decimal("240000"), Decimal("380000"), Decimal("620000")),
    ("UZS", Decimal("42000000"), Decimal("68000000"), Decimal("115000000")),
)

ANALYTICS_BASES = {
    "USD": Decimal("28500"),
    "EUR": Decimal("21400"),
    "RUB": Decimal("1850000"),
    "UZS": Decimal("318000000"),
}

TREND_FACTORS = (
    Decimal("0.72"),
    Decimal("0.78"),
    Decimal("0.75"),
    Decimal("0.84"),
    Decimal("0.88"),
    Decimal("0.93"),
    Decimal("0.90"),
    Decimal("1.02"),
    Decimal("1.08"),
    Decimal("1.12"),
    Decimal("1.18"),
    Decimal("1.25"),
)

ORDER_WEIGHTS = (Decimal("0.28"), Decimal("0.34"), Decimal("0.38"))


def shift_month(value, offset):
    month_index = value.year * 12 + value.month - 1 + offset
    return value.replace(
        year=month_index // 12,
        month=month_index % 12 + 1,
        day=1,
    )


class Command(BaseCommand):
    help = "Dashboard uchun 12 oylik savdo, tushum va pul oqimi demo ma'lumotlarini yaratadi."

    def add_arguments(self, parser):
        parser.add_argument("--organization", help="Tashkilot slug'i")

    @transaction.atomic
    def handle(self, *args, **options):
        organizations = Organization.objects.all()
        if options["organization"]:
            organizations = organizations.filter(slug=options["organization"])
        organization = organizations.first()
        if not organization:
            raise CommandError("Tashkilot topilmadi.")

        actor = (
            Membership.objects.filter(organization=organization, is_active=True)
            .select_related("user")
            .values_list("user", flat=True)
            .first()
        )
        customer, _created = CustomerCompany.objects.get_or_create(
            organization=organization,
            name="TEST — Dashboard analitikasi",
            defaults={"notes": "Dashboard va pul oqimi hisoboti uchun demo mijoz."},
        )
        today = timezone.localdate()

        products = {}
        for currency in ANALYTICS_BASES:
            product, _created = Product.objects.update_or_create(
                organization=organization,
                article=f"DEMO-ANALYTICS-{currency}",
                defaults={
                    "name": f"Demo mahsulot ({currency})",
                    "description": "Dashboard analitikasi uchun xizmat mahsuloti.",
                    "category": Product.Category.OTHER,
                    "unit": Product.Unit.PIECE,
                    "availability": Product.Availability.MADE_TO_ORDER,
                    "list_price": ANALYTICS_BASES[currency],
                    "price_currency": currency,
                    "is_active": True,
                },
            )
            products[currency] = product

        self._seed_analytics_history(
            organization=organization,
            customer=customer,
            products=products,
            actor=actor,
            today=today,
        )
        self._seed_cash_forecast(
            organization=organization,
            customer=customer,
            products=products,
            actor=actor,
            today=today,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"{organization.name} uchun 12 oylik demo savdo, tushum va pul oqimi yaratildi."
            )
        )

    def _seed_analytics_history(self, *, organization, customer, products, actor, today):
        current_start = today.replace(day=1)
        month_starts = [shift_month(current_start, offset) for offset in range(-11, 1)]

        for currency, base_amount in ANALYTICS_BASES.items():
            for month_index, month_start in enumerate(month_starts):
                last_day = calendar.monthrange(month_start.year, month_start.month)[1]
                visible_last_day = today.day if month_start == current_start else last_day
                order_days = sorted({1, min(5, visible_last_day), visible_last_day})
                monthly_total = base_amount * TREND_FACTORS[month_index]

                for slot, (day, weight) in enumerate(zip(order_days, ORDER_WEIGHTS), start=1):
                    order_date = month_start.replace(day=day)
                    line_total = (monthly_total * weight).quantize(Decimal("0.01"))
                    code = f"{month_start:%Y%m}-{slot}"
                    quotation, _created = Quotation.objects.update_or_create(
                        organization=organization,
                        number=f"DEMO-ANALYTICS-{currency}-{code}",
                        defaults={
                            "customer": customer,
                            "status": Quotation.Status.ACCEPTED,
                            "currency": currency,
                            "created_by_id": actor,
                            "notes": "[DEMO ANALYTICS] 12 oylik savdo trendi.",
                        },
                    )
                    QuotationLine.objects.update_or_create(
                        organization=organization,
                        quotation=quotation,
                        product=products[currency],
                        defaults={
                            "description": "Demo savdo",
                            "quantity": Decimal("1"),
                            "unit_price": line_total,
                            "price_source": QuotationLine.PriceSource.MANUAL,
                        },
                    )
                    order, _created = SalesOrder.objects.update_or_create(
                        organization=organization,
                        number=f"DEMO-ANALYTICS-{currency}-{code}",
                        defaults={
                            "customer": customer,
                            "quotation": quotation,
                            "status": SalesOrder.Status.CONFIRMED,
                            "order_date": order_date,
                            "created_by_id": actor,
                            "notes": "[DEMO ANALYTICS] 12 oylik savdo trendi.",
                        },
                    )
                    receipt_date = min(order_date + timedelta(days=2), today)
                    receipt_amount = (line_total * Decimal("0.78")).quantize(
                        Decimal("0.01")
                    )
                    Payment.objects.update_or_create(
                        organization=organization,
                        order=order,
                        reference=f"DEMO-ANALYTICS-{currency}-{code}",
                        defaults={
                            "received_on": receipt_date,
                            "amount": receipt_amount,
                            "method": Payment.Method.BANK,
                            "notes": "[DEMO ANALYTICS] Savdo bo'yicha tushum.",
                            "created_by_id": actor,
                            "is_cancelled": False,
                            "cancelled_at": None,
                            "cancelled_by": None,
                            "cancellation_reason": "",
                        },
                    )
                    sync_order_paid_amount(order)

    def _seed_cash_forecast(self, *, organization, customer, products, actor, today):
        for currency, overdue, next_7_days, next_30_days in DEMO_ROWS:
            quotation, _created = Quotation.objects.update_or_create(
                organization=organization,
                number=f"DEMO-CASHFLOW-{currency}",
                defaults={
                    "customer": customer,
                    "status": Quotation.Status.ACCEPTED,
                    "currency": currency,
                    "created_by_id": actor,
                    "notes": "Dashboard pul oqimi prognozi uchun test taklif.",
                },
            )
            QuotationLine.objects.update_or_create(
                organization=organization,
                quotation=quotation,
                product=products[currency],
                defaults={
                    "description": "Demo pul oqimi buyurtmasi",
                    "quantity": Decimal("1"),
                    "unit_price": overdue + next_7_days + next_30_days,
                    "price_source": QuotationLine.PriceSource.MANUAL,
                },
            )
            order, _created = SalesOrder.objects.update_or_create(
                organization=organization,
                number=f"DEMO-CASHFLOW-{currency}",
                defaults={
                    "customer": customer,
                    "quotation": quotation,
                    "status": SalesOrder.Status.CONFIRMED,
                    "order_date": today,
                    "created_by_id": actor,
                    "notes": "Dashboard pul oqimi prognozi uchun test buyurtma.",
                },
            )
            plan_rows = (
                ("OVERDUE", today - timedelta(days=5), overdue),
                ("NEXT-7", today + timedelta(days=5), next_7_days),
                ("NEXT-30", today + timedelta(days=20), next_30_days),
            )
            plans = {}
            for code, due_date, amount in plan_rows:
                plan, _created = PaymentPlan.objects.update_or_create(
                    organization=organization,
                    order=order,
                    notes=f"[DEMO CASHFLOW] {code}",
                    defaults={
                        "due_date": due_date,
                        "amount": amount,
                        "is_cancelled": False,
                        "cancelled_at": None,
                        "cancelled_by": None,
                        "cancellation_reason": "",
                    },
                )
                plans[code] = plan

            Payment.objects.update_or_create(
                organization=organization,
                order=order,
                reference=f"DEMO-PARTIAL-{currency}",
                defaults={
                    "plan": plans["NEXT-7"],
                    "received_on": today,
                    "amount": next_7_days / Decimal("4"),
                    "method": Payment.Method.BANK,
                    "notes": "[DEMO CASHFLOW] Qisman tushum",
                    "created_by_id": actor,
                    "is_cancelled": False,
                    "cancelled_at": None,
                    "cancelled_by": None,
                    "cancellation_reason": "",
                },
            )
            sync_order_paid_amount(order)
