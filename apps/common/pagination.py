from django.core.paginator import Paginator

from .forms import ListFilterForm


def paginate_queryset(request, queryset, default_per_page=25):
    allowed_sizes = {
        int(value) for value, _label in ListFilterForm.PER_PAGE_CHOICES
    }
    try:
        requested_size = int(request.GET.get("per_page", default_per_page))
    except (TypeError, ValueError):
        requested_size = default_per_page
    per_page = (
        requested_size if requested_size in allowed_sizes else default_per_page
    )

    paginator = Paginator(queryset, per_page)
    page_obj = paginator.get_page(request.GET.get("page"))
    query_params = request.GET.copy()
    query_params.pop("page", None)

    return {
        "page_obj": page_obj,
        "paginator": paginator,
        "pagination_query": query_params.urlencode(),
        "pagination_page_range": paginator.get_elided_page_range(
            page_obj.number,
            on_each_side=1,
            on_ends=1,
        ),
        "per_page": per_page,
    }
