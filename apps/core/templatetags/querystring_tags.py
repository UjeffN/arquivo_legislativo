from django import template


register = template.Library()


@register.simple_tag(takes_context=True)
def querystring(context, **kwargs):
    request = context.get("request")
    if request is None:
        return ""

    query = request.GET.copy()
    for key, value in kwargs.items():
        if value is None or value == "":
            query.pop(key, None)
        else:
            query[key] = value
    return query.urlencode()
