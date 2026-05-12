from django.contrib import messages
from django.core.paginator import Paginator


SHOW_ALL_LIMIT = 500


def paginate_with_show_all(
    request,
    queryset,
    *,
    default_per_page=20,
    allowed_per_page=None,
    item_label="registros",
):
    """Paginate a queryset and support per_page=all with a safe upper bound."""
    per_page_raw = (request.GET.get("per_page") or "").strip()
    show_all = per_page_raw == "all"
    total_count = queryset.count()

    if show_all:
        per_page = max(1, min(total_count, SHOW_ALL_LIMIT))
        if total_count > SHOW_ALL_LIMIT:
            messages.warning(
                request,
                f"A listagem possui {total_count} {item_label}. "
                f"Para manter a tela responsiva, foram exibidos os primeiros {SHOW_ALL_LIMIT}.",
            )
        page_number = 1
    else:
        try:
            per_page = int(per_page_raw) if per_page_raw else default_per_page
        except (TypeError, ValueError):
            per_page = default_per_page

        if allowed_per_page and per_page not in allowed_per_page:
            per_page = default_per_page

        page_number = request.GET.get("page")

    paginator = Paginator(queryset, per_page)
    page_obj = paginator.get_page(page_number)

    pagination_state = {
        "show_all": show_all,
        "show_all_limited": show_all and total_count > SHOW_ALL_LIMIT,
        "show_all_limit": SHOW_ALL_LIMIT,
        "per_page": "all" if show_all else str(per_page),
    }
    return page_obj, pagination_state
