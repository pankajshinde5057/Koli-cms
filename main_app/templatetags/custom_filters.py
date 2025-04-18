from django import template
from datetime import datetime
register = template.Library()

@register.filter
def duration_to_hours_minutes(duration):
    if not duration:
        return "0h 0m 0s"
    total_seconds = int(duration.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}h {minutes}m {seconds}s"


@register.filter
def get_item(queryset, id):
    try:
        return queryset.get(id=id)
    except:
        return None