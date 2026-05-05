from django.core.paginator import EmptyPage


def get_current_page_data(
    page,
    paginator
):
    try:
        return paginator.page(page)
    except EmptyPage:
        return paginator.page(paginator.num_pages)
