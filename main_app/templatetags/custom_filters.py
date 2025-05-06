from django import template
from datetime import datetime,timedelta
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


@register.filter
def is_2nd_or_4th_saturday(date, arg):
    try:
        month, year = map(int, arg.split())
        if date.month == month and date.year == year:
            day = date.day
            if date.weekday() == 5:  # Saturday
                week_of_month = (day - 1) // 7
                return week_of_month in [1, 3]  # 2nd and 4th weeks
        return False
    except (ValueError, AttributeError):
        return False
    

@register.filter
def format_timedelta(td):
    if not isinstance(td, timedelta):
        return td
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"