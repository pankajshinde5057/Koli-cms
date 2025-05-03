from django import template
from datetime import datetime
register = template.Library()

@register.filter
def duration_to_hours_minutes(duration):
    if not duration:
        return "-"
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


@register.filter
def working_duration(duration):
    if not duration:
        return "-"
    total_seconds = int(duration.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes = remainder // 60

    parts = []
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes:
        parts.append(f"{minutes} min")

    return ' '.join(parts) if parts else "0 min"
