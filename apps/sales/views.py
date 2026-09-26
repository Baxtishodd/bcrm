from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render

from apps.common.tenancy import organization_required

from .forms import QuotationForm, QuotationLineForm, SalesOrderForm
from .models import Quotation, SalesOrder
from .services import convert_quotation_to_order, next_document_number


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
def quotation_create(request):
    form = QuotationForm(
        request.POST or None,
        organization=request.organization,
    )
    if form.is_valid():
        quotation = form.save(commit=False)
        quotation.organization = request.organization
        quotation.created_by = request.user
        if not quotation.number:
            quotation.number = next_document_number(
                Quotation,
                request.organization,
                "QT",
            )
        quotation.save()
        messages.success(request, "Tijorat taklifi yaratildi.")
        return redirect("sales:detail", public_id=quotation.public_id)
    return render(
        request,
        "shared/form.html",
        {
            "form": form,
            "page_title": "Yangi tijorat taklifi",
            "cancel_url": "/sales/",
            "organization": request.organization,
        },
    )


@login_required
@organization_required
def quotation_detail(request, public_id):
    quotation = get_object_or_404(
        Quotation.objects.select_related(
            "customer",
            "lead",
            "created_by",
        ).prefetch_related("lines__product"),
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
def quotation_line_create(request, public_id):
    quotation = get_object_or_404(
        Quotation,
        public_id=public_id,
        organization=request.organization,
    )
    form = QuotationLineForm(
        request.POST or None,
        organization=request.organization,
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
        Quotation.objects.select_related("customer", "lead", "created_by").prefetch_related(
            "lines__product"
        ),
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
                "SO",
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
