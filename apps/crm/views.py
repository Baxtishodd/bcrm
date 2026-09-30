import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Prefetch, Q
from django.http import HttpResponseBadRequest, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie

from apps.common.permissions import OrganizationPermission, organization_permission_required
from apps.common.tenancy import organization_required
from apps.sales.models import Quotation

from .forms import ActivityForm, LeadForm, TaskForm
from .models import Activity, Lead, PipelineStage
from .timeline import build_communication_timeline


@login_required
@organization_required
@ensure_csrf_cookie
@never_cache
def lead_list(request):
    query = request.GET.get("q", "").strip()
    direction = request.GET.get("direction", "")
    leads = (
        Lead.objects.filter(
            organization=request.organization,
        )
        .select_related("customer", "stage", "assigned_to")
        .order_by(
            "kanban_position",
            "-created_at",
        )
    )
    if query:
        leads = leads.filter(
            Q(title__icontains=query)
            | Q(customer__name__icontains=query)
            | Q(source__icontains=query)
        )
    if direction:
        leads = leads.filter(business_direction=direction)
    columns = [(value, label, leads.filter(status=value)) for value, label in Lead.Status.choices]
    return render(
        request,
        "crm/list.html",
        {
            "columns": columns,
            "query": query,
            "direction": direction,
            "direction_choices": Lead.BusinessDirection.choices,
            "organization": request.organization,
        },
    )


@login_required
@organization_required
@organization_permission_required(OrganizationPermission.MANAGE_LEADS)
def lead_create(request):
    form = LeadForm(
        request.POST or None,
        organization=request.organization,
    )
    if form.is_valid():
        lead = form.save(commit=False)
        lead.organization = request.organization
        lead.save()
        messages.success(request, "Lead yaratildi.")
        return redirect("crm:detail", public_id=lead.public_id)
    return render(
        request,
        "shared/form.html",
        {
            "form": form,
            "page_title": "Yangi lead",
            "cancel_url": "/leads/",
            "organization": request.organization,
        },
    )


@login_required
@organization_required
def lead_detail(request, public_id):
    lead = get_object_or_404(
        Lead.objects.select_related(
            "customer",
            "contact",
            "stage",
            "assigned_to",
        ).prefetch_related(
            "activities",
            Prefetch(
                "quotations",
                queryset=Quotation.objects.select_related("salesorder").prefetch_related(
                    "lines",
                    "deliveries__sent_by",
                ),
            ),
        ),
        public_id=public_id,
        organization=request.organization,
    )
    quotations = list(lead.quotations.all())
    deliveries = [
        delivery
        for quotation in quotations
        for delivery in quotation.deliveries.all()
    ]
    linked_order = next(
        (quotation.salesorder for quotation in quotations if hasattr(quotation, "salesorder")),
        None,
    )
    orderable_quotation = next(
        (
            quotation
            for quotation in quotations
            if quotation.lines.all() and not hasattr(quotation, "salesorder")
        ),
        None,
    )
    return render(
        request,
        "crm/detail.html",
        {
            "lead": lead,
            "linked_order": linked_order,
            "orderable_quotation": orderable_quotation,
            "timeline": build_communication_timeline(
                activities=lead.activities.all(),
                deliveries=deliveries,
            ),
            "organization": request.organization,
        },
    )


@login_required
@organization_required
@organization_permission_required(OrganizationPermission.MANAGE_LEADS)
def lead_update(request, public_id):
    lead = get_object_or_404(
        Lead,
        public_id=public_id,
        organization=request.organization,
    )
    form = LeadForm(
        request.POST or None,
        instance=lead,
        organization=request.organization,
    )
    if form.is_valid():
        form.save()
        messages.success(request, "Lead yangilandi.")
        return redirect("crm:detail", public_id=lead.public_id)
    return render(
        request,
        "shared/form.html",
        {
            "form": form,
            "page_title": "Leadni tahrirlash",
            "cancel_url": f"/leads/{lead.public_id}/",
            "organization": request.organization,
        },
    )


@login_required
@organization_required
@organization_permission_required(OrganizationPermission.MANAGE_LEADS)
def lead_status_update(request, public_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    try:
        payload = json.loads(request.body or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return HttpResponseBadRequest("Invalid JSON payload")

    status = payload.get("status")
    position = payload.get("position")
    lost_reason = str(payload.get("lost_reason") or "").strip()
    valid_statuses = dict(Lead.Status.choices)
    if status not in valid_statuses:
        return JsonResponse({"error": "Noto'g'ri lead holati."}, status=400)
    if isinstance(position, bool) or not isinstance(position, int) or position < 0:
        return JsonResponse({"error": "Noto'g'ri Kanban pozitsiyasi."}, status=400)

    with transaction.atomic():
        lead = get_object_or_404(
            Lead.objects.select_for_update(),
            public_id=public_id,
            organization=request.organization,
        )
        old_status = lead.status
        if status in {Lead.Status.WON, Lead.Status.LOST}:
            probability = 100 if status == Lead.Status.WON else 0
            lead.stage = (
                PipelineStage.objects.filter(
                    organization=request.organization,
                    is_closed=True,
                    probability=probability,
                )
                .order_by("position", "name")
                .first()
            )
        elif lead.stage_id and lead.stage.is_closed:
            lead.stage = (
                PipelineStage.objects.filter(
                    organization=request.organization,
                    is_closed=False,
                )
                .order_by("position", "name")
                .first()
            )
        lead.status = status
        if status == Lead.Status.LOST:
            lead.lost_reason = lost_reason or lead.lost_reason
        else:
            lead.lost_reason = ""
        try:
            lead.full_clean()
        except ValidationError as error:
            return JsonResponse(
                {"error": " ".join(error.messages)},
                status=400,
            )
        affected_statuses = {old_status, status}
        affected_leads = list(
            Lead.objects.select_for_update()
            .filter(
                organization=request.organization,
                status__in=affected_statuses,
            )
            .order_by("kanban_position", "-created_at")
        )
        source_leads = [
            item for item in affected_leads if item.status == old_status and item.pk != lead.pk
        ]
        target_leads = [
            item for item in affected_leads if item.status == status and item.pk != lead.pk
        ]
        target_position = min(position, len(target_leads))
        target_leads.insert(target_position, lead)
        ordered_leads = target_leads
        if old_status != status:
            ordered_leads = source_leads + target_leads
        for index, item in enumerate(source_leads):
            item.kanban_position = index
        for index, item in enumerate(target_leads):
            item.kanban_position = index
        Lead.objects.bulk_update(
            ordered_leads,
            ["status", "stage", "lost_reason", "kanban_position"],
        )
        lead.save(update_fields=["updated_at"])

    return JsonResponse(
        {
            "status": lead.status,
            "status_label": lead.get_status_display(),
            "position": lead.kanban_position,
            "message": f"Lead «{lead.title}» — {lead.get_status_display()}.",
        }
    )


@login_required
@organization_required
@organization_permission_required(OrganizationPermission.MANAGE_TASKS)
def activity_create(request, public_id):
    lead = get_object_or_404(
        Lead,
        public_id=public_id,
        organization=request.organization,
    )
    form = ActivityForm(
        request.POST or None,
        organization=request.organization,
    )
    if form.is_valid():
        activity = form.save(commit=False)
        activity.organization = request.organization
        activity.lead = lead
        activity.customer = lead.customer
        activity.save()
        messages.success(request, "Faoliyat qo'shildi.")
        return redirect("crm:detail", public_id=lead.public_id)
    return render(
        request,
        "shared/form.html",
        {
            "form": form,
            "page_title": "Yangi faoliyat",
            "cancel_url": f"/leads/{lead.public_id}/",
            "organization": request.organization,
        },
    )


@login_required
@organization_required
def task_list(request):
    status = request.GET.get("status", "open")
    query = request.GET.get("q", "").strip()
    tasks = Activity.objects.filter(
        organization=request.organization,
    ).select_related("lead", "lead__customer", "customer", "assigned_to")
    if status == "completed":
        tasks = tasks.filter(completed_at__isnull=False)
    elif status != "all":
        tasks = tasks.filter(completed_at__isnull=True)
    if query:
        tasks = tasks.filter(
            Q(subject__icontains=query)
            | Q(lead__title__icontains=query)
            | Q(lead__customer__name__icontains=query)
            | Q(customer__name__icontains=query)
        )
    now = timezone.now()
    return render(
        request,
        "crm/tasks.html",
        {
            "tasks": tasks,
            "status": status,
            "query": query,
            "now": now,
            "organization": request.organization,
        },
    )


@login_required
@organization_required
@organization_permission_required(OrganizationPermission.MANAGE_TASKS)
def task_create(request):
    form = TaskForm(request.POST or None, organization=request.organization)
    if form.is_valid():
        task = form.save(commit=False)
        task.organization = request.organization
        task.save()
        messages.success(request, "Vazifa yaratildi.")
        return redirect("tasks:list")
    return render(
        request,
        "shared/form.html",
        {
            "form": form,
            "page_title": "Yangi vazifa yoki eslatma",
            "cancel_url": "/tasks/",
            "organization": request.organization,
        },
    )


@login_required
@organization_required
@organization_permission_required(OrganizationPermission.MANAGE_TASKS)
def task_complete(request, public_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    task = get_object_or_404(
        Activity,
        public_id=public_id,
        organization=request.organization,
    )
    if task.completed_at is None:
        task.completed_at = timezone.now()
        task.save(update_fields=["completed_at", "updated_at"])
        messages.success(request, "Vazifa bajarildi deb belgilandi.")
    next_url = request.POST.get("next", "/tasks/")
    if not next_url.startswith("/"):
        next_url = "/tasks/"
    return redirect(next_url)
