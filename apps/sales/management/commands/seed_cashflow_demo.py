from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.customers.models import CustomerCompany
from apps.organizations.models import Membership, Organization
from apps.sales.models import Payment, PaymentPlan, Quotation, SalesOrder
from apps.sales.services import sync_order_paid_amount

DEMO_ROWS = (
    ("USD", Decimal("4800"), Decimal("7200"), Decimal("12500")),
    ("EUR", Decimal("3100"), Decimal("5600"), Decimal("9400")),
    ("RUB", Decimal("240000"), Decimal("380000"), Decimal("620000")),
    ("UZS", Decimal("42000000"), Decimal("68000000"), Decimal("115000000")),
)


class Command(BaseCommand):
    help = "Dashboard uchun valyutalar kesimidagi test pul oqimi rejasini yaratadi."

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
            name="TEST — Pul oqimi prognozi",
            defaults={"notes": "Dashboard test hisoboti uchun demo mijoz."},
        )
        today = timezone.localdate()

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

        self.stdout.write(
            self.style.SUCCESS(
                f"{organization.name} uchun 4 valyutada test pul oqimi yaratildi."
            )
        )
