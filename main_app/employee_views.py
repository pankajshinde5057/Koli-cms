import json
from datetime import datetime
from django.contrib import messages
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, redirect, get_object_or_404,reverse
from django.utils import timezone

from .forms import *
from .models import *
from django.db.models import Sum, F, DurationField, ExpressionWrapper
from django.db.models.functions import Coalesce
from datetime import timedelta


def employee_home(request):
    employee = get_object_or_404(Employee, admin=request.user)
    
    # Get filter parameters
    date_filter = request.GET.get('date')
    department_filter = request.GET.get('department')
    status_filter = request.GET.get('status')

    # Base queryset - employee's records only
    records = AttendanceRecord.objects.filter(user=request.user).select_related('department')

    # Apply filters
    if department_filter:
        records = records.filter(department_id=department_filter)
    if status_filter:
        records = records.filter(status=status_filter)

    # Apply date filters
    today = timezone.now().date()
    if date_filter == 'today':
        records = records.filter(date=today)
    elif date_filter == 'week':
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
        records = records.filter(date__range=[start_date, end_date])
    elif date_filter == 'month':
        records = records.filter(date__month=today.month, date__year=today.year)

    # Daily View with break time calculation
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

    # For weekly and monthly views, we need to calculate differently
    # First get completed records with their break times
    completed_records = records.filter(clock_out__isnull=False).annotate(
        total_break_time=Coalesce(
            Sum('breaks__duration', output_field=DurationField()),
            timedelta()
        )
    )

    # Weekly View - calculate in Python if dataset isn't too large
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

    # Monthly View - calculate in Python
    monthly_data = {}
    for record in completed_records:
        month = record.date.replace(day=1)
        if month not in monthly_data:
            monthly_data[month] = {
                'total_hours': timedelta(),
                'regular_hours': timedelta(),
                'overtime_hours': timedelta(),
                'present_days': 0,
                'late_days': 0,
                'half_days': 0
            }
        
        net_worked = record.total_worked - record.total_break_time
        monthly_data[month]['total_hours'] += net_worked
        monthly_data[month]['regular_hours'] += record.regular_hours
        monthly_data[month]['overtime_hours'] += record.overtime_hours
        
        if record.status == 'present':
            monthly_data[month]['present_days'] += 1
        elif record.status == 'late':
            monthly_data[month]['late_days'] += 1
        elif record.status == 'half_day':
            monthly_data[month]['half_days'] += 1

    monthly_view = [{
        'month': month,
        'total_hours': data['total_hours'],
        'regular_hours': data['regular_hours'],
        'overtime_hours': data['overtime_hours'],
        'present_days': data['present_days'],
        'late_days': data['late_days'],
        'half_days': data['half_days']
    } for month, data in sorted(monthly_data.items(), reverse=True)]

    # Current status check
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
    
    total_breaks_today = Break.objects.filter(
        attendance_record__date=today
    ).count()
  
    
    # Attendance stats using the enhanced status field
    total_working_days = records.count()
    present_days = records.filter(status='present').count()
    late_days = records.filter(status='late').count()
    half_days = records.filter(status='half_day').count()
    absent_days = records.filter(status='absent').count()
    
    attendance_percentage = (present_days / total_working_days * 100) if total_working_days else 0
    # Recent activities (last 10)
    recent_activities = ActivityFeed.objects.filter(
        user=request.user
    ).order_by('-timestamp').first()

    context = {
        'page_title': 'Employee Dashboard',
        'employee': employee,
        'current_record': current_record,
        'current_break': current_break,
        'recent_activities': recent_activities,
        'attendance_stats': {
            'total_days': total_working_days,
            'present_days': present_days,
            'late_days': late_days,
            'half_days': half_days,
            'absent_days': absent_days,
            'attendance_percentage': round(attendance_percentage, 1),
            'total_breaks_today':total_breaks_today
        },
        'daily_view': daily_view,
        'weekly_view': weekly_view,
        'monthly_view': monthly_view,
        'current_filters': {
            'date': date_filter,
            'department': department_filter,
            'status': status_filter
        },
        'status_choices': AttendanceRecord.STATUS_CHOICES,
    }
    return render(request, 'employee_template/home_content.html', context)


def employee_apply_leave(request):
    form = LeaveReportEmployeeForm(request.POST or None)
    employee = get_object_or_404(Employee, admin_id=request.user.id)
    context = {
        'form': form,
        'leave_history': LeaveReportEmployee.objects.filter(employee=employee),
        'page_title': 'Apply for leave'
    }
    if request.method == 'POST':
        if form.is_valid():
            try:
                obj = form.save(commit=False)
                obj.employee = employee
                obj.save()
                messages.success(
                    request, "Application for leave has been submitted for review")
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
                return redirect(reverse('employee_feedback'))
            except Exception:
                messages.error(request, "Could not Submit!")
        else:
            messages.error(request, "Form has errors!")
    return render(request, "employee_template/employee_feedback.html", context)


def employee_view_profile(request):
    employee = get_object_or_404(Employee, admin=request.user)
    form = EmployeeEditForm(request.POST or None, request.FILES or None,
                           instance=employee)
    context = {'form': form,
               'page_title': 'View/Edit Profile'
               }
    if request.method == 'POST':
        try:
            if form.is_valid():
                first_name = form.cleaned_data.get('first_name')
                last_name = form.cleaned_data.get('last_name')
                password = form.cleaned_data.get('password') or None
                address = form.cleaned_data.get('address')
                gender = form.cleaned_data.get('gender')
                passport = request.FILES.get('profile_pic') or None
                admin = employee.admin
                if password != None:
                    admin.set_password(password)
                if passport != None:
                    fs = FileSystemStorage()
                    filename = fs.save(passport.name, passport)
                    passport_url = fs.url(filename)
                    admin.profile_pic = passport_url
                admin.first_name = first_name
                admin.last_name = last_name
                admin.address = address
                admin.gender = gender
                admin.save()
                employee.save()
                messages.success(request, "Profile Updated!")
                return redirect(reverse('employee_view_profile'))
            else:
                messages.error(request, "Invalid Data Provided")
        except Exception as e:
            messages.error(request, "Error Occured While Updating Profile " + str(e))

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


@ csrf_exempt
def employee_view_attendance(request):
    employee = get_object_or_404(Employee, admin=request.user)
    if request.method != 'POST':
        division = get_object_or_404(Division, id=employee.division.id)
        context = {
            'departments': Department.objects.filter(division=division),
            'page_title': 'View Attendance'
        }
        return render(request, 'employee_template/employee_view_attendance.html', context)
    else:
        department_id = request.POST.get('department')
        start = request.POST.get('start_date')
        end = request.POST.get('end_date')
        try:
            department = get_object_or_404(Department, id=department_id)
            start_date = datetime.strptime(start, "%Y-%m-%d")
            end_date = datetime.strptime(end, "%Y-%m-%d")
            attendance = AttendanceRecord.objects.filter(
                date__range=(start_date, end_date), department=department)
            attendance_reports = ActivityFeed.objects.filter(
                related_record__in=attendance, user=employee)
            json_data = []
            for report in attendance_reports:
                data = {
                    "date":  str(report.related_record.date),
                    "status": report.activity_type
                }
                json_data.append(data)
            return JsonResponse(json.dumps(json_data), safe=False)
        except Exception as e:
            return None

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
    notifications = NotificationEmployee.objects.filter(employee=employee)
    context = {
        'notifications': notifications,
        'page_title': "View Notifications"
    }
    return render(request, "employee_template/employee_view_notification.html", context)

def employee_requests(request):
    # leave , device claimed or not , device issue request
    employee = Employee.objects.get(admin=request.user)

    leave_requests = LeaveReportEmployee.objects.filter(employee=employee).order_by('-created_at')
    
    asset_claims = Notify_Manager.objects.filter(employee=request.user).order_by('-timestamp')

    context = {
        'leave_requests': leave_requests,
        # 'leave_reports': leave_reports,
        'asset_claims': asset_claims,
        # 'issue_reports': issue_reports,
        'page_title': 'My Requests'
    }

    return render(request, 'employee_template/employee_requests.html',context)