from .models import CustomUser, AttendanceRecord, Notification, EarylyClockOutRequest
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


            fixed_time = timedelta(hours=9) 
            # fixed_time = timedelta(minutes=1) # for testing

            if work_duration >= fixed_time:
                context["complete_8Hours"] = True
                context['work_duration'] = work_duration
            else:
                context['remaining_time'] = int((fixed_time - work_duration).total_seconds())

        if current_record:
            early_request = EarylyClockOutRequest.objects.filter(
                attendance_record=current_record
            ).order_by('-submitted_at').first()
            if early_request:
                context['early_clock_out_status'] = early_request.status
                context['early_clock_out_message'] = early_request.notes or 'No reason provided'

        context["latest_entry"] = latest_entry
        context["current_record"] = current_record

    except CustomUser.DoesNotExist:
        pass

    return context

# def unread_notification_count(request):
#     if request.user.is_authenticated:
#         employee_general_count = Notification.objects.filter(user=request.user, is_read=False, notification_type='notification',role = "employee").count()
#         manager_general_count = Notification.objects.filter(user=request.user, is_read=False, notification_type='notification',role = "manager").count()
#         admin_general_count = Notification.objects.filter(user=request.user, is_read=False, notification_type='notification',role = "admin").count()
#         admin_employee_feedback_count = Notification.objects.filter(user=request.user, is_read=False, notification_type='employee feedback',role = "admin").count()
#         employee_leave_count = Notification.objects.filter(user=request.user, is_read=False, notification_type='leave',role = "employee").count()
#         manager_leave_count = Notification.objects.filter(user=request.user, is_read=False, notification_type='leave',role = "manager").count()
#         admin_leave_count = Notification.objects.filter(user=request.user, is_read=False, notification_type='leave',role = "admin").count()
#         print("general_countgeneral_count>>",employee_general_count,"manager_general_count>>>",manager_general_count,"admin_general_count>>>>>>",admin_general_count,request.user)
#         print("employee_leave_count>>>",employee_leave_count,"manager_leave_count>>>",manager_leave_count,"admin_leave_count>>>>>",admin_leave_count,request.user)
#         print("admin_employee_feedback_count>>",admin_employee_feedback_count)
#     else:
#         general_count = 0
#         leave_count = 0
#         employee_general_count = 0
#         manager_general_count = 0
#         admin_general_count = 0
#         admin_employee_feedback_count = 0
#         employee_leave_count = 0
#         manager_leave_count= 0
#         admin_leave_count= 0

#     return {
#         # 'unread_general_notification_count': general_count,
#         'unread_employee_general_notification_count': employee_general_count,
#         'unread_manager_general_notification_count': manager_general_count,
#         'admin_employee_feedback_count':admin_employee_feedback_count,
#         'admin_general_count':admin_general_count,
#         # 'unread_leave_notification_count': leave_count,
#         'unread_employee_leave_notification_count': employee_leave_count,
#         'unread_manager_leave_notification_count': manager_leave_count,
#         'admin_leave_count':admin_leave_count
#     }

from .models import Notification

def admin_notification_count(request):
    context = {
        'unread_admin_manager_leave_count': 0,
        'unread_admin_general_count': 0,
        'total_admin_notifications': 0,
    }
    
    if request.user.is_authenticated and request.user.is_superuser:
        # Count of unread manager leave applications for admin
        context['unread_admin_manager_leave_count'] = Notification.objects.filter(
            is_read=False,
            notification_type='leave',
            role='manager'  # notifications from managers
        ).count()
        
        # Count of general notifications for admin
        context['unread_admin_general_count'] = Notification.objects.filter(
            is_read=False,
            notification_type='notification',
            role='admin'  # notifications meant for admin
        ).count()
        
        # Total admin notifications count
        context['total_admin_notifications'] = (
            context['unread_admin_manager_leave_count'] + 
            context['unread_admin_general_count']
        )
    
    return context
    
# def unread_notification_count(request):
#     if not request.user.is_authenticated:
#         return {
#             'unread_employee_general_notification_count': 0,
#             'unread_manager_general_notification_count': 0,
#             'admin_employee_feedback_count': 0,
#             'admin_general_count': 0,
#             'unread_employee_leave_notification_count': 0,
#             'unread_manager_leave_notification_count': 0,
#             'admin_leave_count': 0
#         }
    
#     context = {
#         'unread_employee_general_notification_count': 0,
#         'unread_manager_general_notification_count': 0,
#         'admin_employee_feedback_count': 0,
#         'admin_general_count': 0,
#         'unread_employee_leave_notification_count': 0,
#         'unread_manager_leave_notification_count': 0,
#         'admin_leave_count': 0
#     }

#     try:
      
#         general_notifications = Notification.objects.filter(
#             user=request.user,
#             is_read=False
#         ).exclude(
#             notification_type__in=['asset_request', 'asset_issue']
#         )

#         # Employee counts
#         if hasattr(request.user, 'employee'):
#             context.update({
#                 'unread_employee_general_notification_count': general_notifications.filter(
#                     role="employee",
#                     notification_type="notification"
#                 ).count(),
#                 'unread_employee_leave_notification_count': general_notifications.filter(
#                     role="employee",
#                     notification_type="leave"
#                 ).count()
#             })

#         # Manager counts
#         elif hasattr(request.user, 'manager'):
#             context.update({
#                 'unread_manager_general_notification_count': general_notifications.filter(
#                     role="manager",
#                     notification_type="notification"
#                 ).count(),
#                 'unread_manager_leave_notification_count': general_notifications.filter(
#                     role="manager",
#                     notification_type="leave"
#                 ).count()
#             })

#         # Admin counts
#         elif hasattr(request.user, 'admin'):
#             context.update({
#                 'admin_general_count': general_notifications.filter(
#                     role="admin",
#                     notification_type="notification"
#                 ).count(),
#                 'admin_employee_feedback_count': general_notifications.filter(
#                     role="admin",
#                     notification_type="employee feedback"
#                 ).count(),
#                 'admin_leave_count': general_notifications.filter(
#                     role="admin",
#                     notification_type="leave"
#                 ).count()
#             })

#     except Exception as e:
#         # Log error but don't break the site
#         import logging
#         logging.error(f"Error in unread_notification_count context processor: {str(e)}")
    
#     return context



def asset_notification_count(request):
    if not request.user.is_authenticated:
        return {
            'unread_asset_notification_count': 0,
            'unread_asset_request_count': 0,
            'unread_asset_issue_count': 0
        }

    context = {
        'unread_asset_notification_count': 0,
        'unread_asset_request_count': 0,
        'unread_asset_issue_count': 0
    }

    try:
        # For Managers (Asset Requests)
        if hasattr(request.user, 'manager'):
            # Count pending asset requests (manager-specific)
            asset_request_count = Notification.objects.filter(
                user=request.user,
                is_read=False,
                notification_type='asset_request',
                role="manager"
            ).count()
            
            # Count pending asset issues (global, but manager can see)
            asset_issue_count = Notification.objects.filter(
                is_read=False,
                notification_type='asset_issue',
                role="manager"
            ).count()
            
            context.update({
                'unread_asset_notification_count': asset_request_count + asset_issue_count,
                'unread_asset_request_count': asset_request_count,
                'unread_asset_issue_count': asset_issue_count
            })

        # For Employees (if they can have asset notifications)
        elif hasattr(request.user, 'employee'):
            asset_issue_count = Notification.objects.filter(
                user=request.user,
                is_read=False,
                notification_type='asset_issue',
                role="employee"
            ).count()
            
            context.update({
                'unread_asset_notification_count': asset_issue_count,
                'unread_asset_issue_count': asset_issue_count
            })

        # For Admins (if they need to see all asset notifications)
        elif hasattr(request.user, 'admin'):
            asset_request_count = Notification.objects.filter(
                is_read=False,
                notification_type='asset_request'
            ).count()
            
            asset_issue_count = Notification.objects.filter(
                is_read=False,
                notification_type='asset_issue'
            ).count()
            
            context.update({
                'unread_asset_notification_count': asset_request_count + asset_issue_count,
                'unread_asset_request_count': asset_request_count,
                'unread_asset_issue_count': asset_issue_count
            })

    except Exception as e:
        # Log error but don't break the site
        import logging
        logging.error(f"Error in asset_notification_count context processor: {str(e)}")
    
    return context
