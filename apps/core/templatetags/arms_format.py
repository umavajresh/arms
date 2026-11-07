from django import template

register = template.Library()


@register.filter
def inr(value):
    try:
        return "₹{:,.2f}".format(float(value))
    except (TypeError, ValueError):
        return value
