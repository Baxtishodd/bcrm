from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.common.tenancy import organization_required

from .forms import ProductForm, ProductVariantForm
from .models import Product


@login_required
@organization_required
def product_list(request):
    query = request.GET.get("q", "").strip()
    products = Product.objects.filter(
        organization=request.organization,
    ).select_related("fabric")
    if query:
        products = products.filter(
            Q(article__icontains=query) | Q(name__icontains=query)
        )
    return render(
        request,
        "catalog/list.html",
        {"products": products, "query": query, "organization": request.organization},
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
        Product.objects.select_related("fabric").prefetch_related(
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

