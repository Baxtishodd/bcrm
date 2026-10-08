from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.common.pagination import paginate_queryset
from apps.common.permissions import (
    OrganizationPermission,
    can_edit_record,
    can_manage_all_records,
    ensure_record_editable,
    organization_permission_required,
)
from apps.common.tenancy import organization_required
from apps.communications.models import Message
from apps.crm.models import Activity
from apps.crm.timeline import build_communication_timeline
from apps.sales.models import QuotationDelivery

from .forms import (
    ContactForm,
    ContactListFilterForm,
    CustomerCompanyForm,
    CustomerListFilterForm,
)
from .models import Contact, CustomerCompany


@login_required
@organization_required
@organization_permission_required(OrganizationPermission.VIEW_CUSTOMERS)
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
            "filter_create_url": (
                "/customers/new/"
                if request.crm_permissions[OrganizationPermission.CREATE_CUSTOMERS]
                else ""
            ),
            "filter_create_label": "Yangi mijoz",
            "organization": request.organization,
            **pagination,
        },
    )


@login_required
@organization_required
@organization_permission_required(OrganizationPermission.CREATE_CUSTOMERS)
def customer_create(request):
    form = CustomerCompanyForm(
        request.POST or None,
        organization=request.organization,
    )
    if form.is_valid():
        customer = form.save(commit=False)
        customer.organization = request.organization
        if not can_manage_all_records(request.user, request.membership):
            customer.owner = request.user
        elif customer.owner_id is None:
            customer.owner = request.user
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
@organization_permission_required(OrganizationPermission.VIEW_CUSTOMERS)
def customer_detail(request, public_id):
    customer = get_object_or_404(
        CustomerCompany.objects.prefetch_related("contacts__owner"),
        public_id=public_id,
        organization=request.organization,
    )
    activities = Activity.objects.filter(
        Q(customer=customer) | Q(lead__customer=customer),
        organization=request.organization,
    ).select_related("lead", "assigned_to")
    deliveries = QuotationDelivery.objects.filter(
        organization=request.organization,
        quotation__customer=customer,
    ).select_related("quotation", "sent_by")
    communication_messages = Message.objects.filter(
        Q(conversation__customer=customer)
        | Q(conversation__lead__customer=customer)
        | Q(conversation__contact__company=customer),
        organization=request.organization,
    ).select_related("conversation", "sender")
    return render(
        request,
        "customers/detail.html",
        {
            "customer": customer,
            "record_editable": can_edit_record(
                request.user, request.membership, customer
            ),
            "timeline": build_communication_timeline(
                activities=activities.distinct(),
                deliveries=deliveries,
                messages=communication_messages.distinct(),
            ),
            "organization": request.organization,
        },
    )


@login_required
@organization_required
@organization_permission_required(OrganizationPermission.UPDATE_CUSTOMERS)
def customer_update(request, public_id):
    customer = get_object_or_404(
        CustomerCompany,
        public_id=public_id,
        organization=request.organization,
    )
    ensure_record_editable(request, customer)
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
@organization_permission_required(OrganizationPermission.VIEW_CUSTOMERS)
def contact_list(request):
    list_scope = request.GET.get("scope", "all")
    if list_scope not in {"all", "mine"}:
        list_scope = "all"
    view_mode = request.GET.get("view", "cards")
    if view_mode not in {"cards", "table"}:
        view_mode = "cards"
    filter_form = ContactListFilterForm(request.GET, organization=request.organization)
    if list_scope == "mine":
        filter_form.fields.pop("owner", None)
    contacts = Contact.objects.filter(
        organization=request.organization,
    ).select_related("company", "owner")
    if list_scope == "mine":
        contacts = contacts.filter(owner=request.user)
    if filter_form.is_valid():
        query = filter_form.cleaned_data["q"].strip()
        contact_type = filter_form.cleaned_data["contact_type"]
        company = filter_form.cleaned_data["company"]
        country = filter_form.cleaned_data["country"]
        owner = filter_form.cleaned_data.get("owner")
    else:
        query = request.GET.get("q", "").strip()
        contact_type = country = ""
        company = owner = None
    if query:
        contacts = contacts.filter(
            Q(full_name__icontains=query)
            | Q(position__icontains=query)
            | Q(phone__icontains=query)
            | Q(whatsapp__icontains=query)
            | Q(email__icontains=query)
            | Q(tags__icontains=query)
            | Q(company__name__icontains=query)
        )
    if contact_type:
        contacts = contacts.filter(contact_type=contact_type)
    if company:
        contacts = contacts.filter(company=company)
    if country:
        contacts = contacts.filter(country=country)
    if owner:
        contacts = contacts.filter(owner=owner)
    pagination = paginate_queryset(request, contacts)
    tabs_query_params = request.GET.copy()
    tabs_query_params.pop("scope", None)
    tabs_query_params.pop("page", None)
    tabs_query = tabs_query_params.urlencode()
    contacts_path = request.path
    reset_params = []
    if list_scope == "mine":
        reset_params.append("scope=mine")
    if view_mode == "table":
        reset_params.append("view=table")
    reset_query = "&".join(reset_params)
    return render(
        request,
        "customers/contact_list.html",
        {
            "contacts": pagination["page_obj"].object_list,
            "filter_form": filter_form,
            "filter_reset_url": (
                f"{contacts_path}?{reset_query}" if reset_query else contacts_path
            ),
            "filter_create_url": (
                "/customers/contacts/new/"
                if request.crm_permissions[OrganizationPermission.CREATE_CUSTOMERS]
                else ""
            ),
            "filter_create_label": "Yangi kontakt",
            "organization": request.organization,
            "view_mode": view_mode,
            "list_scope": list_scope,
            "contacts_all_url": (
                f"{contacts_path}?{tabs_query}&scope=all"
                if tabs_query
                else f"{contacts_path}?scope=all"
            ),
            "contacts_mine_url": (
                f"{contacts_path}?{tabs_query}&scope=mine"
                if tabs_query
                else f"{contacts_path}?scope=mine"
            ),
            **pagination,
        },
    )


@login_required
@organization_required
@organization_permission_required(OrganizationPermission.VIEW_CUSTOMERS)
def contact_detail(request, public_id):
    contact = get_object_or_404(
        Contact.objects.select_related("company", "owner"),
        public_id=public_id,
        organization=request.organization,
    )
    leads = contact.lead_set.filter(
        organization=request.organization,
    ).select_related("stage", "assigned_to")
    activities = Activity.objects.filter(
        Q(contact=contact) | Q(lead__contact=contact),
        organization=request.organization,
    ).select_related("lead", "assigned_to")
    deliveries = QuotationDelivery.objects.filter(
        organization=request.organization,
        quotation__contact=contact,
    ).select_related("quotation", "sent_by")
    communication_messages = Message.objects.filter(
        Q(conversation__contact=contact) | Q(conversation__lead__contact=contact),
        organization=request.organization,
    ).select_related("conversation", "sender")
    return render(
        request,
        "customers/contact_detail.html",
        {
            "contact": contact,
            "record_editable": can_edit_record(
                request.user, request.membership, contact
            ),
            "leads": leads,
            "timeline": build_communication_timeline(
                activities=activities.distinct(),
                deliveries=deliveries,
                messages=communication_messages.distinct(),
            ),
            "organization": request.organization,
        },
    )


@login_required
@organization_required
@organization_permission_required(OrganizationPermission.CREATE_CUSTOMERS)
def contact_create(request, customer_public_id=None):
    customer = None
    if customer_public_id:
        customer = get_object_or_404(
            CustomerCompany,
            public_id=customer_public_id,
            organization=request.organization,
        )
    form = ContactForm(
        request.POST or None,
        request.FILES or None,
        organization=request.organization,
        initial={"company": customer, "contact_type": Contact.Type.CUSTOMER},
    )
    if form.is_valid():
        contact = form.save(commit=False)
        contact.organization = request.organization
        contact.owner = request.user
        contact.save()
        messages.success(request, "Kontakt qo'shildi.")
        return redirect("customers:contact-detail", public_id=contact.public_id)
    return render(
        request,
        "customers/contact_form.html",
        {
            "form": form,
            "page_title": "Yangi kontakt",
            "cancel_url": (
                f"/customers/{customer.public_id}/" if customer else "/customers/contacts/"
            ),
            "organization": request.organization,
        },
    )


@login_required
@organization_required
@organization_permission_required(OrganizationPermission.UPDATE_CUSTOMERS)
def contact_update(request, public_id):
    contact = get_object_or_404(
        Contact,
        public_id=public_id,
        organization=request.organization,
    )
    ensure_record_editable(request, contact)
    form = ContactForm(
        request.POST or None,
        request.FILES or None,
        instance=contact,
        organization=request.organization,
    )
    if form.is_valid():
        form.save()
        messages.success(request, "Kontakt ma'lumotlari yangilandi.")
        return redirect("customers:contact-detail", public_id=contact.public_id)
    return render(
        request,
        "customers/contact_form.html",
        {
            "form": form,
            "page_title": "Kontaktni tahrirlash",
            "cancel_url": f"/customers/contacts/{contact.public_id}/",
            "organization": request.organization,
        },
    )
