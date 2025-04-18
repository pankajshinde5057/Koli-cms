from .models import CustomUser, AttendanceRecord
from django.utils import timezone
from django.contrib.auth.models import AnonymousUser


def clock_times(request):
    context = {
        "latest_entry": None,
    }

    user = request.user
    if isinstance(user, AnonymousUser) or not user.is_authenticated:
        return context

    try:
        custom_user = CustomUser.objects.get(id=user.id)
        latest_entry = AttendanceRecord.objects.filter(user=custom_user).order_by("-clock_in").first()
        context["latest_entry"] = latest_entry

    except CustomUser.DoesNotExist:
        pass

    return context
