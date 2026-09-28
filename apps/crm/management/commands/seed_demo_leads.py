from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.accounts.models import User
from apps.crm.models import Activity, Lead, PipelineStage
from apps.customers.models import CustomerCompany
from apps.organizations.models import Organization


STAGES = (
    ("new", "Yangi murojaat", 10, 10, "#3b82f6", False),
    ("needs", "Ehtiyojni aniqlash", 20, 25, "#8b5cf6", False),
    ("offer", "Taklif tayyorlash", 30, 50, "#f59e0b", False),
    ("negotiation", "Muzokara", 40, 75, "#14b8a6", False),
    ("won", "Yutildi", 50, 100, "#22c55e", True),
    ("lost", "Yutqazildi", 60, 0, "#ef4444", True),
)


LEADS = (
    {
        "title": "Kulirka suprem uchun oylik 12 tonna talab",
        "direction": Lead.BusinessDirection.KNIT_FABRIC,
        "status": Lead.Status.IN_PROGRESS,
        "stage": "negotiation",
        "priority": Lead.Priority.HIGH,
        "source": "Telegram",
        "value": "42000",
        "customer_index": 0,
        "next_days": 1,
        "activity": (Activity.Type.CALL, "Narx va ranglar bo'yicha qo'ng'iroq"),
        "description": "30/1 kulirka suprem, oq va qora ranglar. Oylik yetkazib berish shartlari muhokamada.",
    },
    {
        "title": "Interlock namunasi va eksport narxi",
        "direction": Lead.BusinessDirection.KNIT_FABRIC,
        "status": Lead.Status.NEW,
        "stage": "needs",
        "priority": Lead.Priority.MEDIUM,
        "source": "Email",
        "value": "18500",
        "customer_index": 1,
        "next_days": 2,
        "activity": (Activity.Type.EMAIL, "Interlock namuna katalogini yuborish"),
        "description": "Mijoz 220-240 GSM interlock uchun namuna va FCA narx so'ragan.",
    },
    {
        "title": "Poplin 243 sm — 75 000 p/m taklif",
        "direction": Lead.BusinessDirection.WEAVING,
        "status": Lead.Status.IN_PROGRESS,
        "stage": "offer",
        "priority": Lead.Priority.HIGH,
        "source": "WhatsApp",
        "value": "60000",
        "customer_index": 0,
        "next_days": 1,
        "activity": (Activity.Type.TASK, "51/TT price-list asosida taklif tayyorlash"),
        "description": "Poplin 243 sm, 110 GSM, 75 000 pogon metr. FCA Koson sharti.",
    },
    {
        "title": "Satin matosi bo'yicha mehmonxona loyihasi",
        "direction": Lead.BusinessDirection.WEAVING,
        "status": Lead.Status.NEW,
        "stage": "new",
        "priority": Lead.Priority.MEDIUM,
        "source": "Ko'rgazma",
        "value": "37500",
        "customer_index": 1,
        "next_days": 3,
        "activity": (Activity.Type.MEETING, "Satin texnik parametrlarini aniqlash"),
        "description": "Satin smooth va satin stripe variantlari, 130-140 GSM.",
    },
    {
        "title": "Ne30/1 combed compact — 21 tonna",
        "direction": Lead.BusinessDirection.YARN,
        "status": Lead.Status.IN_PROGRESS,
        "stage": "offer",
        "priority": Lead.Priority.HIGH,
        "source": "Email",
        "value": "61950",
        "customer_index": 0,
        "next_days": 1,
        "activity": (Activity.Type.EMAIL, "Yuklash sanasi bilan yarn price-list yuborish"),
        "description": "Ne30/1 CCM combed compact ring, 100% cotton, 21 000 kg.",
    },
    {
        "title": "OE Ne20/1 ip uchun sinov buyurtmasi",
        "direction": Lead.BusinessDirection.YARN,
        "status": Lead.Status.WON,
        "stage": "won",
        "priority": Lead.Priority.MEDIUM,
        "source": "Telegram",
        "value": "39000",
        "customer_index": 1,
        "next_days": None,
        "activity": (Activity.Type.NOTE, "Buyurtma kelishildi va savdoga o'tkazildi"),
        "description": "OE Ne20/1, 20 000 kg, 100% oldindan to'lov.",
    },
    {
        "title": "Private label futbolka kolleksiyasi",
        "direction": Lead.BusinessDirection.SEWING,
        "status": Lead.Status.NEW,
        "stage": "needs",
        "priority": Lead.Priority.HIGH,
        "source": "Instagram",
        "value": "25000",
        "customer_index": 0,
        "next_days": 2,
        "activity": (Activity.Type.MEETING, "Model, o'lcham va rang matritsasini kelishish"),
        "description": "5 model, 4 rang va S-XXL o'lchamlar bo'yicha tayyor kiyim buyurtmasi.",
    },
    {
        "title": "Tikuvchilik xizmati — 8 000 dona",
        "direction": Lead.BusinessDirection.SEWING,
        "status": Lead.Status.LOST,
        "stage": "lost",
        "priority": Lead.Priority.LOW,
        "source": "Tavsiya",
        "value": "16000",
        "customer_index": 1,
        "next_days": None,
        "activity": (Activity.Type.NOTE, "Rad etish sababini qayd qilish"),
        "description": "Mijoz talab qilgan ishlab chiqarish muddati bilan kelishilmadi.",
        "lost_reason": "Yetkazish muddati mijoz talabiga mos kelmadi.",
    },
    {
        "title": "Eksport qadoqlash bo'yicha hamkorlik",
        "direction": Lead.BusinessDirection.OTHER,
        "status": Lead.Status.IN_PROGRESS,
        "stage": "needs",
        "priority": Lead.Priority.MEDIUM,
        "source": "Hamkor tavsiyasi",
        "value": "12000",
        "customer_index": None,
        "next_days": 4,
        "activity": (Activity.Type.CALL, "Qadoqlash talablari bo'yicha aloqa qilish"),
        "description": "Eksport partiyalari uchun markirovka va qadoqlash xizmati.",
    },
    {
        "title": "Qayta ishlangan paxta bo'yicha pilot loyiha",
        "direction": Lead.BusinessDirection.OTHER,
        "status": Lead.Status.NEW,
        "stage": "new",
        "priority": Lead.Priority.LOW,
        "source": "Ko'rgazma",
        "value": "9000",
        "customer_index": None,
        "next_days": 5,
        "activity": (Activity.Type.TASK, "Pilot loyiha texnik talablarini yig'ish"),
        "description": "Recycled cotton aralashmasi bo'yicha kichik sinov partiyasi.",
    },
)


class Command(BaseCommand):
    help = "Create idempotent demo pipeline stages, leads and activities."

    def add_arguments(self, parser):
        parser.add_argument("--organization", default="bunyodkor")

    def handle(self, *args, **options):
        try:
            organization = Organization.objects.get(slug=options["organization"])
        except Organization.DoesNotExist as exc:
            raise CommandError("Tashkilot topilmadi.") from exc

        assigned_to = (
            User.objects.filter(
                memberships__organization=organization,
                memberships__is_active=True,
            )
            .distinct()
            .first()
        )
        stages = {}
        for key, name, position, probability, color, is_closed in STAGES:
            stage, _ = PipelineStage.objects.update_or_create(
                organization=organization,
                name=name,
                defaults={
                    "position": position,
                    "probability": probability,
                    "color": color,
                    "is_closed": is_closed,
                },
            )
            stages[key] = stage

        customers = {
            direction: list(
                CustomerCompany.objects.filter(
                    organization=organization,
                    business_direction=direction,
                    is_active=True,
                ).order_by("name")[:2]
            )
            for direction, _ in Lead.BusinessDirection.choices
        }
        now = timezone.now()
        for row in LEADS:
            customer = None
            customer_index = row["customer_index"]
            candidates = customers[row["direction"]]
            if customer_index is not None and len(candidates) > customer_index:
                customer = candidates[customer_index]
            contact = (
                customer.contacts.order_by("-is_primary", "full_name").first()
                if customer
                else None
            )
            next_action = (
                now + timedelta(days=row["next_days"])
                if row["next_days"] is not None
                else None
            )
            lead, _ = Lead.objects.update_or_create(
                organization=organization,
                title=row["title"],
                defaults={
                    "business_direction": row["direction"],
                    "customer": customer,
                    "contact": contact,
                    "stage": stages[row["stage"]],
                    "status": row["status"],
                    "priority": row["priority"],
                    "source": row["source"],
                    "estimated_value": Decimal(row["value"]),
                    "currency": "USD",
                    "assigned_to": assigned_to,
                    "next_action_at": next_action,
                    "lost_reason": row.get("lost_reason", ""),
                    "description": row["description"],
                },
            )
            activity_type, subject = row["activity"]
            is_closed = row["status"] in (Lead.Status.WON, Lead.Status.LOST)
            Activity.objects.update_or_create(
                organization=organization,
                lead=lead,
                subject=subject,
                defaults={
                    "activity_type": activity_type,
                    "details": row["description"],
                    "due_at": next_action,
                    "completed_at": now if is_closed else None,
                    "assigned_to": assigned_to,
                },
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"{len(STAGES)} ta bosqich, {len(LEADS)} ta lead va faoliyatlar tayyorlandi."
            )
        )
