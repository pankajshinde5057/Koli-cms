
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from main_app.models import Notification
from django.views.decorators.csrf import csrf_exempt

def send_notification(user, message,notification_type,id,role):
    Notification.objects.create(
        user=user,
        message=message,
        notification_type = notification_type,
        leave_or_notification_id = id,
        role = role
    )

def employee_view_notification(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')

    # Mark all as read when viewed
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)

    return render(request, 'employee/notifications.html', {
        'notifications': notifications
    })


@csrf_exempt
def mark_notification_read(request, notification_id,type,role):
    
    if request.method == 'POST':
        if type == "leave":
            notification = Notification.objects.filter(leave_or_notification_id=notification_id, user=request.user,role = role).first()
            if notification:
                notification.is_read = True
                notification.save()
                return JsonResponse({'success': True})
    else:
        notification = Notification.objects.filter(user=request.user, notification_type='notification',role = role)
        updated_count = notification.update(is_read=True)
        print("updated_count",updated_count)
        if updated_count > 0:
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False}, status=404)
    return JsonResponse({'success': False}, status=400)
