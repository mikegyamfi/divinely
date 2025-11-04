import re
from django import template

register = template.Library()

@register.filter
def format_bundle(value):
    """
    Converts offer strings like '500MB' or '1500 MB' to readable format:
      500MB → 500MB
      1500MB → 1.5GB
    """
    if not value:
        return ""

    s = str(value).upper().replace(" ", "")
    match = re.match(r"([\d]+(?:\.\d+)?)", s)
    if not match:
        return value

    amount = float(match.group(1))
    if amount >= 1000:
        gb = amount / 1000
        return f"{gb:.2f}".rstrip("0").rstrip(".") + "GB"
    else:
        return f"{int(amount) if amount.is_integer() else amount}MB"
