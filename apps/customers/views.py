from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.common.tenancy import organization_required

from .forms import ContactForm, CustomerCompanyForm
from .models import CustomerCompany


@login_required
@organization_required
def customer_list(request):
    query = request.GET.get("q", "").strip()
    customers = CustomerCompany.objects.filter(
        organization=request.organization,
    ).select_related("owner")
    if query:
        customers = customers.filter(
            Q(name__icontains=query)
            | Q(phone__icontains=query)
            | Q(email__icontains=query)
            | Q(tax_id__icontains=query)
        )
    return render(
        request,
        "customers/list.html",
        {"customers": customers, "query": query, "organization": request.organization},
    )


@login_required
@organization_required
def customer_create(request):
    form = CustomerCompanyForm(
        request.POST or None,
        organization=request.organization,
    )
    if form.is_valid():
        customer = form.save(commit=False)
        customer.organization = request.organization
        customer.save()
        messages.success(request, "Mijoz yaratildi.")
        return redirect("customers:detail", public_id=customer.public_id)
    return render(
        request,
        "shared/form.html",
        {
            "form": form,
            "page_title": "Yangi mijoz",
            "cancel_url": "/customers/",
            "organization": request.organization,
        },
    )


@login_required
@organization_required
def customer_detail(request, public_id):
    customer = get_object_or_404(
        CustomerCompany.objects.prefetch_related("contacts"),
        public_id=public_id,
        organization=request.organization,
    )
    return render(
        request,
        "customers/detail.html",
        {"customer": customer, "organization": request.organization},
    )


@login_required
@organization_required
def customer_update(request, public_id):
    customer = get_object_or_404(
        CustomerCompany,
        public_id=public_id,
        organization=request.organization,
    )
    form = CustomerCompanyForm(
        request.POST or None,
        instance=customer,
        organization=request.organization,
    )
    if form.is_valid():
        form.save()
        messages.success(request, "Mijoz ma'lumotlari yangilandi.")
        return redirect("customers:detail", public_id=customer.public_id)
    return render(
        request,
        "shared/form.html",
        {
            "form": form,
            "page_title": "Mijozni tahrirlash",
            "cancel_url": f"/customers/{customer.public_id}/",
            "organization": request.organization,
        },
    )


@login_required
@organization_required
def contact_create(request, public_id):
    customer = get_object_or_404(
        CustomerCompany,
        public_id=public_id,
        organization=request.organization,
    )
    form = ContactForm(request.POST or None)
    if form.is_valid():
        contact = form.save(commit=False)
        contact.organization = request.organization
        contact.company = customer
        contact.save()
        messages.success(request, "Kontakt qo'shildi.")
        return redirect("customers:detail", public_id=customer.public_id)
    return render(
        request,
        "shared/form.html",
        {
            "form": form,
            "page_title": "Yangi kontakt",
            "cancel_url": f"/customers/{customer.public_id}/",
            "organization": request.organization,
        },
    )

