from .models import CustomUser, AttendanceRecord, Notification
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
            fixed_time = timedelta(seconds=15) # for testing

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

def unread_notification_count(request):
    if request.user.is_authenticated:
        employee_general_count = Notification.objects.filter(user=request.user, is_read=False, notification_type='notification',role = "employee").count()
        manager_general_count = Notification.objects.filter(user=request.user, is_read=False, notification_type='notification',role = "manager").count()
        admin_general_count = Notification.objects.filter(user=request.user, is_read=False, notification_type='notification',role = "admin").count()
        admin_employee_feedback_count = Notification.objects.filter(user=request.user, is_read=False, notification_type='employee feedback',role = "admin").count()
        employee_leave_count = Notification.objects.filter(user=request.user, is_read=False, notification_type='leave',role = "employee").count()
        manager_leave_count = Notification.objects.filter(user=request.user, is_read=False, notification_type='leave',role = "manager").count()
        admin_leave_count = Notification.objects.filter(user=request.user, is_read=False, notification_type='leave',role = "admin").count()
        print("general_countgeneral_count>>",employee_general_count,"manager_general_count>>>",manager_general_count,"admin_general_count>>>>>>",admin_general_count,request.user)
        print("employee_leave_count>>>",employee_leave_count,"manager_leave_count>>>",manager_leave_count,"admin_leave_count>>>>>",admin_leave_count,request.user)
        print("admin_employee_feedback_count>>",admin_employee_feedback_count)
    else:
        general_count = 0
        leave_count = 0
        employee_general_count = 0
        manager_general_count = 0
        admin_general_count = 0
        admin_employee_feedback_count = 0
        employee_leave_count = 0
        manager_leave_count= 0
        admin_leave_count= 0

    return {
        # 'unread_general_notification_count': general_count,
        'unread_employee_general_notification_count': employee_general_count,
        'unread_manager_general_notification_count': manager_general_count,
        'admin_employee_feedback_count':admin_employee_feedback_count,
        'admin_general_count':admin_general_count,
        # 'unread_leave_notification_count': leave_count,
        'unread_employee_leave_notification_count': employee_leave_count,
        'unread_manager_leave_notification_count': manager_leave_count,
        'admin_leave_count':admin_leave_count
    }