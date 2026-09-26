from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render
from django.utils import timezone

from apps.crm.models import Activity, Lead
from apps.customers.models import CustomerCompany
from apps.organizations.models import Membership
from apps.sales.models import Quotation, SalesOrder


@login_required
def dashboard(request):
    membership = (
        Membership.objects.select_related("organization")
        .filter(user=request.user, is_active=True)
        .first()
    )
    organization = membership.organization if membership else None
    leads = Lead.objects.none()
    customers = CustomerCompany.objects.none()
    tasks = Activity.objects.none()
    quotations = Quotation.objects.none()
    orders = SalesOrder.objects.none()

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
        orders = SalesOrder.objects.filter(organization=organization).prefetch_related("lines")

    now = timezone.now()
    open_leads = leads.exclude(status__in=[Lead.Status.WON, Lead.Status.LOST])
    open_tasks = tasks.filter(completed_at__isnull=True)

    return render(
        request,
        "dashboard/home.html",
        {
            "organization": organization,
            "lead_count": leads.count(),
            "won_count": leads.filter(status=Lead.Status.WON).count(),
            "customer_count": customers.count(),
            "open_lead_count": open_leads.count(),
            "pipeline_value": open_leads.aggregate(total=Sum("estimated_value"))["total"] or 0,
            "quotation_count": quotations.count(),
            "order_count": orders.count(),
            "order_value": sum(order.total for order in orders),
            "overdue_task_count": open_tasks.filter(due_at__lt=now).count(),
            "upcoming_tasks": open_tasks.order_by("due_at", "created_at")[:6],
            "recent_leads": leads.order_by("-created_at")[:8],
        },
    )
