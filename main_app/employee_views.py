import json
from datetime import datetime
from django.contrib import messages
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, redirect, get_object_or_404,reverse
from django.utils import timezone
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from calendar import monthrange

from main_app.notification_badge import mark_notification_read, send_notification
from .forms import *
from .models import *
from django.db.models import Sum, F, DurationField, ExpressionWrapper
from django.db.models.functions import Coalesce
from datetime import timedelta
from asset_app.models import Notify_Manager,AssetIssue


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
    # print("recordsaaaaa",records)
    # Handle date range filtering
    start_date_str = request.GET.get('start_date')
    print("start_date_str",start_date_str)
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
    # print("recordsbbbbbbb",records)
    # Additional filters
    if department_filter:
        records = records.filter(department_id=department_filter)
    if status_filter:
        records = records.filter(status=status_filter)
    # print("recordsccccc",records)
    # Create detailed time entries (clock in/out and breaks)
    detailed_time_entries = []
    for record in records.order_by('date', 'clock_in'):
        # Add clock in entry
        detailed_time_entries.append({
            'type': 'clock_in',
            'date': record.date,
            'time': record.clock_in,
            'record': record,
            'status': 'Clocked In' if not record.clock_out else 'Clocked Out'
        })
        
        # Add all break entries for this record
        breaks = record.breaks.all().order_by('break_start')
        for brk in breaks:
            detailed_time_entries.append({
                'type': 'break',
                'date': record.date,
                'time': brk.break_start,
                'end_time': brk.break_end,
                'duration': brk.duration,
                'record': record,
                'status': 'Break Start' if not brk.break_end else 'Break End'
            })
        
        # Add clock out entry if exists
        if record.clock_out:
            detailed_time_entries.append({
                'type': 'clock_out',
                'date': record.date,
                'time': record.clock_out,
                'record': record,
                'status': 'Clocked Out'
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

    # Calculate working days in month (excluding weekends and holidays)
    days_in_month = monthrange(current_year, current_month)[1]
    total_working_days = 0
    weekend_days_list = []

    month_record = AttendanceRecord.objects.filter(
        user_id=request.user,  
        date__range=(start_date, end_date)
    )
    print("month_record",month_record)
    record_dict = {rec.date: rec.status for rec in month_record}
    absent_days = 0
    current_date = start_date
    print("START DATE",start_date)
    while current_date <= today:
        print("CURREBNT DATE",current_date)
        weekday = current_date.weekday()
        is_sunday = weekday == 6
        is_saturday = weekday == 5
        is_1st_or_3rd_saturday = is_saturday and ((current_date.day - 1) // 7) in [1, 3]
        if not is_sunday and not is_1st_or_3rd_saturday:
            status = record_dict.get(current_date)
            if not status:
                absent_days+=1
            elif status == "half":
                print("status",status)
                absent_days += 0.5
            else:
                leave_records = LeaveReportEmployee.objects.filter(
                    employee=employee,
                    status=1,  # Approved
                    leave_type = "Half-Day",
                    start_date=current_date  # The specific date you're checking
                )
                # leave_count = LeaveReportEmployee.objects.filter(employee = employee)
                print("leaveeeeeeeeeee)***************",leave_records)
                if leave_records:
                    absent_days+=0.5
        current_date += timedelta(days=1)
    print("absent_days",absent_days)
    print("days_in_month",days_in_month)
    for day in range(1, days_in_month + 1):
        date = timezone.datetime(current_year, current_month, day).date()
        weekday = date.weekday()
        is_sunday = weekday == 6
        is_saturday = weekday == 5
        is_1st_or_3rd_saturday = is_saturday and ((day - 1) // 7) in [0, 2]
        if is_1st_or_3rd_saturday or is_sunday:
            weekend_days_list.append(str(date))
        if not is_sunday and not is_1st_or_3rd_saturday:
            total_working_days += 1
        

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
    print("todaytoday",today.day, start_date.day)
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
            'total_breaks_today': total_breaks_in_month
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
    form = LeaveReportEmployeeForm(request.POST or None)
    employee = get_object_or_404(Employee, admin_id=request.user.id)
    print(">>>>>>>>>>>>>>>>>>>>request.user.id",request.user.id,employee.team_lead,employee.team_lead.admin.id)
    unread_ids = list(
            Notification.objects.filter(
                user=request.user,
                is_read=False,
                notification_type='leave'
            ).values_list('leave_or_notification_id', flat=True) 
        )
    context = {
        'form': form,
        'leave_history': LeaveReportEmployee.objects.filter(employee=employee).order_by('-created_at'),
        'page_title': 'Apply for leave',
        'unread_ids': unread_ids
    }
    if request.method == 'POST':
        if form.is_valid():
            try:
                obj = form.save(commit=False)
                obj.employee = employee
                obj.save()
                messages.success(
                    request, "Application for leave has been submitted for review")
                user = CustomUser.objects.get(id = employee.team_lead.admin.id)
                send_notification(user, "Leave Appplied from ","notification",obj.id,"manager")
                return redirect(reverse('employee_apply_leave'))
            except Exception:
                messages.error(request, "Could not submit")
        else:
            messages.error(request, "Form has errors!")

    return render(request, "employee_template/employee_apply_leave.html", context)


def employee_feedback(request):
    form = FeedbackEmployeeForm(request.POST or None)
    employee = get_object_or_404(Employee, admin_id=request.user.id)
    context = {
        'form': form,
        'feedbacks': FeedbackEmployee.objects.filter(employee=employee),
        'page_title': 'Employee Feedback'

    }
    if request.method == 'POST':
        if form.is_valid():
            try:
                obj = form.save(commit=False)
                obj.employee = employee
                obj.save()
                messages.success(
                    request, "Feedback submitted for review")
                user = CustomUser.objects.get(id = employee.team_lead.admin.id)
                print("****************", employee.admin.id, employee.team_lead.admin.id,employee.team_lead.admin)
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
            ).order_by('date', 'clock_in')
        
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
                    # Update first clock-in if earlier
                    if record.clock_in and (day['first_clock_in'] is None or record.clock_in < day['first_clock_in']):
                        day['first_clock_in'] = record.clock_in
                    # Update last clock-out if later
                    if record.clock_out and (day['last_clock_out'] is None or record.clock_out > day['last_clock_out']):
                        day['last_clock_out'] = record.clock_out
                    # Update status (prioritize 'late' over 'present')
                    if record.status == 'late':
                        day['status'] = 'late'
                    # Sum total worked time
                    if record.total_worked:
                        day['total_worked'] += record.total_worked
                    day['records_count'] += 1
            
            # Convert to list and format for response
            json_data = []
            for date_str, day in sorted(daily_summaries.items(), reverse=True):
                # Calculate net worked time (subtract breaks if needed)
                # Note: You might need to add break time calculation logic here
                net_worked = day['total_worked']
                
                json_data.append({
                    "date": date_str,
                    "status": day['status'],
                    "clock_in": day['first_clock_in'].strftime('%H:%M:%S') if day['first_clock_in'] else '--',
                    "clock_out": day['last_clock_out'].strftime('%H:%M:%S') if day['last_clock_out'] else '--',
                    "total_worked": str(net_worked),
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
    try:
        print("HIIII")
        employee = get_object_or_404(Employee, admin=request.user)
        print("employee",employee)
        notifications = NotificationEmployee.objects.filter(employee=employee).order_by('-id')
        print("notifications",notifications)
        context = {
            'notifications': notifications,
            'page_title': "View Notifications"
        }
        # print("HIIIII")
        mark_notification_read(request, 0,"notification","employee")
    except Exception as e:
        print("ERRROR",str(e))
    return render(request, "employee_template/employee_view_notification.html", context)



def employee_requests(request):
    try:
        employee = Employee.objects.get(admin=request.user)
    except Employee.DoesNotExist:
        messages.error(request, "Employee not found.")
    
    leave_requests = LeaveReportEmployee.objects.filter(employee=employee).order_by('-created_at')
    asset_claims = Notify_Manager.objects.filter(employee=request.user).order_by('-timestamp')
    asset_issues = AssetIssue.objects.filter(reported_by=request.user).order_by("reported_date")
    context = {
        'leave_requests': leave_requests,
        'asset_claims': asset_claims,
        'asset_issues': asset_issues,
        'page_title': 'My Requests'
    }

    return render(request, 'employee_template/employee_requests.html',context)