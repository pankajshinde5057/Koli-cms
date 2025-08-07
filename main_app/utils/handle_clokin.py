from main_app.models import *
from django.http import JsonResponse
from django.shortcuts import get_object_or_404

def handle_clock_in(request,user_,now,today):
    # Check if already clocked in
    existing_record = AttendanceRecord.objects.filter(
        user_id=user_.id,
        date=today,
        clock_out__isnull=False
    ).first()

    if existing_record:
        return JsonResponse({
            'status': 'error',
            'message': 'You are already clocked in for today.'
        }, status=400)
    
    # Check leave status
    leave = LeaveReportEmployee.objects.filter(
        employee__admin=user_,
        start_date__lte=today,
        end_date__gte=today,
        status=1
    ).first()

    leave_manager = LeaveReportManager.objects.filter(
        manager__admin=user_,
        start_date__lte=today,
        end_date__gte=today,
        status=1
    ).first()

    if leave:
        if leave.leave_type == 'Full-Day':
            return JsonResponse({
                'status': 'error',
                'message': 'Cannot clock in on an approved leave day.'
            }, status=400)
        
        # For half-day leave
        current_time = now.time()
        # For first half leave, allow clock-in only after 1:00 pm
        if leave.half_day_type and current_time < time(13, 0):
            return JsonResponse({
                'status': 'error',
                'message': 'For First Half leave, you can only clock in after 1:00 PM.'
            }, status=400)

        # For Second Half leave, allow clock-in only before 1:00 PM
        if leave.leave_type and current_time >= time(13, 0):
            return JsonResponse({
                'status': 'error',
                'message': 'For Second Half leave, you must clock in before 1:00 PM.'
            }, status=400)
        
    if leave_manager:
        if leave_manager.leave_type == 'Full-Day':
            return JsonResponse({
                'status': 'error',
                'message': 'Cannot clock in on an approved leave day.'
            }, status=400)
        
    # Determine attendance status
    if not user_.is_second_shift:    
        # Logic for non-second shift users
        on_time_threshold = datetime.combine(today, time(9, 0))
        late_threshold = datetime.combine(today, time(9, 30))
        half_day_threshold = datetime.combine(today, time(13, 0))

        earliest_clock_in = datetime.combine(today, time(8, 45)) if user_.user_type == "3" else datetime.combine(today, time(8, 30))

        if now < earliest_clock_in:
            return JsonResponse({
                'status': 'error',
                'message': f"Clock-in is not allowed before {'8:45 AM' if user_.user_type == '3' else '8:30 AM'} IST."
            }, status=400)

        status = 'present'
        if now > half_day_threshold or leave:
            status = 'half_day'
        elif now > late_threshold:
            status = 'late'
    
    else:
        # Logic for second shift users
        status = 'present'  # Default status for second shift users
        if leave_manager and leave_manager.leave_type == 'Half-Day':
            status = 'half_day'

    # Create record only on successful validation
    department_id = request.POST.get('department')
    department = Department.objects.get(id=department_id) if department_id else None
    
    employee_ = Employee.objects.filter(admin=user_).first()
    current_user = employee_ if employee_ else Manager.objects.filter(admin=user_).first()

    new_record = AttendanceRecord.objects.create(
        user=user_,
        date=today,
        clock_in=now,
        department=current_user.department,
        status=status,
        ip_address=request.META.get('REMOTE_ADDR'),
        notes=request.POST.get('notes', '')
    )
    new_record.full_clean()
    new_record.save()

    ActivityFeed.objects.create(
        user=user_,
        activity_type='clock_in',
        related_record=new_record
    )

    return JsonResponse({
        'status': 'success',
        'message': 'Successfully clocked in!'
    })

