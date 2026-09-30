from datetime import timedelta
from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.models import MailboxAccount
from apps.common.permissions import OrganizationPermission, organization_permission_required
from apps.common.tenancy import organization_required
from apps.crm.models import Lead

from .forms import (
    QuotationDeliveryForm,
    QuotationDocumentForm,
    QuotationDocumentLineFormSet,
    QuotationEmailForm,
    QuotationForm,
    QuotationLineForm,
    SalesOrderForm,
)
from .models import Quotation, QuotationDelivery, SalesOrder
from .pdf import build_quotation_pdf, quotation_pdf_filename
from .services import (
    QuotationEmailError,
    convert_quotation_to_order,
    next_document_number,
    send_quotation_email,
)


@login_required
@organization_required
def quotation_list(request):
    query = request.GET.get("q", "").strip()
    quotations = Quotation.objects.filter(
        organization=request.organization,
    ).select_related("customer", "created_by")
    if query:
        quotations = quotations.filter(
            Q(number__icontains=query) | Q(customer__name__icontains=query)
        )
    return render(
        request,
        "sales/list.html",
        {
            "quotations": quotations,
            "query": query,
            "organization": request.organization,
        },
    )


@login_required
@organization_required
@organization_permission_required(OrganizationPermission.MANAGE_SALES)
def quotation_create(request, lead_public_id=None):
    source_lead = None
    initial = {}
    cancel_url = "/sales/"
    if lead_public_id:
        source_lead = get_object_or_404(
            Lead.objects.select_related("customer", "contact", "assigned_to"),
            public_id=lead_public_id,
            organization=request.organization,
        )
        cancel_url = f"/leads/{source_lead.public_id}/"
        if source_lead.customer_id is None:
            messages.error(
                request,
                "Savdo taklifi yaratishdan oldin Lead'ga mijoz biriktiring.",
            )
            return redirect("crm:detail", public_id=source_lead.public_id)
        initial = {
            "customer": source_lead.customer,
            "contact": source_lead.contact,
            "lead": source_lead,
            "assigned_to": source_lead.assigned_to or request.user,
            "currency": source_lead.currency or request.organization.default_currency,
            "valid_until": timezone.localdate()
            + timedelta(days=request.organization.quotation_validity_days),
            "delivery_terms": request.organization.default_delivery_terms,
            "payment_terms": request.organization.default_payment_terms,
            "notes": source_lead.description,
        }
    elif request.method == "GET":
        initial = {
            "currency": request.organization.default_currency,
            "valid_until": timezone.localdate()
            + timedelta(days=request.organization.quotation_validity_days),
            "delivery_terms": request.organization.default_delivery_terms,
            "payment_terms": request.organization.default_payment_terms,
            "assigned_to": request.user,
        }
    form = QuotationForm(
        request.POST or None,
        organization=request.organization,
        source_lead=source_lead,
        initial=initial,
    )
    if form.is_valid():
        quotation = form.save(commit=False)
        quotation.organization = request.organization
        quotation.created_by = request.user
        if not quotation.number:
            quotation.number = next_document_number(
                Quotation,
                request.organization,
            )
        quotation.save()
        messages.success(request, "Tijorat taklifi yaratildi.")
        return redirect("sales:detail", public_id=quotation.public_id)
    return render(
        request,
        "shared/form.html",
        {
            "form": form,
            "page_title": (
                f"{source_lead.title} uchun savdo taklifi"
                if source_lead
                else "Yangi tijorat taklifi"
            ),
            "cancel_url": cancel_url,
            "organization": request.organization,
        },
    )


@login_required
@organization_required
def quotation_detail(request, public_id):
    quotation = get_object_or_404(
        Quotation.objects.select_related(
            "customer",
            "contact",
            "lead",
            "assigned_to",
            "created_by",
        ).prefetch_related(
            "lines__product",
            "lines__variant__color",
            "lines__variant__size",
            "deliveries__sent_by",
        ),
        public_id=public_id,
        organization=request.organization,
    )
    return render(
        request,
        "sales/detail.html",
        {"quotation": quotation, "organization": request.organization},
    )


@login_required
@organization_required
@organization_permission_required(OrganizationPermission.MANAGE_SALES)
def quotation_delivery_create(request, public_id):
    quotation = get_object_or_404(
        Quotation,
        public_id=public_id,
        organization=request.organization,
    )
    form = QuotationDeliveryForm(request.POST or None)
    if form.is_valid():
        delivery = form.save(commit=False)
        delivery.organization = request.organization
        delivery.quotation = quotation
        delivery.sent_by = request.user
        delivery.save()
        if (
            quotation.status == Quotation.Status.DRAFT
            and delivery.status != QuotationDelivery.Status.FAILED
        ):
            quotation.status = Quotation.Status.SENT
            quotation.save(update_fields=["status", "updated_at"])
        messages.success(request, "Taklif yuborish tarixi saqlandi.")
        return redirect("sales:detail", public_id=quotation.public_id)
    return render(
        request,
        "shared/form.html",
        {
            "form": form,
            "page_title": f"{quotation.number} yuborilishini qayd etish",
            "cancel_url": f"/sales/{quotation.public_id}/",
            "organization": request.organization,
        },
    )


@login_required
@organization_required
@organization_permission_required(OrganizationPermission.MANAGE_SALES)
def quotation_email_send(request, public_id):
    quotation = get_object_or_404(
        Quotation.objects.select_related(
            "organization",
            "customer",
            "contact",
            "lead",
            "assigned_to",
        ).prefetch_related(
            "lines__product",
            "lines__variant__color",
            "lines__variant__size",
        ),
        public_id=public_id,
        organization=request.organization,
    )
    recipient = ""
    if quotation.contact and quotation.contact.email:
        recipient = quotation.contact.email
    elif quotation.customer.email:
        recipient = quotation.customer.email
    accounts = MailboxAccount.objects.filter(
        organization=request.organization,
        user=request.user,
        is_active=True,
    )
    default_account = accounts.filter(is_default=True).first() or accounts.first()
    initial = {
        "account": default_account,
        "recipient": recipient,
        "subject": f"{quotation.number} — {request.organization.document_name} tijorat taklifi",
        "message": (
            f"Assalomu alaykum,\n\n{quotation.number} raqamli tijorat taklifini "
            "PDF ko'rinishida ilova qilmoqdamiz.\n\nHurmat bilan,\n"
            f"{request.organization.document_name}"
        ),
        "follow_up_at": timezone.localtime(
            timezone.now() + timedelta(days=3)
        ).strftime("%Y-%m-%dT%H:%M"),
    }
    form = QuotationEmailForm(
        request.POST or None,
        initial=initial,
        accounts=accounts,
    )
    if form.is_valid():
        try:
            send_quotation_email(
                quotation=quotation,
                actor=request.user,
                **form.cleaned_data,
            )
        except QuotationEmailError as error:
            form.add_error(None, str(error))
        else:
            messages.success(
                request,
                "Taklif email orqali yuborildi va follow-up vazifasi yaratildi.",
            )
            return redirect("sales:detail", public_id=quotation.public_id)
    return render(
        request,
        "shared/form.html",
        {
            "form": form,
            "page_title": f"{quotation.number} taklifini email orqali yuborish",
            "submit_label": "Email yuborish",
            "submit_loading_label": "Yuborilmoqda...",
            "submit_waiting_message": (
                "SMTP server javobi kutilmoqda. Tugmani qayta bosmang — "
                "natija avtomatik ko'rsatiladi."
            ),
            "form_notice": (
                "Email yuborishdan oldin shaxsiy IMAP va SMTP akkauntingizni ulang."
                if not default_account
                else "Xat tanlangan shaxsiy SMTP akkauntingiz orqali yuboriladi."
            ),
            "form_notice_url": "/account/email/new/" if not default_account else "",
            "form_notice_link": "Email akkauntini ulash",
            "submit_disabled": not default_account,
            "cancel_url": f"/sales/{quotation.public_id}/",
            "organization": request.organization,
        },
    )


@login_required
@organization_required
@organization_permission_required(OrganizationPermission.MANAGE_SALES)
def quotation_update(request, public_id):
    quotation = get_object_or_404(
        Quotation,
        public_id=public_id,
        organization=request.organization,
    )
    form = QuotationForm(
        request.POST or None,
        instance=quotation,
        organization=request.organization,
    )
    if form.is_valid():
        form.save()
        messages.success(request, "Tijorat taklifi yangilandi.")
        return redirect("sales:detail", public_id=quotation.public_id)
    return render(
        request,
        "shared/form.html",
        {
            "form": form,
            "page_title": "Taklifni tahrirlash",
            "cancel_url": f"/sales/{quotation.public_id}/",
            "organization": request.organization,
        },
    )


@login_required
@organization_required
@organization_permission_required(OrganizationPermission.MANAGE_SALES)
def quotation_line_create(request, public_id):
    quotation = get_object_or_404(
        Quotation,
        public_id=public_id,
        organization=request.organization,
    )
    form = QuotationLineForm(
        request.POST or None,
        organization=request.organization,
        quotation=quotation,
    )
    if form.is_valid():
        line = form.save(commit=False)
        line.organization = request.organization
        line.quotation = quotation
        line.save()
        messages.success(request, "Taklif qatori qo'shildi.")
        return redirect("sales:detail", public_id=quotation.public_id)
    return render(
        request,
        "shared/form.html",
        {
            "form": form,
            "page_title": "Taklifga mahsulot qo'shish",
            "cancel_url": f"/sales/{quotation.public_id}/",
            "organization": request.organization,
        },
    )


@login_required
@organization_required
def quotation_print(request, public_id):
    quotation = get_object_or_404(
        Quotation.objects.select_related(
            "customer", "contact", "lead", "assigned_to", "created_by"
        ).prefetch_related("lines__product", "lines__variant"),
        public_id=public_id,
        organization=request.organization,
    )
    return render(
        request,
        "sales/quotation_print.html",
        {"quotation": quotation, "organization": request.organization},
    )


@login_required
@organization_required
@organization_permission_required(OrganizationPermission.MANAGE_SALES)
def quotation_document_edit(request, public_id):
    quotation = get_object_or_404(
        Quotation.objects.select_related(
            "organization",
            "customer",
            "contact",
        ).prefetch_related(
            "lines__product",
            "lines__variant__color",
            "lines__variant__size",
        ),
        public_id=public_id,
        organization=request.organization,
    )
    form = QuotationDocumentForm(request.POST or None, instance=quotation)
    line_formset = QuotationDocumentLineFormSet(
        request.POST or None,
        instance=quotation,
        prefix="lines",
        form_kwargs={
            "organization": request.organization,
            "quotation": quotation,
        },
    )
    if form.is_valid() and line_formset.is_valid():
        with transaction.atomic():
            form.save()
            lines = line_formset.save(commit=False)
            for deleted_line in line_formset.deleted_objects:
                deleted_line.delete()
            for line in lines:
                line.organization = request.organization
                line.quotation = quotation
                line.save()
            line_formset.save_m2m()
        messages.success(request, "Savdo taklifi hujjati saqlandi.")
        return redirect("sales:document-edit", public_id=quotation.public_id)
    return render(
        request,
        "sales/document_editor.html",
        {
            "quotation": quotation,
            "form": form,
            "line_formset": line_formset,
            "organization": request.organization,
        },
    )


@login_required
@organization_required
def quotation_pdf(request, public_id):
    quotation = get_object_or_404(
        Quotation.objects.select_related(
            "organization",
            "customer",
            "contact",
            "lead",
            "assigned_to",
            "created_by",
        ).prefetch_related(
            "lines__product__fabric",
            "lines__product__yarn_specification",
            "lines__product__woven_specification",
            "lines__variant__color",
            "lines__variant__size",
        ),
        public_id=public_id,
        organization=request.organization,
    )
    filename = quotation_pdf_filename(quotation)
    response = HttpResponse(build_quotation_pdf(quotation), content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="{filename}"; filename*=UTF-8\'\'{quote(filename)}'
    )
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
@organization_required
@organization_permission_required(OrganizationPermission.MANAGE_SALES)
def quotation_convert(request, public_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    quotation = get_object_or_404(
        Quotation,
        public_id=public_id,
        organization=request.organization,
    )
    if not quotation.lines.exists():
        messages.error(request, "Buyurtma yaratish uchun taklifga mahsulot qo'shing.")
        return redirect("sales:detail", public_id=quotation.public_id)
    order, created = convert_quotation_to_order(quotation, request.user)
    if created:
        messages.success(request, f"{order.number} buyurtmasi yaratildi.")
    else:
        messages.info(request, "Bu taklifdan buyurtma avval yaratilgan.")
    return redirect("sales:order-detail", public_id=order.public_id)


@login_required
@organization_required
def order_list(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    orders = SalesOrder.objects.filter(
        organization=request.organization,
    ).select_related("customer", "assigned_to", "quotation").prefetch_related("lines")
    if query:
        orders = orders.filter(
            Q(number__icontains=query) | Q(customer__name__icontains=query)
        )
    if status:
        orders = orders.filter(status=status)
    return render(
        request,
        "sales/order_list.html",
        {
            "orders": orders,
            "query": query,
            "status": status,
            "status_choices": SalesOrder.Status.choices,
            "organization": request.organization,
        },
    )


@login_required
@organization_required
def order_detail(request, public_id):
    order = get_object_or_404(
        SalesOrder.objects.select_related(
            "customer",
            "quotation",
            "assigned_to",
            "created_by",
        ).prefetch_related("lines__product"),
        public_id=public_id,
        organization=request.organization,
    )
    return render(
        request,
        "sales/order_detail.html",
        {"order": order, "organization": request.organization},
    )


@login_required
@organization_required
@organization_permission_required(OrganizationPermission.MANAGE_SALES)
def order_update(request, public_id):
    order = get_object_or_404(
        SalesOrder,
        public_id=public_id,
        organization=request.organization,
    )
    form = SalesOrderForm(
        request.POST or None,
        instance=order,
        organization=request.organization,
    )
    if form.is_valid():
        updated_order = form.save(commit=False)
        if not updated_order.number:
            updated_order.number = next_document_number(
                SalesOrder,
                request.organization,
            )
        updated_order.save()
        messages.success(request, "Buyurtma yangilandi.")
        return redirect("sales:order-detail", public_id=order.public_id)
    return render(
        request,
        "shared/form.html",
        {
            "form": form,
            "page_title": "Buyurtmani tahrirlash",
            "cancel_url": f"/sales/orders/{order.public_id}/",
            "organization": request.organization,
        },
    )
