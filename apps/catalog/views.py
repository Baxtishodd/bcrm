from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.common.tenancy import organization_required

from .forms import (
    PriceListDocumentLineFormSet,
    PriceListForm,
    PriceListLineForm,
    ProductForm,
    ProductVariantForm,
    WovenFabricSpecificationForm,
    YarnSpecificationForm,
)
from .models import (
    PriceList,
    Product,
    WovenFabricSpecification,
    YarnSpecification,
)
from .pdf import build_price_list_pdf, price_list_pdf_filename


@login_required
@organization_required
def product_list(request):
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "")
    products = Product.objects.filter(
        organization=request.organization,
    ).select_related("fabric")
    if query:
        products = products.filter(
            Q(article__icontains=query) | Q(name__icontains=query)
        )
    if category:
        products = products.filter(category=category)
    return render(
        request,
        "catalog/list.html",
        {
            "products": products,
            "query": query,
            "category": category,
            "category_choices": Product.Category.choices,
            "organization": request.organization,
        },
    )


@login_required
@organization_required
def price_list(request):
    query = request.GET.get("q", "").strip()
    availability = request.GET.get("availability", "")
    category = request.GET.get("category", "")
    products = Product.objects.filter(
        organization=request.organization,
        is_active=True,
        list_price__isnull=False,
    ).select_related("fabric")
    if query:
        products = products.filter(
            Q(article__icontains=query)
            | Q(name__icontains=query)
            | Q(fabric__name__icontains=query)
        )
    if availability:
        products = products.filter(availability=availability)
    if category:
        products = products.filter(category=category)
    return render(
        request,
        "catalog/price_list.html",
        {
            "products": products,
            "query": query,
            "availability": availability,
            "availability_choices": Product.Availability.choices,
            "category": category,
            "category_choices": Product.Category.choices,
            "today": timezone.localdate(),
            "organization": request.organization,
        },
    )


@login_required
@organization_required
def product_create(request):
    form = ProductForm(
        request.POST or None,
        request.FILES or None,
        organization=request.organization,
    )
    if form.is_valid():
        product = form.save(commit=False)
        product.organization = request.organization
        product.save()
        messages.success(request, "Mahsulot yaratildi.")
        return redirect("catalog:detail", public_id=product.public_id)
    return render(
        request,
        "shared/form.html",
        {
            "form": form,
            "page_title": "Yangi mahsulot",
            "cancel_url": "/catalog/",
            "organization": request.organization,
        },
    )


@login_required
@organization_required
def product_detail(request, public_id):
    product = get_object_or_404(
        Product.objects.select_related(
            "fabric",
            "yarn_specification",
            "woven_specification",
        ).prefetch_related(
            "variants__color",
            "variants__size",
        ),
        public_id=public_id,
        organization=request.organization,
    )
    return render(
        request,
        "catalog/detail.html",
        {"product": product, "organization": request.organization},
    )


@login_required
@organization_required
def product_specification_update(request, public_id):
    product = get_object_or_404(
        Product,
        public_id=public_id,
        organization=request.organization,
    )
    if product.category == Product.Category.YARN:
        form_class = YarnSpecificationForm
        model_class = YarnSpecification
        page_title = f"{product.name} — ip texnikasi"
    elif product.category == Product.Category.WOVEN_FABRIC:
        form_class = WovenFabricSpecificationForm
        model_class = WovenFabricSpecification
        page_title = f"{product.name} — mato texnikasi"
    else:
        messages.info(
            request,
            "Bu kategoriya uchun alohida texnik forma hali talab qilinmaydi.",
        )
        return redirect("catalog:detail", public_id=product.public_id)

    instance = model_class.objects.filter(
        organization=request.organization,
        product=product,
    ).first()
    form = form_class(request.POST or None, instance=instance)
    if form.is_valid():
        specification = form.save(commit=False)
        specification.organization = request.organization
        specification.product = product
        specification.save()
        if product.category == Product.Category.YARN:
            product.yarn_count = specification.yarn_count
            product.save(update_fields=["yarn_count", "updated_at"])
        messages.success(request, "Texnik xususiyatlar saqlandi.")
        return redirect("catalog:detail", public_id=product.public_id)
    return render(
        request,
        "shared/form.html",
        {
            "form": form,
            "page_title": page_title,
            "cancel_url": f"/catalog/{product.public_id}/",
            "organization": request.organization,
        },
    )


@login_required
@organization_required
def offer_list(request):
    offers = PriceList.objects.filter(
        organization=request.organization,
    ).prefetch_related("lines")
    return render(
        request,
        "catalog/offer_list.html",
        {"offers": offers, "organization": request.organization},
    )


@login_required
@organization_required
def offer_create(request):
    form = PriceListForm(request.POST or None)
    if form.is_valid():
        offer = form.save(commit=False)
        offer.organization = request.organization
        offer.created_by = request.user
        offer.save()
        messages.success(request, "Taklif hujjati yaratildi.")
        return redirect("catalog:offer-detail", public_id=offer.public_id)
    return render(
        request,
        "shared/form.html",
        {
            "form": form,
            "page_title": "Yangi price-list yoki product-list",
            "cancel_url": "/catalog/offers/",
            "organization": request.organization,
        },
    )


@login_required
@organization_required
def offer_detail(request, public_id):
    offer = get_object_or_404(
        PriceList.objects.prefetch_related("lines__product"),
        public_id=public_id,
        organization=request.organization,
    )
    return render(
        request,
        "catalog/offer_detail.html",
        {"offer": offer, "organization": request.organization},
    )


@login_required
@organization_required
def offer_update(request, public_id):
    offer = get_object_or_404(
        PriceList,
        public_id=public_id,
        organization=request.organization,
    )
    form = PriceListForm(request.POST or None, instance=offer)
    if form.is_valid():
        form.save()
        messages.success(request, "Taklif hujjati yangilandi.")
        return redirect("catalog:offer-detail", public_id=offer.public_id)
    return render(
        request,
        "shared/form.html",
        {
            "form": form,
            "page_title": "Taklif hujjatini tahrirlash",
            "cancel_url": f"/catalog/offers/{offer.public_id}/",
            "organization": request.organization,
        },
    )


@login_required
@organization_required
def offer_document_edit(request, public_id):
    offer = get_object_or_404(
        PriceList.objects.select_related("organization").prefetch_related(
            "lines__product__fabric",
            "lines__product__yarn_specification",
            "lines__product__woven_specification",
        ),
        public_id=public_id,
        organization=request.organization,
    )
    form = PriceListForm(request.POST or None, instance=offer)
    line_formset = PriceListDocumentLineFormSet(
        request.POST or None,
        instance=offer,
        prefix="lines",
        form_kwargs={
            "organization": request.organization,
            "price_list": offer,
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
                line.price_list = offer
                line.save()
            line_formset.save_m2m()
        messages.success(request, "Taklif hujjati saqlandi.")
        return redirect("catalog:offer-document-edit", public_id=offer.public_id)
    return render(
        request,
        "catalog/offer_document_editor.html",
        {
            "offer": offer,
            "form": form,
            "line_formset": line_formset,
            "organization": request.organization,
        },
    )


@login_required
@organization_required
def offer_pdf(request, public_id):
    offer = get_object_or_404(
        PriceList.objects.select_related("organization").prefetch_related(
            "lines__product__fabric",
            "lines__product__yarn_specification",
            "lines__product__woven_specification",
        ),
        public_id=public_id,
        organization=request.organization,
    )
    filename = price_list_pdf_filename(offer)
    response = HttpResponse(build_price_list_pdf(offer), content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="{filename}"; filename*=UTF-8\'\'{quote(filename)}'
    )
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
@organization_required
def offer_line_create(request, public_id):
    offer = get_object_or_404(
        PriceList,
        public_id=public_id,
        organization=request.organization,
    )
    default_units = {
        Product.Category.YARN: Product.Unit.KILOGRAM,
        Product.Category.WOVEN_FABRIC: Product.Unit.METER,
        Product.Category.KNITTED_FABRIC: Product.Unit.KILOGRAM,
        Product.Category.APPAREL: Product.Unit.PIECE,
    }
    form = PriceListLineForm(
        request.POST or None,
        organization=request.organization,
        price_list=offer,
        initial={"unit": default_units.get(offer.category, Product.Unit.PIECE)},
    )
    if form.is_valid():
        line = form.save(commit=False)
        line.organization = request.organization
        line.price_list = offer
        line.save()
        messages.success(request, "Taklifga mahsulot qo'shildi.")
        return redirect("catalog:offer-detail", public_id=offer.public_id)
    return render(
        request,
        "shared/form.html",
        {
            "form": form,
            "page_title": f"{offer.number} — mahsulot qo'shish",
            "cancel_url": f"/catalog/offers/{offer.public_id}/",
            "organization": request.organization,
        },
    )


@login_required
@organization_required
def product_update(request, public_id):
    product = get_object_or_404(
        Product,
        public_id=public_id,
        organization=request.organization,
    )
    form = ProductForm(
        request.POST or None,
        request.FILES or None,
        instance=product,
        organization=request.organization,
    )
    if form.is_valid():
        form.save()
        messages.success(request, "Mahsulot yangilandi.")
        return redirect("catalog:detail", public_id=product.public_id)
    return render(
        request,
        "shared/form.html",
        {
            "form": form,
            "page_title": "Mahsulotni tahrirlash",
            "cancel_url": f"/catalog/{product.public_id}/",
            "organization": request.organization,
        },
    )


@login_required
@organization_required
def variant_create(request, public_id):
    product = get_object_or_404(
        Product,
        public_id=public_id,
        organization=request.organization,
    )
    form = ProductVariantForm(
        request.POST or None,
        organization=request.organization,
    )
    if form.is_valid():
        variant = form.save(commit=False)
        variant.organization = request.organization
        variant.product = product
        variant.save()
        messages.success(request, "Rang-o'lcham varianti qo'shildi.")
        return redirect("catalog:detail", public_id=product.public_id)
    return render(
        request,
        "shared/form.html",
        {
            "form": form,
            "page_title": "Yangi variant",
            "cancel_url": f"/catalog/{product.public_id}/",
            "organization": request.organization,
        },
    )
