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

# import openpyxl.workbook
from asset_app.models import Notify_Manager,LOCATION_CHOICES
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
from django.contrib.auth.decorators import login_required
import openpyxl
from openpyxl.styles import Font, Alignment
from io import BytesIO

def get_ist_date():
    return timezone.now().astimezone(pytz.timezone('Asia/Kolkata')).date()
from django.db.models import Q


@login_required   
def employee_home(request):
    today = timezone.now().date()
    employee = get_object_or_404(Employee, admin=request.user)
    date_filter = request.GET.get('date', "today")
    department_filter = request.GET.get('department')
    status_filter = request.GET.get('status')

    current_month = today.month
    current_year = today.year
    start_date = today.replace(day=1)

    if today.month == 12:
        next_month = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_month = today.replace(month=today.month + 1, day=1)

    end_date = next_month - timedelta(days=1)
    records = AttendanceRecord.objects.filter(user=request.user).select_related('department')
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

    detailed_time_entries = []
    for record in records.order_by('date', 'clock_in'):
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

    completed_records = records.filter(clock_out__isnull=False).annotate(
        total_break_time=Coalesce(
            Sum('breaks__duration', output_field=DurationField()),
            timedelta()
        )
    )

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

    # Monthly data calculation with half_day counted as present and late
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
            monthly_data[month_start_date]['present_days'] += 1
            monthly_data[month_start_date]['late_days'] += 1
        elif record.status == 'half_day':
            monthly_data[month_start_date]['present_days'] += 1  # Count as present
            monthly_data[month_start_date]['late_days'] += 1    # Count as late
            monthly_data[month_start_date]['half_days'] += 0.5    # Count as half day

    monthly_view = [{
        'month': month,
        'total_hours': data['total_hours'],
        'regular_hours': data['regular_hours'],
        'overtime_hours': data['overtime_hours'],
        'present_days': data['present_days'],
        'late_days': data['late_days'],
        'half_days': data['half_days']
    } for month, data in sorted(monthly_data.items(), reverse=True)]

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

    total_breaks_in_month = Break.objects.filter(
        attendance_record__date__month=current_month,
        attendance_record__date__year=current_year,
        attendance_record__user=request.user
    ).count()

    todays_breaks = Break.objects.filter(
        attendance_record__date=today,
        attendance_record__user=request.user
    ).count()

    holidays = Holiday.objects.filter(
        date__month=current_month,
        date__year=current_year
    ).values_list('date', flat=True)

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
        is_1st_or_3rd_saturday = is_saturday and ((current_date.day - 1) // 7) in [1, 3]
        
        is_working_day = not is_sunday and not is_1st_or_3rd_saturday and current_date not in holidays
        
        if is_working_day:
            record_exists = AttendanceRecord.objects.filter(
                user=request.user,
                date=current_date
            ).exists()
            
            leave_exists = LeaveReportEmployee.objects.filter(
                employee=employee,
                status=1,
                start_date__lte=current_date,
                end_date__gte=current_date
            ).exists()
            
            if not record_exists and not leave_exists:
                absent_days += 1
            elif (LeaveReportEmployee.objects.filter(
                    employee=employee,
                    status=1,
                    leave_type="Half-Day",
                    start_date__lte=current_date,
                    end_date__gte=current_date
                ).exists() or 
                AttendanceRecord.objects.filter(
                    user=request.user,
                    date=current_date,
                    status="half_day"
                ).exists()):
                absent_days += 0.5
        
        current_date += timedelta(days=1)

    for day in range(1, days_in_month + 1):
        date = timezone.datetime(current_year, current_month, day).date()
        weekday = date.weekday()
        is_sunday = weekday == 6
        is_saturday = weekday == 5
        is_1st_or_3rd_saturday = is_saturday and ((day - 1) // 7) in [1, 3]
        
        if not is_sunday and not is_1st_or_3rd_saturday and date not in holidays:
            total_working_days += 1
        
        if is_1st_or_3rd_saturday or is_sunday or date in holidays:
            weekend_days_list.append(str(date))

    # Adjusted present and late days counting
    attended_dates = records.values_list('date', flat=True).distinct()
    present_dates = records.filter(
        status__in=['present', 'late', 'half_day']  # Include half_day as present
    ).values_list('date', flat=True).distinct().count()

    late_dates = records.filter(
        status__in=['late', 'half_day']  # Include half_day as late
    ).values_list('date', flat=True).distinct().count()

    half_days = records.filter(
        status='half_day'
    ).values_list('date', flat=True).distinct().count()

    present_days = present_dates

    approved_leaves = LeaveReportEmployee.objects.filter(
        employee=employee,
        status=1,
        start_date__month=current_month,
        start_date__year=current_year
    )
    
    leave_half_days = approved_leaves.filter(leave_type='Half-Day').count()

    if total_working_days > 0:
        effective_present_days = present_days + (leave_half_days * 0.5)
        attendance_percentage = (effective_present_days / total_working_days) * 100
    else:
        attendance_percentage = 0

    attendance_percentage = round(attendance_percentage, 1)

    recent_activities = ActivityFeed.objects.filter(
        user=request.user
    ).order_by('-timestamp').first()

    # Simplified today's status logic (status is handled in model)
    today_records = AttendanceRecord.objects.filter(
        user=request.user,
        date=today
    ).order_by('clock_in')

    today_total_worked = timedelta()
    today_status = None
    today_late = False
    today_half_day = False

    if today_records.exists():
        today_record = today_records.first()
        today_status = today_record.status
        
        if today_status == 'late':
            today_late = True
        elif today_status == 'half_day':
            today_late = True    # Half day counts as late
            today_half_day = True

        first_clock_in = today_record.clock_in
        last_clock_out_record = today_records.filter(clock_out__isnull=False).last()
        last_clock_out = last_clock_out_record.clock_out if last_clock_out_record else None
        
        if first_clock_in and last_clock_out:
            today_total_worked = last_clock_out - first_clock_in
            total_break_time = sum(
                (brk.duration for record in today_records 
                for brk in record.breaks.all() if brk.duration),
                timedelta()
            )
            today_total_worked -= total_break_time
    has_taken_lunch_today = Break.objects.filter(
    attendance_record__user=request.user,
    attendance_record__date=today,
    break_type='lunch'
    ).exists()
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
        'has_taken_lunch_today': has_taken_lunch_today,
        'attendance_stats': {
            'total_days': total_working_days,
            'present_days': present_days,
            'late_days': late_dates,
            'half_days': half_days,
            'absent_days': absent_days,
            'attendance_percentage': attendance_percentage,
            'total_breaks_in_month': total_breaks_in_month,
            'todays_total_breaks': todays_breaks,
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

@login_required   
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


@login_required   
def employee_feedback(request):
    employee = get_object_or_404(Employee, admin_id=request.user.id)
    form = FeedbackEmployeeForm(request.POST or None)
    
    # Paginate feedback list
    feedbacks_list = FeedbackEmployee.objects.filter(employee=employee).order_by('-created_at')
    paginator = Paginator(feedbacks_list, 5)  # 5 items per page
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        'form': form,
        'page_obj': page_obj,
        'page_title': 'Employee Feedback'
    }

    mark_notification_read(request, 0, "feedback", "employee")

    if request.method == 'POST':
        if form.is_valid():
            try:
                obj = form.save(commit=False)
                obj.employee = employee
                obj.save()
                messages.success(request, "Feedback submitted for review")
                user = CustomUser.objects.get(id=employee.team_lead.admin.id)
                send_notification(user, f"Feedback submitted for review for {obj.id}", "employee feedback", obj.id, "admin")
                # For AJAX form submission, return JSON
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    html = render_to_string('employee_template/employee_feedback.html', context, request=request)
                    return JsonResponse({
                        'html': html,
                        'success': True,
                        'message': "Feedback submitted for review"
                    })
                return redirect(reverse('employee_feedback'))
            except Exception:
                messages.error(request, "Could not Submit!")
        else:
            messages.error(request, "Form has errors!")
        
        # Handle form errors for AJAX
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': "Form has errors!" if form.errors else "Could not Submit!",
                'errors': form.errors.as_json()
            })

    # Handle AJAX pagination
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' and request.method == 'GET':
        html = render_to_string('employee_template/employee_feedback.html', context, request=request)
        return JsonResponse({
            'html': html,
            'current_page': page_obj.number,
            'num_pages': paginator.num_pages,
            'has_previous': page_obj.has_previous(),
            'has_next': page_obj.has_next(),
            'previous_page_number': page_obj.previous_page_number() if page_obj.has_previous() else None,
            'next_page_number': page_obj.next_page_number() if page_obj.has_next() else None,
        })

    return render(request, "employee_template/employee_feedback.html", context)


@login_required   
def employee_view_profile(request):
    employee = get_object_or_404(Employee, admin=request.user)
    context = {'employee': employee,
               'page_title': 'Profile'
               }
    return render(request, "employee_template/employee_view_profile.html", context)


@login_required   
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


@login_required   
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
            page = request.POST.get('page', 1)
            
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

                # Format total_worked to HHh MMm
                total_worked_str = '--'
                if day['total_worked'] and str(day['total_worked']) != '0:00:00':
                    total_seconds = int(day['total_worked'].total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    total_worked_str = f"{hours}h {minutes}m"

                json_data.append({
                    "date": date_str,
                    "status": day['status'],
                    "clock_in": localtime(day['first_clock_in']).strftime('%I:%M %p') if day['first_clock_in'] else '--',
                    "clock_out": localtime(day['last_clock_out']).strftime('%I:%M %p') if day['last_clock_out'] else '--',
                    "total_worked": total_worked_str,
                    "records_count": day['records_count']
                })

            # Paginate the json_data
            paginator = Paginator(json_data, 1)  # 5 records per page
            try:
                page_obj = paginator.page(page)
            except PageNotAnInteger:
                page_obj = paginator.page(1)
            except EmptyPage:
                page_obj = paginator.page(paginator.num_pages)

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                # Render the full template with paginated data
                context = {
                    'page_title': 'View Attendance',
                    'default_start': start_date,
                    'default_end': end_date,
                    'page_obj': page_obj,
                    'json_data': page_obj.object_list,  # Pass paginated data
                }
                html = render_to_string('employee_template/employee_view_attendance.html', context, request=request)
                return JsonResponse({
                    'html': html,
                    'current_page': page_obj.number,
                    'num_pages': paginator.num_pages,
                    'has_previous': page_obj.has_previous(),
                    'has_next': page_obj.has_next(),
                    'previous_page_number': page_obj.previous_page_number() if page_obj.has_previous() else None,
                    'next_page_number': page_obj.next_page_number() if page_obj.has_next() else None,
                })

            return JsonResponse({'data': page_obj.object_list}, safe=False)

        except ValueError as e:
            return JsonResponse({'error': f'Invalid date format: {str(e)}'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

        
@login_required   
def employee_view_salary(request):
    employee = get_object_or_404(Employee, admin=request.user)
    salarys = EmployeeSalary.objects.filter(employee=employee)
    context = {
        'salarys': salarys,
        'page_title': "View Salary"
    }
    return render(request, "employee_template/employee_view_salary.html", context)


@login_required   
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


@login_required   
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



from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from .models import Employee, DailySchedule
from datetime import date

@login_required
def daily_schedule(request):
    employee = get_object_or_404(Employee, admin=request.user)
    today = date.today()
    
    # Get schedule_id from query string for editing
    schedule_id = request.GET.get('schedule_id')
    
    # Get all schedules for history
    all_schedules = DailySchedule.objects.filter(employee=employee).order_by('-date')
    
    # Format schedules with hours and minutes for display
    formatted_schedules = []
    for schedule in all_schedules:
        total_minutes = 0
        for task in schedule.task_description.splitlines():
            try:
                time_part = task.split('(')[1].split(')')[0].strip().lower()
                if 'h' in time_part:
                    total_minutes += float(time_part.replace('h', '')) * 60
                elif 'm' in time_part:
                    total_minutes += float(time_part.replace('m', ''))
                elif 's' in time_part:
                    total_minutes += float(time_part.replace('s', '')) / 60
            except (IndexError, ValueError):
                continue
        
        if abs(schedule.total_hours - (total_minutes / 60)) > 0.01:
            schedule.total_hours = total_minutes / 60
            schedule.save()
        
        hours = int(total_minutes / 60)
        minutes = int(total_minutes % 60)
        formatted_schedules.append({
            'id': schedule.id,
            'date': schedule.date,
            'project': schedule.project,
            'task_description': schedule.task_description,
            'justification': schedule.justification,
            'hours': hours,
            'minutes': minutes,
        })
    
    # Load existing schedule for editing
    edit_schedule = None
    edit_tasks = []
    if schedule_id:
        edit_schedule = get_object_or_404(DailySchedule, id=schedule_id, employee=employee)
        # Preprocess tasks for editing
        for task in edit_schedule.task_description.splitlines():
            try:
                desc, time = task.split(' (')
                time = time.rstrip(')')
                edit_tasks.append({
                    'description': desc.strip(),
                    'time': time.strip()
                })
            except (IndexError, ValueError):
                continue
    
    if request.method == 'POST':
        task_description = request.POST.get('task_description', '')
        project = request.POST.get('project', '')
        justification = request.POST.get('justification', '')
        schedule_date = request.POST.get('schedule_date', today)
        schedule_id = request.POST.get('schedule_id')  # Get schedule_id from form

        # Validate tasks
        tasks = [line.strip() for line in task_description.split("\n") if line.strip()]
        invalid_tasks = [t for t in tasks if '|' not in t]
        
        if invalid_tasks:
            messages.error(request, "Each task must include time estimate (e.g., 'Task description|2h')")
            return render(request, 'employee_template/daily_schedule.html', {
                'schedules': formatted_schedules,
                'today': today,
                'edit_schedule': edit_schedule,
                'edit_tasks': edit_tasks,
                'project': project,
                'justification': justification,
            })

        # Calculate total time
        total_minutes = 0
        for task in tasks:
            try:
                time_part = task.split('|')[1].strip().lower()
                if 'h' in time_part:
                    total_minutes += float(time_part.replace('h', '')) * 60
                elif 'm' in time_part:
                    total_minutes += float(time_part.replace('m', ''))
                elif 's' in time_part:
                    total_minutes += float(time_part.replace('s', '')) / 60
                else:
                    total_minutes += float(time_part)
            except (IndexError, ValueError):
                messages.error(request, "Invalid time format in tasks")
                return render(request, 'employee_template/daily_schedule.html', {
                    'schedules': formatted_schedules,
                    'today': today,
                    'edit_schedule': edit_schedule,
                    'edit_tasks': edit_tasks,
                    'project': project,
                    'justification': justification,
                })

        # Format tasks for storage
        formatted_tasks = []
        for task in tasks:
            desc, time = task.split('|')
            formatted_tasks.append(f"{desc.strip()} ({time.strip()})")
        formatted_task_description = "\n".join(formatted_tasks)

        if schedule_id:
            # Update existing schedule
            edit_schedule = get_object_or_404(DailySchedule, id=schedule_id, employee=employee)
            edit_schedule.task_description = formatted_task_description
            edit_schedule.project = project
            edit_schedule.justification = justification if total_minutes < 480 else ''
            edit_schedule.total_hours = total_minutes / 60
            edit_schedule.date = schedule_date
            try:
                edit_schedule.save()
                messages.success(request, "Schedule successfully updated!")
                return redirect('daily_schedule')
            except ValidationError as e:
                messages.error(request, f"Error updating schedule: {e}")
        else:
            # Create new schedule
            existing_schedule = DailySchedule.objects.filter(employee=employee, date=schedule_date).first()
            if existing_schedule:
                messages.error(request, "A schedule already exists for this date!")
                return render(request, 'employee_template/daily_schedule.html', {
                    'schedules': formatted_schedules,
                    'today': today,
                    'edit_schedule': edit_schedule,
                    'edit_tasks': edit_tasks,
                    'project': project,
                    'justification': justification,
                })
            
            schedule = DailySchedule(
                employee=employee,
                date=schedule_date,
                task_description=formatted_task_description,
                project=project,
                justification=justification if total_minutes < 480 else '',
                total_hours=total_minutes / 60
            )
            try:
                schedule.save()
                messages.success(request, "Schedule created successfully!")
                return redirect('daily_schedule')
            except ValidationError as e:
                messages.error(request, f"Error creating schedule: {e}")

    return render(request, 'employee_template/daily_schedule.html', {
        'schedules': formatted_schedules,
        'today': today,
        'edit_schedule': edit_schedule,
        'edit_tasks': edit_tasks,
    })
    
    
    
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import ValidationError
from datetime import datetime
from django.utils import timezone

def get_ist_date():
    ist = timezone.get_current_timezone()
    return timezone.now().astimezone(ist).date()

@login_required
def todays_update(request):
    employee = get_object_or_404(Employee, admin=request.user)
    today = get_ist_date()
    schedule = DailySchedule.objects.filter(employee=employee, date=today).first()
    
    if not schedule:
        messages.error(request, "Create a schedule first!")
        return redirect('daily_schedule')

    existing_update = schedule.updates.first()
    is_editable = not existing_update or existing_update.updated_at.date() == today

    if request.method == 'POST' and is_editable:
        update_description = request.POST.get('update_description', '')
        justification = request.POST.get('justification', '')
        
        # Validate updates
        updates = [line.strip() for line in update_description.split("\n") if line.strip()]
        invalid_updates = [u for u in updates if '|' not in u or len(u.split('|')) != 2]
        
        if invalid_updates:
            messages.error(request, "Each update must include description and time spent (e.g., 'Completed task|1.5h')")
            return render(request, 'employee_template/todays_update.html', {
                'schedule': schedule,
                'update': existing_update,
                'today': today,
                'is_editable': is_editable,
                'justification': justification,
            })

        # Calculate total time spent and validate time format
        total_minutes = 0
        for update in updates:
            try:
                desc, time_part = update.split('|')
                time_part = time_part.strip().lower()
                if 'h' in time_part:
                    total_minutes += float(time_part.replace('h', '')) * 60
                elif 'm' in time_part:
                    total_minutes += float(time_part.replace('m', ''))
                elif 's' in time_part:
                    total_minutes += float(time_part.replace('s', '')) / 60
                else:
                    raise ValueError
            except (ValueError, IndexError):
                messages.error(request, f"Invalid time format in update: {update}. Use format like 'Task|1.5h'")
                return render(request, 'employee_template/todays_update.html', {
                    'schedule': schedule,
                    'update': existing_update,
                    'today': today,
                    'is_editable': is_editable,
                    'justification': justification,
                })

        # Require justification if total time is less than 8 hours (480 minutes)
        if total_minutes < 480 and not justification.strip():
            messages.error(request, "Please provide justification for spending less than 8 hours.")
            return render(request, 'employee_template/todays_update.html', {
                'schedule': schedule,
                'update': existing_update,
                'today': today,
                'is_editable': is_editable,
                'justification': justification,
            })

        if existing_update:
            # Update existing
            existing_update.update_description = update_description
            existing_update.justification = justification
            try:
                existing_update.full_clean()
                existing_update.save()
                messages.success(request, "Update modified successfully!")
            except ValidationError as e:
                messages.error(request, f"Error updating: {e}")
                return render(request, 'employee_template/todays_update.html', {
                    'schedule': schedule,
                    'update': existing_update,
                    'today': today,
                    'is_editable': is_editable,
                    'justification': justification,
                })
        else:
            # Create new
            update = DailyUpdate(
                schedule=schedule,
                update_description=update_description,
                justification=justification,
            )
            try:
                update.full_clean()
                update.save()
                messages.success(request, "Update submitted successfully!")
            except ValidationError as e:
                messages.error(request, f"Error submitting: {e}")
                return render(request, 'employee_template/todays_update.html', {
                    'schedule': schedule,
                    'update': existing_update,
                    'today': today,
                    'is_editable': is_editable,
                    'justification': justification,
                })

        return redirect('todays_update')

    return render(request, 'employee_template/todays_update.html', {
        'schedule': schedule,
        'update': existing_update,
        'today': today,
        'is_editable': is_editable,
    })

def view_all_schedules(request):
    """View all schedules and their updates for the logged-in employee"""
    employee = get_object_or_404(Employee, admin=request.user)
    today = get_ist_date()

    schedules = DailySchedule.objects.filter(employee=employee).order_by('-date')

    # Get filter parameters
    filter_type = request.GET.get('filter_type', 'today')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    # Base queryset
    schedules = DailySchedule.objects.filter(employee=employee).order_by('-date')

    if filter_type == 'today':
        schedules = schedules.filter(date=today)
    elif filter_type == 'weekly':
        start = today - timedelta(days=6)  # last 7 days including today
        schedules = schedules.filter(date__gte=start, date__lte=today)
    elif filter_type == "monthly":
        start = today - timedelta(days=29)  
        schedules = schedules.filter(date__gte=start, date__lte=today)
    elif filter_type == 'custom' and start_date and end_date:
        try:
            from datetime import datetime
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
            if start > end:
                messages.error(request, "Start date cannot be after end date.")
                start = end = today
            schedules = schedules.filter(date__gte=start, date__lte=end)
        except ValueError:
            messages.error(request, "Invalid date format. Using all schedules.")
            start_date = end_date = None

    if 'export' in request.GET:
        if not schedules:
            messages.error(request,"No Schedules Found for this date range")
        else:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Schedules and Updates"

            # Define headers
            headers = [
                "Schedule Date", "Project", "Tasks-Schedule", "Task-Updates"
            ]

            ws.append(headers)
            for cell in ws[1]:
                cell.font = Font(bold=True)
                cell.alignment = Alignment(horizontal='center', vertical='center')
            
            for schedule in schedules:
                tasks = schedule.task_description_lines
                updates = schedule.updates.all()
                if not updates:
                    # Schedule without updates
                    ws.append([
                        schedule.date.strftime('%Y-%m-%d'),
                        schedule.project or '',
                        '\n'.join(tasks) if tasks else 'No tasks',
                        '', '', ''
                    ])
                else:
                    for update in updates:
                        update_lines = update.update_description_lines
                        ws.append([
                            schedule.date.strftime('%Y-%m-%d'),
                            schedule.project or '',
                            '\n'.join(tasks) if tasks else 'No tasks',
                            '\n'.join(update_lines) if update_lines else 'No updates'
                        ])
            # Adjust column widths
            for col in ws.columns:
                max_length = 0
                column = col[0].column_letter
                for cell in col:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = (max_length + 2)
                ws.column_dimensions[column].width = adjusted_width
            
            # Create response
            output = BytesIO()
            wb.save(output)
            output.seek(0)
            response = HttpResponse(
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                content=output.getvalue()
            )
            response['Content-Disposition'] = f'attachment; filename=schedules_{today.strftime("%Y%m%d")}.xlsx'
            return response
    
    return render(request, 'employee_template/all_schedules.html', {
        'schedules': schedules,
        'today': today,
        'filter_type': filter_type,
        'start_date': start_date,
        'end_date': end_date
    })


@login_required
def others_schedule(request):
    employee = get_object_or_404(Employee, admin=request.user)
    if not employee.department:
        messages.error(request, "You are not assigned to a department.")
        return redirect('all_schedules')

    # Get filter parameters
    filter_type = request.GET.get('filter_type', 'today')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    employee_id = request.GET.get('employee_id')

    schedules = DailySchedule.objects.filter(
        employee__department=employee.department
    ).exclude(employee=employee).order_by('-date')

    # Apply date filters
    today = get_ist_date()
    if filter_type == 'today':
        schedules = schedules.filter(date=today)
    elif filter_type == 'weekly':
        start = today - timedelta(days=6)
        schedules = schedules.filter(date__gte=start, date__lte=today)
    elif filter_type == 'monthly':
        start = today - timedelta(days=29)
        schedules = schedules.filter(date__gte=start, date__lte=today)
    elif filter_type == 'custom' and start_date and end_date:
        try:
            from datetime import datetime
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
            if start > end:
                messages.error(request, "Start date cannot be after end date.")
                start = end = today
            schedules = schedules.filter(date__gte=start, date__lte=end)
        except ValueError:
            messages.error(request, "Invalid date format. Using all schedules.")
            start_date = end_date = None
    
    if employee_id and employee_id != 'all':
        try:
            schedules = schedules.filter(employee__id=employee_id)
        except ValueError:
            messages.error(request, "Invalid employee selected.")

    # Get other employees in the department for the filter dropdown
    department_employees = Employee.objects.filter(
        department=employee.department
    ).exclude(id=employee.id).order_by('admin__first_name')

    return render(request, 'employee_template/others_schedules.html', {
        'schedules': schedules,
        'today': today,
        'filter_type': filter_type,
        'start_date': start_date,
        'end_date': end_date,
        'employee_id': employee_id,
        'department_employees': department_employees
    })


@login_required
def early_clock_out_request_page(request):
    context = {
        'has_active_attendance': False,
        'request_status': 'none',
        'request_message': '',
    }

    attendance_record = AttendanceRecord.objects.filter(
        user=request.user,
        date=timezone.now().date(),
        clock_out__isnull=True
    ).first()

    if attendance_record:
        context['has_active_attendance'] = True
        early_request = EarylyClockOutRequest.objects.filter(
            attendance_record=attendance_record
        ).order_by('-submitted_at').first()
        if early_request:
            context['request_status'] = early_request.status
            context['request_message'] = early_request.notes or ''

    return render(request, 'employee_template/early_clock_out_request.html', context)