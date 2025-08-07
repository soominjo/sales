from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def multiply(value, arg):
    try:
        return Decimal(str(value)) * (Decimal(str(arg)) / Decimal('100'))
    except (ValueError, TypeError):
        return 0

@register.filter
def subtract(value, arg):
    """Subtracts the arg from the value"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return value

@register.filter
def percentage_diff(current, previous):
    try:
        if previous == 0:
            return 0
        current = Decimal(str(current))
        previous = Decimal(str(previous))
        diff = ((current - previous) / previous) * 100
        return diff
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

@register.filter
def index(lst, i):
    try:
        return lst[int(i)]
    except (IndexError, ValueError, TypeError):
        return None

@register.filter
def abs_val(value):
    """Return the absolute value of the number."""
    try:
        return abs(Decimal(str(value)))
    except (ValueError, TypeError):
        return value

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)