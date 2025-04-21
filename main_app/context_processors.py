from .models import CustomUser, AttendanceRecord
from django.utils import timezone
from django.contrib.auth.models import AnonymousUser
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta

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
        current_record = AttendanceRecord.objects.filter(user=request.user,clock_out__isnull=True,date=timezone.now().date()).first()

        if latest_entry:
            clock_in_time = latest_entry.clock_in.astimezone(ZoneInfo('Asia/Kolkata'))
            current_time = datetime.now(ZoneInfo('Asia/Kolkata'))
            work_duration = current_time - clock_in_time


            # fixed_time = timedelta(hours=8) 
            fixed_time = timedelta(minutes=1) # for testing

            if work_duration >= fixed_time:
                context["complete_8Hours"] = True
                context['work_duration'] = work_duration
            else:
                context['remaining_time'] = int((fixed_time - work_duration).total_seconds())


        context["latest_entry"] = latest_entry
        context["current_record"] = current_record

    except CustomUser.DoesNotExist:
        pass

    return context
