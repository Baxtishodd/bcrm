from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.shortcuts import render
from django.utils import timezone

from apps.crm.models import Activity, Lead
from apps.customers.models import CustomerCompany
from apps.organizations.models import Membership
from apps.sales.models import Payment, PaymentPlan, Quotation, SalesOrder

from .forms import SalesReportFilterForm
from .permissions import OrganizationPermission, organization_permission_required
from .tenancy import organization_required


def build_cash_forecast(payment_plans, today):
    forecast_totals = defaultdict(
        lambda: {
            "overdue": Decimal("0"),
            "next_7_days": Decimal("0"),
            "next_30_days": Decimal("0"),
        }
    )
    for plan in payment_plans:
        balance = plan.balance
        if balance <= 0:
            continue
        currency = plan.order.currency
        if plan.due_date < today:
            forecast_totals[currency]["overdue"] += balance
        elif plan.due_date <= today + timedelta(days=7):
            forecast_totals[currency]["next_7_days"] += balance
            forecast_totals[currency]["next_30_days"] += balance
        elif plan.due_date <= today + timedelta(days=30):
            forecast_totals[currency]["next_30_days"] += balance
    return [
        {"currency": currency, **totals}
        for currency, totals in sorted(forecast_totals.items())
    ]


@login_required
def dashboard(request):
    membership = (
        Membership.objects.select_related("organization")
        .filter(user=request.user, is_active=True)
        .first()
    )
    organization = membership.organization if membership else None
    request.membership = membership
    leads = Lead.objects.none()
    customers = CustomerCompany.objects.none()
    tasks = Activity.objects.none()
    quotations = Quotation.objects.none()
    orders = SalesOrder.objects.none()
    payment_plans = PaymentPlan.objects.none()

    if organization:
        leads = Lead.objects.filter(organization=organization).select_related(
            "assigned_to",
            "customer",
        )
        customers = CustomerCompany.objects.filter(organization=organization)
        tasks = Activity.objects.filter(organization=organization).select_related(
            "lead",
            "assigned_to",
        )
        quotations = Quotation.objects.filter(organization=organization).prefetch_related(
            "lines"
        )
        orders = SalesOrder.objects.filter(organization=organization).select_related(
            "quotation",
            "organization",
        ).prefetch_related("lines", "quotation__lines")
        payment_plans = PaymentPlan.objects.filter(
            organization=organization,
            is_cancelled=False,
            due_date__lte=timezone.localdate() + timedelta(days=30),
        ).select_related("order__quotation", "order__organization").prefetch_related(
            "payments"
        )

    now = timezone.now()
    open_leads = leads.exclude(status__in=[Lead.Status.WON, Lead.Status.LOST])
    open_tasks = tasks.filter(completed_at__isnull=True)
    pipeline_by_currency = list(
        open_leads.values("currency")
        .annotate(total=Sum("estimated_value"))
        .order_by("currency")
    )
    order_totals = defaultdict(lambda: Decimal("0"))
    for order in orders:
        total = order.total
        if total:
            order_totals[order.currency] += total
    orders_by_currency = [
        {"currency": currency, "total": total}
        for currency, total in sorted(order_totals.items())
    ]
    active_payment_plans = list(payment_plans)
    overdue_payment_plans = [
        plan
        for plan in active_payment_plans
        if plan.due_date < timezone.localdate() and plan.balance > 0
    ]
    cash_forecast = build_cash_forecast(active_payment_plans, timezone.localdate())

    return render(
        request,
        "dashboard/home.html",
        {
            "organization": organization,
            "lead_count": leads.count(),
            "won_count": leads.filter(status=Lead.Status.WON).count(),
            "customer_count": customers.count(),
            "open_lead_count": open_leads.count(),
            "pipeline_by_currency": pipeline_by_currency,
            "quotation_count": quotations.count(),
            "order_count": orders.count(),
            "orders_by_currency": orders_by_currency,
            "overdue_task_count": open_tasks.filter(due_at__lt=now).count(),
            "overdue_payment_count": len(overdue_payment_plans),
            "cash_forecast": cash_forecast,
            "upcoming_tasks": open_tasks.order_by("due_at", "created_at")[:6],
            "recent_leads": leads.order_by("-created_at")[:8],
        },
    )


@login_required
@organization_required
@organization_permission_required(OrganizationPermission.MANAGE_ORGANIZATION)
def sales_report(request):
    organization = request.organization
    form = SalesReportFilterForm(request.GET or None, organization=organization)
    leads = Lead.objects.filter(organization=organization).select_related("assigned_to")
    date_from = None
    date_to = None

    if form.is_valid():
        date_from = form.cleaned_data.get("date_from")
        date_to = form.cleaned_data.get("date_to")
        assigned_to = form.cleaned_data.get("assigned_to")
        business_direction = form.cleaned_data.get("business_direction")
        if date_from:
            leads = leads.filter(created_at__date__gte=date_from)
        if date_to:
            leads = leads.filter(created_at__date__lte=date_to)
        if assigned_to:
            leads = leads.filter(assigned_to=assigned_to)
        if business_direction:
            leads = leads.filter(business_direction=business_direction)

    status_counts = {
        row["status"]: row["count"]
        for row in leads.values("status").annotate(count=Count("id"))
    }
    total_count = sum(status_counts.values())
    won_count = status_counts.get(Lead.Status.WON, 0)
    lost_count = status_counts.get(Lead.Status.LOST, 0)
    closed_count = won_count + lost_count
    conversion_rate = round(won_count * 100 / closed_count, 1) if closed_count else 0

    funnel_rows = []
    for value, label in Lead.Status.choices:
        count = status_counts.get(value, 0)
        funnel_rows.append(
            {
                "value": value,
                "label": label,
                "count": count,
                "percent": round(count * 100 / total_count, 1) if total_count else 0,
            }
        )

    open_statuses = [Lead.Status.NEW, Lead.Status.IN_PROGRESS]
    pipeline_by_currency = list(
        leads.filter(status__in=open_statuses)
        .values("currency")
        .annotate(total=Sum("estimated_value"), count=Count("id"))
        .order_by("currency")
    )
    won_by_currency = list(
        leads.filter(status=Lead.Status.WON)
        .values("currency")
        .annotate(total=Sum("estimated_value"), count=Count("id"))
        .order_by("currency")
    )

    manager_rows = list(
        leads.values(
            "assigned_to_id",
            "assigned_to__first_name",
            "assigned_to__last_name",
            "assigned_to__email",
        )
        .annotate(
            total=Count("id"),
            won=Count("id", filter=Q(status=Lead.Status.WON)),
            lost=Count("id", filter=Q(status=Lead.Status.LOST)),
            open=Count("id", filter=Q(status__in=open_statuses)),
        )
        .order_by("assigned_to__first_name", "assigned_to__email")
    )
    for row in manager_rows:
        closed = row["won"] + row["lost"]
        row["conversion_rate"] = round(row["won"] * 100 / closed, 1) if closed else 0
        full_name = " ".join(
            filter(
                None,
                [row["assigned_to__first_name"], row["assigned_to__last_name"]],
            )
        )
        row["manager_name"] = full_name or row["assigned_to__email"] or "Biriktirilmagan"

    direction_labels = dict(Lead.BusinessDirection.choices)
    direction_rows = list(
        leads.values("business_direction")
        .annotate(
            total=Count("id"),
            won=Count("id", filter=Q(status=Lead.Status.WON)),
            lost=Count("id", filter=Q(status=Lead.Status.LOST)),
        )
        .order_by("business_direction")
    )
    for row in direction_rows:
        row["label"] = direction_labels.get(row["business_direction"], "Boshqa")

    lost_reasons = list(
        leads.filter(status=Lead.Status.LOST)
        .exclude(lost_reason="")
        .values("lost_reason")
        .annotate(count=Count("id"))
        .order_by("-count", "lost_reason")[:10]
    )
    quotation_count = Quotation.objects.filter(
        organization=organization,
        lead__in=leads,
    ).count()
    filtered_orders = SalesOrder.objects.filter(
        organization=organization,
        quotation__lead__in=leads,
    ).select_related("quotation", "organization")
    order_count = filtered_orders.count()

    active_payment_plans = PaymentPlan.objects.filter(
        organization=organization,
        order__in=filtered_orders,
        is_cancelled=False,
    ).select_related("order__quotation", "order__organization").prefetch_related("payments")
    payment_plans = active_payment_plans
    payments = Payment.objects.filter(
        organization=organization,
        order__in=filtered_orders,
        is_cancelled=False,
    ).select_related("order__quotation", "order__organization")
    if date_from:
        payment_plans = payment_plans.filter(due_date__gte=date_from)
        payments = payments.filter(received_on__gte=date_from)
    if date_to:
        payment_plans = payment_plans.filter(due_date__lte=date_to)
        payments = payments.filter(received_on__lte=date_to)

    planned_totals = defaultdict(lambda: Decimal("0"))
    actual_totals = defaultdict(lambda: Decimal("0"))
    for plan in payment_plans:
        planned_totals[plan.order.currency] += plan.amount
    for payment in payments:
        actual_totals[payment.order.currency] += payment.amount
    payment_comparison = [
        {
            "currency": currency,
            "planned": planned_totals[currency],
            "actual": actual_totals[currency],
            "difference": actual_totals[currency] - planned_totals[currency],
        }
        for currency in sorted(planned_totals.keys() | actual_totals.keys())
    ]

    cash_forecast = build_cash_forecast(active_payment_plans, timezone.localdate())

    return render(
        request,
        "reports/sales.html",
        {
            "organization": organization,
            "form": form,
            "total_count": total_count,
            "won_count": won_count,
            "lost_count": lost_count,
            "conversion_rate": conversion_rate,
            "quotation_count": quotation_count,
            "order_count": order_count,
            "payment_comparison": payment_comparison,
            "cash_forecast": cash_forecast,
            "funnel_rows": funnel_rows,
            "pipeline_by_currency": pipeline_by_currency,
            "won_by_currency": won_by_currency,
            "manager_rows": manager_rows,
            "direction_rows": direction_rows,
            "lost_reasons": lost_reasons,
        },
    )
