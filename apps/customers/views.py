from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.common.pagination import paginate_queryset
from apps.common.tenancy import organization_required

from .forms import ContactForm, CustomerCompanyForm, CustomerListFilterForm
from .models import CustomerCompany


@login_required
@organization_required
def customer_list(request):
    filter_form = CustomerListFilterForm(
        request.GET,
        organization=request.organization,
    )
    customers = CustomerCompany.objects.filter(
        organization=request.organization,
    ).select_related("owner")
    if filter_form.is_valid():
        query = filter_form.cleaned_data["q"].strip()
        relationship_status = filter_form.cleaned_data["relationship_status"]
        business_direction = filter_form.cleaned_data["business_direction"]
        country = filter_form.cleaned_data["country"]
        owner = filter_form.cleaned_data["owner"]
    else:
        query = request.GET.get("q", "").strip()
        relationship_status = ""
        business_direction = ""
        country = ""
        owner = None

    if query:
        customers = customers.filter(
            Q(name__icontains=query)
            | Q(phone__icontains=query)
            | Q(whatsapp__icontains=query)
            | Q(email__icontains=query)
            | Q(tax_id__icontains=query)
            | Q(product_interest__icontains=query)
            | Q(purchase_purpose__icontains=query)
            | Q(notes__icontains=query)
            | Q(contacts__full_name__icontains=query)
            | Q(contacts__phone__icontains=query)
        )
    if relationship_status:
        customers = customers.filter(relationship_status=relationship_status)
    if business_direction:
        customers = customers.filter(business_direction=business_direction)
    if country:
        customers = customers.filter(country=country)
    if owner:
        customers = customers.filter(owner=owner)
    customers = customers.distinct()
    pagination = paginate_queryset(request, customers)
    return render(
        request,
        "customers/list.html",
        {
            "customers": pagination["page_obj"].object_list,
            "filter_form": filter_form,
            "filter_reset_url": "/customers/",
            "filter_create_url": "/customers/new/",
            "filter_create_label": "Yangi mijoz",
            "organization": request.organization,
            **pagination,
        },
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
