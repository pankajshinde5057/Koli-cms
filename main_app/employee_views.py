import json
from datetime import datetime
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, redirect, get_object_or_404,reverse
from django.utils import timezone
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from calendar import monthrange
from asset_app.models import Notify_Manager,LOCATION_CHOICES
from main_app.notification_badge import mark_notification_read, send_notification
from .forms import *
from .models import *
from django.db.models import Sum, F, DurationField, ExpressionWrapper
from django.db.models.functions import Coalesce
from datetime import timedelta
from asset_app.models import Notify_Manager,AssetIssue
from django.utils.timezone import localtime, make_aware
from datetime import timedelta, datetime, time
from django.core.paginator import Paginator
from datetime import date
from django.template.loader import render_to_string


def employee_home(request):
    today = timezone.now().date()
    employee = get_object_or_404(Employee, admin=request.user)
    date_filter = request.GET.get('date', "today")
    department_filter = request.GET.get('department')
    status_filter = request.GET.get('status')

    current_month = today.month
    current_year = today.year
    start_date = today.replace(day=1)

    # Add a month, then subtract days until we get back to the last day of the current month
    if today.month == 12:
        next_month = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_month = today.replace(month=today.month + 1, day=1)

    end_date = next_month - timedelta(days=1)
    # Base query for attendance records
    records = AttendanceRecord.objects.filter(user=request.user).select_related('department')
    # Handle date range filtering
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    if start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            records = records.filter(date__range=(start_date, end_date))
        except ValueError:
            messages.warning(request, "Invalid date range format. Please use YYYY-MM-DD.")
    else:
        records = records.filter(date__month=current_month, date__year=current_year)

        # if date_filter == 'today':
        #     records = records.filter(date=today)
        # elif date_filter == 'week':
        #     start_date = today - timedelta(days=today.weekday())
        #     end_date = start_date + timedelta(days=6)
        #     records = records.filter(date__range=[start_date, end_date])
    # Additional filters
    if department_filter:
        records = records.filter(department_id=department_filter)
    if status_filter:
        records = records.filter(status=status_filter)
    # Create detailed time entries (clock in/out and breaks)
    detailed_time_entries = []
    for record in records.order_by('date', 'clock_in'):
        # Add clock in entry
        detailed_time_entries.append({
            'type': 'clock_in',
            'date': record.date,
            'start_time': record.clock_in,  
            'end_time': record.clock_out if record.clock_out else None,
            'time': record.clock_in,
            'record': record,
            'status': 'Clocked In' if not record.clock_out else 'Clocked Out',
            'duration': record.clock_out - record.clock_in if record.clock_out else None
        })
        
        # Add all break entries for this record
        breaks = record.breaks.all().order_by('break_start')
        for brk in breaks:
            detailed_time_entries.append({
                'type': 'break',
                'date': record.date,
                'start_time': brk.break_start,  
                'end_time': brk.break_end,     
                'time': brk.break_start,        
                'duration': brk.duration,
                'record': record,
                'status': 'Break End' if brk.break_end else 'Break Start'
            })
        
        # Add clock out entry if exists
        if record.clock_out:
            detailed_time_entries.append({
                'type': 'clock_out',
                'date': record.date,
                'start_time': record.clock_in,   
                'end_time': record.clock_out,     
                'time': record.clock_out,         
                'record': record,
                'status': 'Clocked Out',
                'duration': record.clock_out - record.clock_in
            })
    
    detailed_time_entries.sort(key=lambda x: (x['date'], x['time']), reverse=True)

    paginator = Paginator(detailed_time_entries, 10)
    page = request.GET.get('page', 1)

    try:
        paginated_entries = paginator.page(page)
    except PageNotAnInteger:
        paginated_entries = paginator.page(1)
    except EmptyPage:
        paginated_entries = paginator.page(paginator.num_pages)

    # Daily view with aggregated data
    daily_view = records.annotate(
        total_break_time=Coalesce(
            Sum('breaks__duration', output_field=DurationField()),
            timedelta()
        )
    ).annotate(
        net_worked_time=ExpressionWrapper(
            F('total_worked') - F('total_break_time'),
            output_field=DurationField()
        )
    ).order_by('-date')

    # Weekly and monthly summaries
    completed_records = records.filter(clock_out__isnull=False).annotate(
        total_break_time=Coalesce(
            Sum('breaks__duration', output_field=DurationField()),
            timedelta()
        )
    )

    # Weekly data calculation
    weekly_data = {}
    for record in completed_records:
        week = record.date.isocalendar()[1]
        if week not in weekly_data:
            weekly_data[week] = {
                'total_hours': timedelta(),
                'regular_hours': timedelta(),
                'overtime_hours': timedelta(),
                'week_start': record.date - timedelta(days=record.date.weekday())
            }

        net_worked = record.total_worked - record.total_break_time
        weekly_data[week]['total_hours'] += net_worked
        weekly_data[week]['regular_hours'] += record.regular_hours
        weekly_data[week]['overtime_hours'] += record.overtime_hours

    weekly_view = [{
        'week': data['week_start'],
        'total_hours': data['total_hours'],
        'regular_hours': data['regular_hours'],
        'overtime_hours': data['overtime_hours']
    } for week, data in sorted(weekly_data.items(), reverse=True)]

    # Monthly data calculation
    monthly_data = {}
    for record in completed_records:
        month_start_date = record.date.replace(day=1)
        if month_start_date not in monthly_data:
            monthly_data[month_start_date] = {
                'total_hours': timedelta(),
                'regular_hours': timedelta(),
                'overtime_hours': timedelta(),
                'present_days': 0,
                'late_days': 0,
                'half_days': 0
            }

        net_worked = record.total_worked - record.total_break_time
        monthly_data[month_start_date]['total_hours'] += net_worked
        monthly_data[month_start_date]['regular_hours'] += record.regular_hours
        monthly_data[month_start_date]['overtime_hours'] += record.overtime_hours

        if record.status == 'present':
            monthly_data[month_start_date]['present_days'] += 1
        elif record.status == 'late':
            monthly_data[month_start_date]['late_days'] += 1
        elif record.status == 'half_day':
            monthly_data[month_start_date]['half_days'] += 1

    monthly_view = [{
        'month': month,
        'total_hours': data['total_hours'],
        'regular_hours': data['regular_hours'],
        'overtime_hours': data['overtime_hours'],
        'present_days': data['present_days'],
        'late_days': data['late_days'],
        'half_days': data['half_days']
    } for month, data in sorted(monthly_data.items(), reverse=True)]

    # Current session status
    current_record = AttendanceRecord.objects.filter(
        user=request.user,
        clock_out__isnull=True,
        date=today
    ).first()

    current_break = None
    if current_record:
        current_break = Break.objects.filter(
            attendance_record=current_record,
            break_end__isnull=True
        ).first()

    # Attendance statistics
    total_breaks_in_month = Break.objects.filter(
        attendance_record__date__month=current_month,
        attendance_record__date__year=current_year,
        attendance_record__user=request.user
    ).count()

    # Breaks taken today
    todays_breaks = Break.objects.filter(
        attendance_record__date=today,
        attendance_record__user=request.user
    ).count()

    # Get holidays for the current month
    holidays = Holiday.objects.filter(
        date__month=current_month,
        date__year=current_year
    ).values_list('date', flat=True)

    # Calculate working days in month (excluding weekends, holidays, and 1st/3rd Saturdays)
    days_in_month = monthrange(current_year, current_month)[1]
    total_working_days = 0
    weekend_days_list = []

    month_record = AttendanceRecord.objects.filter(
        user_id=request.user,  
        date__range=(start_date, end_date)
    )
    record_dict = {rec.date: rec.status for rec in month_record}
    absent_days = 0
    current_date = start_date
    while current_date <= today:
        weekday = current_date.weekday()
        is_sunday = weekday == 6
        is_saturday = weekday == 5
        is_1st_or_3rd_saturday = is_saturday and ((current_date.day - 1) // 7) in [0, 2]  # 0 and 2 for 1st and 3rd weeks
        
        # Check if it's a working day (not sunday, not 1st/3rd saturday, not holiday)
        is_working_day = not is_sunday and not is_1st_or_3rd_saturday and current_date not in holidays
        
        if is_working_day:
            status = record_dict.get(current_date)
            if not status:
                absent_days += 1
            elif status == "half":
                absent_days += 0.5
            else:
                leave_records = LeaveReportEmployee.objects.filter(
                    employee=employee,
                    status=1,  # Approved
                    leave_type="Half-Day",
                    start_date=current_date  # The specific date you're checking
                )
                if leave_records:
                    absent_days += 0.5
        current_date += timedelta(days=1)

    # Calculate total working days for the month (excluding weekends and holidays)
    for day in range(1, days_in_month + 1):
        date = timezone.datetime(current_year, current_month, day).date()
        weekday = date.weekday()
        is_sunday = weekday == 6
        is_saturday = weekday == 5
        is_1st_or_3rd_saturday = is_saturday and ((day - 1) // 7) in [0, 2]
        
        # Count as working day if not sunday, not 1st/3rd saturday, and not holiday
        if not is_sunday and not is_1st_or_3rd_saturday and date not in holidays:
            total_working_days += 1
        
        if is_1st_or_3rd_saturday or is_sunday or date in holidays:
            weekend_days_list.append(str(date))

    # Get distinct dates with attendance records
    attended_dates = records.values_list('date', flat=True).distinct()
    # Count present and late days (counting each date only once)
    present_dates = records.filter(
        status='present'
    ).values_list('date', flat=True).distinct().count()

    late_dates = records.filter(
        status='late'
    ).values_list('date', flat=True).distinct().count()
    # Total present days (including late days as present)
    present_days = present_dates + late_dates

    # Get approved leaves for the current month
    approved_leaves = LeaveReportEmployee.objects.filter(
        employee=employee,
        status=1,  # Approved leaves
        start_date__month=current_month,
        start_date__year=current_year
    )
    
    # Count half days and full day leaves
    half_days = approved_leaves.filter(leave_type='Half-Day').count()
     # absent_days = approved_leaves.filter(leave_type='Full-Day').count()
    # Calculate attendance percentage
    if total_working_days > 0:
        # Count half days as 0.5 present days
        effective_present_days = present_days + (half_days * 0.5)
        attendance_percentage = (effective_present_days / total_working_days) * 100
    else:
        attendance_percentage = 0

    attendance_percentage = round(attendance_percentage, 1)

    # Recent activity
    recent_activities = ActivityFeed.objects.filter(
        user=request.user
    ).order_by('-timestamp').first()

    LATE_LOGIN_TIME = timezone.datetime.strptime('09:30:00', '%H:%M:%S').time()
    HALF_DAY_TIME = timezone.datetime.strptime('13:00:00', '%H:%M:%S').time()
    today_records = AttendanceRecord.objects.filter(
        user=request.user,
        date=today
    ).order_by('clock_in')

    today_total_worked = timedelta()
    today_status = None
    today_late = False
    today_half_day = False

    if today_records.exists():
        today_record = today_records.first()  # Get the main record for today
        
        # Automatically set status based on clock-in time
        if today_record.clock_in.time() >= HALF_DAY_TIME:
            today_record.status = 'half_day'
            today_record.save()
            today_half_day = True
        elif today_record.clock_in.time() >= LATE_LOGIN_TIME:
            today_record.status = 'late'
            today_record.save()
            today_late = True
        else:
            today_record.status = 'present'
            today_record.save()
        
        today_status = today_record.status
        
        # Calculate late minutes if late
        if today_late:
            late_time = datetime.combine(today, today_record.clock_in.time()) - datetime.combine(today, LATE_LOGIN_TIME)
            today_record.late_minutes = late_time.seconds // 60
            today_record.save()
        
        # Get first clock-in of the day
        first_clock_in = today_record.clock_in
        
        # Get last clock-out of the day (if exists)
        last_clock_out_record = today_records.filter(clock_out__isnull=False).last()
        last_clock_out = last_clock_out_record.clock_out if last_clock_out_record else None
        
        if first_clock_in and last_clock_out:
            # Calculate total worked time
            today_total_worked = last_clock_out - first_clock_in
            
            # Subtract total break time
            total_break_time = sum(
                (brk.duration for record in today_records 
                for brk in record.breaks.all() if brk.duration),
                timedelta()
            )
            today_total_worked -= total_break_time

    today_status = None
    today_late = False
    today_half_day = False

    if today_records.exists():
        today_record = today_records.first()  # Get the main record for today
        today_status = today_record.status
        
        if today_status == 'late':
            today_late = True
        elif today_status == 'half_day':
            today_half_day = True

    context = {
        'page_title': 'Employee Dashboard',
        'employee': employee,
        'today_total_worked': today_total_worked,
        'today_status': today_status,
        'today_late': today_late,
        'today_half_day': today_half_day,
        'current_record': current_record,
        'current_break': current_break,
        'recent_activities': recent_activities,
        'attendance_stats': {
            'total_days': total_working_days,
            'present_days': present_days,
            'late_days': late_dates,
            'half_days': half_days,
            'absent_days': absent_days,
            'attendance_percentage': attendance_percentage,
            'total_breaks_in_month': total_breaks_in_month,
            'todays_total_breaks' : todays_breaks,
        },
        'detailed_time_entries': paginated_entries,
        'daily_view': daily_view,
        'weekly_view': weekly_view,
        'monthly_view': monthly_view,
        'current_filters': {
            'date': date_filter,
            'department': department_filter,
            'status': status_filter,
            'month': str(current_month),
            'year': str(current_year),
        },
        'status_choices': AttendanceRecord.STATUS_CHOICES,
    }

    return render(request, 'employee_template/home_content.html', context)

def employee_apply_leave(request):
    employee = get_object_or_404(Employee, admin_id=request.user.id)
    unread_ids = Notification.objects.filter(
        user=request.user,
        role="employee",
        is_read=False,
        notification_type="leave"
    ).values_list('leave_or_notification_id', flat=True)

    leave_list = LeaveReportEmployee.objects.filter(employee=employee).order_by('-created_at')
    paginator = Paginator(leave_list, 5)  # Show 5 leave records per page

    page_number = request.GET.get('page')
    leave_page = paginator.get_page(page_number)

    if request.method == 'POST':
        leave_type_ = request.POST.get('leave_type')
        half_day_type_ = request.POST.get('half_day_type')
        start_date_ = request.POST.get('start_date')
        end_date_ = request.POST.get('end_date')
        message_ = request.POST.get('message')

        if not all([leave_type_, start_date_, message_]):
            messages.error(request, "All fields are required")
            return redirect(reverse('employee_apply_leave'))

        existing_leaves = LeaveReportEmployee.objects.filter(
            employee=employee,
            start_date__lte=end_date_ if end_date_ else start_date_,
            end_date__gte=start_date_,
            status__in=[0, 1]
        ).exists()

        if existing_leaves:
            messages.error(request, "You already applied or have approved leave for these dates.")
            return redirect(reverse('employee_apply_leave'))

        try:
            start_date = date.fromisoformat(start_date_)
            end_date = date.fromisoformat(end_date_ if end_date_ else start_date_)
            if end_date < start_date:
                messages.error(request, "End date cannot be before start date.")
                return redirect(reverse('employee_apply_leave'))
        except ValueError:
            messages.error(request, "Invalid date format.")
            return redirect(reverse('employee_apply_leave'))

        try:
            obj = LeaveReportEmployee.objects.create(
                employee=employee,
                leave_type=leave_type_,
                half_day_type=half_day_type_ if half_day_type_ else None,
                start_date=start_date_,
                end_date=end_date_ if end_date_ else start_date_,
                message=message_
            )
            messages.success(request, "Your leave request has been submitted.")
            user = CustomUser.objects.get(id=employee.team_lead.admin.id)
            send_notification(user, "Leave Applied", "notification", obj.id, "manager")
            return redirect(reverse('employee_apply_leave'))
        except Exception as e:
            messages.error(request, f"Error submitting leave: {str(e)}")
            return redirect(reverse('employee_apply_leave'))

    context = {
        'leave_page': leave_page,
        'unread_ids': list(unread_ids),
        'page_title': 'Apply for Leave',
    }
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # Just render part of the existing template using a specific block
        html = render_to_string("employee_template/employee_apply_leave.html", context, request=request)
        # Extract only the inner HTML of #leave-history-container
        # (We'll handle this in JS by selecting it from the rendered template)
        return HttpResponse(html)

    return render(request, "employee_template/employee_apply_leave.html", context)



def employee_feedback(request):
    form = FeedbackEmployeeForm(request.POST or None)
    employee = get_object_or_404(Employee, admin_id=request.user.id)
    feedbacks_list = FeedbackEmployee.objects.filter(employee=employee).order_by('-created_at')
    paginator = Paginator(feedbacks_list, 5)  # 5 items per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context = {
        'form': form,
        'page_obj': page_obj, 
        'feedbacks': FeedbackEmployee.objects.filter(employee=employee),
        'page_title': 'Employee Feedback'

    }
    mark_notification_read(request, 0,"feedback","employee")
    if request.method == 'POST':
        if form.is_valid():
            try:
                obj = form.save(commit=False)
                obj.employee = employee
                obj.save()
                messages.success(
                    request, "Feedback submitted for review")
                user = CustomUser.objects.get(id = employee.team_lead.admin.id)
                send_notification(user, f"Feedback submitted for review for {obj.id}","employee feedback",obj.id,"admin")
                return redirect(reverse('employee_feedback'))
            except Exception:
                messages.error(request, "Could not Submit!")
        else:
            messages.error(request, "Form has errors!")
    return render(request, "employee_template/employee_feedback.html", context)


def employee_view_profile(request):
    employee = get_object_or_404(Employee, admin=request.user)
    context = {'employee': employee,
               'page_title': 'Profile'
               }
    return render(request, "employee_template/employee_view_profile.html", context)


@csrf_exempt
def employee_fcmtoken(request):
    token = request.POST.get('token')
    employee_user = get_object_or_404(CustomUser, id=request.user.id)
    try:
        employee_user.fcm_token = token
        employee_user.save()
        return HttpResponse("True")
    except Exception as e:
        return HttpResponse("False")

@csrf_exempt
def employee_view_attendance(request):
    employee = get_object_or_404(Employee, admin=request.user)
    
    if request.method == 'GET':
        division = get_object_or_404(Division, id=employee.division.id)
        context = {
            'departments': Department.objects.filter(division=division),
            'page_title': 'View Attendance',
            'default_start': (timezone.now() - timedelta(days=7)).strftime('%Y-%m-%d'),
            'default_end': timezone.now().strftime('%Y-%m-%d')
        }
        return render(request, 'employee_template/employee_view_attendance.html', context)

    elif request.method == 'POST':
        try:
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            
            if not all([start_date, end_date]):
                return JsonResponse({'error': 'Missing required parameters'}, status=400)
            
            if start_date > end_date:
                return JsonResponse({'error': 'Start date cannot be after end date'}, status=400)
            
            all_records = AttendanceRecord.objects.filter(
                user=request.user,
                date__range=(start_date, end_date)
            ).exclude(clock_in=None).exclude(clock_out=None).order_by('date', 'clock_in')
        
            daily_summaries = {}
            for record in all_records:
                date_str = record.date.strftime('%Y-%m-%d')
                
                if date_str not in daily_summaries:
                    daily_summaries[date_str] = {
                        'date': date_str,
                        'first_clock_in': record.clock_in,
                        'last_clock_out': record.clock_out,
                        'status': record.status,
                        'total_worked': record.total_worked or timedelta(),
                        'records_count': 1
                    }
                else:
                    day = daily_summaries[date_str]

                    if record.clock_in and record.clock_in < day['first_clock_in']:
                        day['first_clock_in'] = record.clock_in

                    if record.clock_out and record.clock_out > day['last_clock_out']:
                        day['last_clock_out'] = record.clock_out

                    if record.status == 'late':
                        day['status'] = 'late'

                    if record.total_worked:
                        day['total_worked'] += record.total_worked

                    day['records_count'] += 1
            
            json_data = []
            for date_str, day in sorted(daily_summaries.items(), reverse=True):
                # Define lunch break period
                lunch_start = make_aware(datetime.combine(datetime.strptime(date_str, '%Y-%m-%d'), time(13, 0)))
                lunch_end = make_aware(datetime.combine(datetime.strptime(date_str, '%Y-%m-%d'), time(13, 40)))

                # Subtract lunch time if work period spans it
                if day['first_clock_in'] <= lunch_start and day['last_clock_out'] >= lunch_end:
                    day['total_worked'] -= timedelta(minutes=40)

                json_data.append({
                    "date": date_str,
                    "status": day['status'],
                    "clock_in": localtime(day['first_clock_in']).strftime('%I:%M %p') if day['first_clock_in'] else '--',
                    "clock_out": localtime(day['last_clock_out']).strftime('%I:%M %p') if day['last_clock_out'] else '--',
                    "total_worked": str(day['total_worked']),
                    "records_count": day['records_count']
                })

            return JsonResponse({'data': json_data}, safe=False)

        except ValueError as e:
            return JsonResponse({'error': f'Invalid date format: {str(e)}'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

        

def employee_view_salary(request):
    employee = get_object_or_404(Employee, admin=request.user)
    salarys = EmployeeSalary.objects.filter(employee=employee)
    context = {
        'salarys': salarys,
        'page_title': "View Salary"
    }
    return render(request, "employee_template/employee_view_salary.html", context)


def employee_view_notification(request):
    employee = get_object_or_404(Employee, admin=request.user)
    all_notifications = NotificationEmployee.objects.filter(
        employee=employee
    ).order_by('-created_at')
    notification_from_admin = all_notifications.filter(
        created_by__is_superuser=True
    )
    
    notification_from_manager = all_notifications.filter(
        created_by__is_superuser=False
    )
    
    notification_ids = Notification.objects.filter(
        user=request.user,
        is_read=False,
    ).values_list('leave_or_notification_id', flat=True)
    unread_ids = list(notification_ids)
    admin_paginator = Paginator(notification_from_admin, 10)
    admin_page_number = request.GET.get('notification_page')
    notification_from_admin_obj = admin_paginator.get_page(admin_page_number)
    manager_paginator = Paginator(notification_from_manager, 10)
    manager_page_number = request.GET.get('manager_page')
    notification_from_manager_obj = manager_paginator.get_page(manager_page_number)
    
    context = {
        'notification_from_admin_obj': notification_from_admin_obj,
        'notification_from_manager_obj': notification_from_manager_obj,
        'total_notifications': notification_from_admin.count(),
        'total_manager_notifications': notification_from_manager.count(),
        'page_title': "View Notifications",
        'manager_unread_ids': unread_ids,
        'LOCATION_CHOICES': LOCATION_CHOICES,
    }

    return render(request, "employee_template/employee_view_notification.html", context)


def employee_requests(request):
    try:
        employee = Employee.objects.get(admin=request.user)
    except Employee.DoesNotExist:
        messages.error(request, "Employee not found.")
        employee = None

    # Leave Requests Pagination
    leave_requests = LeaveReportEmployee.objects.filter(employee=employee).order_by('-created_at')
    leave_paginator = Paginator(leave_requests, 5)  
    leave_page_number = request.GET.get('leave_page')
    leave_requests_page = leave_paginator.get_page(leave_page_number)

    # Asset Claims Pagination
    asset_claims = Notify_Manager.objects.filter(employee=request.user).order_by('-timestamp')
    asset_paginator = Paginator(asset_claims, 5) 
    asset_page_number = request.GET.get('asset_page')
    asset_claims_page = asset_paginator.get_page(asset_page_number)

    # Asset Issues Pagination
    asset_issues = AssetIssue.objects.filter(reported_by=request.user).order_by('reported_date')
    issue_paginator = Paginator(asset_issues, 5)  
    issue_page_number = request.GET.get('issue_page')
    asset_issues_page = issue_paginator.get_page(issue_page_number)

    context = {
        'leave_requests': leave_requests_page,
        'asset_claims': asset_claims_page,
        'asset_issues': asset_issues_page,
        'page_title': 'My Requests'
    }

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # Render the entire template but client-side JS will extract relevant parts
        html = render_to_string('employee_template/employee_requests.html', context, request=request)
        return HttpResponse(html)

    return render(request, 'employee_template/employee_requests.html', context)