from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.common.tenancy import organization_required

from .forms import ActivityForm, LeadForm, TaskForm
from .models import Activity, Lead


@login_required
@organization_required
def lead_list(request):
    query = request.GET.get("q", "").strip()
    leads = Lead.objects.filter(
        organization=request.organization,
    ).select_related("customer", "stage", "assigned_to")
    if query:
        leads = leads.filter(
            Q(title__icontains=query)
            | Q(customer__name__icontains=query)
            | Q(source__icontains=query)
        )
    columns = [
        (value, label, leads.filter(status=value))
        for value, label in Lead.Status.choices
    ]
    return render(
        request,
        "crm/list.html",
        {
            "columns": columns,
            "query": query,
            "organization": request.organization,
        },
    )


@login_required
@organization_required
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
        ).prefetch_related("activities"),
        public_id=public_id,
        organization=request.organization,
    )
    return render(
        request,
        "crm/detail.html",
        {"lead": lead, "organization": request.organization},
    )


@login_required
@organization_required
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
    ).select_related("lead", "lead__customer", "assigned_to")
    if status == "completed":
        tasks = tasks.filter(completed_at__isnull=False)
    elif status != "all":
        tasks = tasks.filter(completed_at__isnull=True)
    if query:
        tasks = tasks.filter(
            Q(subject__icontains=query)
            | Q(lead__title__icontains=query)
            | Q(lead__customer__name__icontains=query)
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
