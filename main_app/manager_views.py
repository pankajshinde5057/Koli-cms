import json
from django.contrib import messages
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404,redirect, render
from django.urls import reverse
from django.db.models import Count,Q
from main_app.notification_badge import send_notification
from .forms import *
from .models import *
from asset_app.models import Notify_Manager,AssetsIssuance,Assets,LOCATION_CHOICES,AssetAssignmentHistory,AssetIssue,AssetCategory
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone
from datetime import datetime, time, timedelta
from django.forms.models import model_to_dict
from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from calendar import monthrange
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import transaction
from django.contrib.auth import update_session_auth_hash
import logging
from django.utils.text import get_valid_filename
from django.contrib.auth import get_user_model 
from .utils.email_utils import send_emails_in_background


LOCATION_CHOICES = (
    ("Main Room" , "Main Room"),
    ("Meeting Room", "Meeting Room"),
    ("Main Office", "Main Office"),
)

from django.utils.timezone import is_naive, make_aware

def make_aware_if_naive(dt):
    if dt and is_naive(dt):
        return make_aware(dt)
    return dt


@login_required   
def manager_home(request):
    try:
        manager = get_object_or_404(Manager, admin=request.user)
        manager_department = manager.department.name.lower().strip()
        today = date.today()
        current_time = timezone.now()

        predefined_names = ['Python Department', 'React JS Department', 'Node JS Department']
        all_departments = Department.objects.all()
        leave_request_from_employee = None
        if manager_department in ['hr','h r']:
            leave_request_from_employee = LeaveReportEmployee.objects.filter(status = 0).count()
        else:
            leave_request_from_employee = LeaveReportEmployee.objects.filter(status=0,employee__department=manager.department).count()
        # selected_department = request.GET.get('department', 'all').strip().lower()
        # start_date = request.GET.get('start_date')
        # end_date = request.GET.get('end_date')

        is_partial = request.GET.get('partial') == 'breaks'  # New flag for partial updates

        # try:
        #     if manager_department in ['hr','h r']:
        #         employees = CustomUser.objects.filter(user_type = '3')
        #     else:
        employees = CustomUser.objects.filter(user_type = '3')
        # except Exception as e:
        #     return render(request,'manager_template/home_content.html')
            
        # employees = Employee.objects.filter(department=manager.department)  

        normalized_predefined = [name.lower() for name in predefined_names]

        # if selected_department != 'all':
        #     if selected_department == 'others':
        #         employees = employees.exclude(employee__department__name__in=predefined_names)
        #     else:
        #         employees = employees.filter(employee__department__name__iexact=selected_department.title())

        employee_ids = employees.values_list('id', flat=True)
        filtered_records = AttendanceRecord.objects.filter(user_id__in=employee_ids)
        
        on_break_now = Break.objects.filter(
            attendance_record__user__in=employee_ids,
            break_start__date=today,
            break_start__lte=current_time,
        ).filter(models.Q(break_end__isnull=True) | models.Q(break_end__gte=current_time)).distinct()

        total_on_break = on_break_now.count()

        # if start_date and end_date:
        #     date_range = [parse_date(start_date), parse_date(end_date)]
        #     filtered_records = filtered_records.filter(date__range=date_range)

        time_history_data = []
        break_entries = []
        current_break = None

        for employee in employees:
            emp_records = filtered_records.filter(user=employee)
            total_present = emp_records.filter(status='present').count()
            total_late = emp_records.filter(status='late').count()
            
            emp_leaves = LeaveReportEmployee.objects.filter(employee__admin=employee,status=0)
            # if start_date and end_date:
            #     emp_leaves = emp_leaves.filter(
            #         start_date__lte=parse_date(end_date),
            #         end_date__gte=parse_date(start_date)
            #     )

            total_leave = emp_leaves.count()
        
            emp_breaks = Break.objects.filter(
                attendance_record__user=employee,
                break_start__date=today
            ).order_by('-break_start')  # Changed to descending order

            for b in emp_breaks:
                duration = 0
                if b.break_end:
                    duration_seconds = int((b.break_end - b.break_start).total_seconds())
                else:
                    duration_seconds = int((current_time - b.break_start).total_seconds())

                minutes = int(duration_seconds // 60)
                seconds = int(duration_seconds % 60)

                if minutes > 0 and seconds > 0:
                    duration = f"{minutes} min {seconds} sec"
                elif minutes > 0:
                    duration = f"{minutes} min"
                else:
                    duration = f"{seconds} sec"

                break_entries.append({
                    'employee_id': employee.id,
                    'employee_name': employee.get_full_name(),
                    'department': employee.employee.department.name if hasattr(employee, 'employee') and employee.employee.department else '',
                    'break_start': b.break_start.strftime('%H:%M'),
                    'break_end': b.break_end.strftime('%H:%M') if b.break_end else 'Ongoing',
                    'break_duration': duration,
                })

            # current record
            current_record = AttendanceRecord.objects.filter(
                user=request.user,
                clock_out__isnull=True,
                date=today
            ).first()

            # for break start end
            current_break = None
            if current_record:
                current_break = Break.objects.filter(
                    attendance_record=current_record,
                    break_end__isnull=True
                ).first()

        # Sort break entries by break_start in descending order (newest first)
        if break_entries:
            break_entries = sorted(break_entries, key=lambda x: x['break_start'], reverse=True)
            
        # Paginate break entries
        paginator = Paginator(break_entries, 10)  
        try:
            page_number = int(request.GET.get('page', 1))
        except ValueError:
            page_number = 1
        page_obj = paginator.get_page(page_number)
        break_entries = page_obj.object_list
        
        for employee in employees:
            time_history_data.append({
                'employee_name': employee.get_full_name(),
                'department': employee.employee.department.name if hasattr(employee, 'employee') and employee.employee.department else '',
                'present': total_present,
                'late': total_late,
                'leave': total_leave,
                'working_days': total_present + total_late,
            })

        context = {
            'page_title': f"Manager Dashboard",
            'departments': all_departments,
            'time_history_data': time_history_data,
            # 'selected_department': selected_department,
            # 'start_date': start_date,
            # 'end_date': end_date,
            'total_employees': employees.count(),
            'total_attendance': filtered_records.count(),
            'total_leave': sum(item['leave'] for item in time_history_data),
            'total_department': all_departments.count(),
            'total_on_break': total_on_break,
            'break_entries': break_entries,
            'page_obj': page_obj,
            'current_break': current_break,
            'leave_request_from_employee': leave_request_from_employee
        }

        if is_partial:
            # Return only the breaks table for AJAX updates
            return render(request, 'manager_template/partials/breaks_table.html', context)
        
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string('manager_template/home_content.html', context, request=request)
            return HttpResponse(html)

        return render(request, 'manager_template/home_content.html', context)
    
    except Exception as e:
        print(e)
        # messages.warning(request,"something went wrong")
        return render(request,'manager_template/home_content.html')


    
    

logger = logging.getLogger(__name__)

@login_required
def manager_leave_balance(request):
    manager = get_object_or_404(Manager, admin=request.user)
    today = get_ist_date()
    current_year = today.year
    current_month = today.month

    # Check for the first clock-in
    first_clock_in = AttendanceRecord.objects.filter(
        user=request.user,
        status__in=['present', 'late', 'half_day']
    ).order_by('date').first()

    yearly_leave_data = []
    total_available_leaves = 0.0
    yearly_total_allocated_leaves = 0.0
    total_used_leaves = 0.0

    if not first_clock_in:
        # Before first clock-in, show all values as 0.0 and an empty table
        context = {
            'page_title': 'Leave Balance',
            'manager': manager,
            'yearly_leave_data': yearly_leave_data,
            'total_available_leaves': round(total_available_leaves, 1),
            'yearly_total_allocated_leaves': round(yearly_total_allocated_leaves, 1),
        }
        return render(request, 'manager_template/manager_leave_balance.html', context)

    # After first clock-in, proceed with actual calculations
    leave_balances = ManagerLeaveBalance.objects.filter(manager=manager, year=current_year).order_by('month')
    joining_date = manager.date_of_joining

    if joining_date:
        joining_year = joining_date.year
        joining_month = joining_date.month

        # Calculate yearly total allocated and used leaves
        if current_year >= joining_year:
            start_month = joining_month if current_year == joining_year else 1
            end_month = 12  # Calculate until end of year
            months_in_year = end_month - start_month + 1
            yearly_total_allocated_leaves = months_in_year * 1.0  # 1 leave per month

            # Process leave balances to calculate total used leaves
            for month in range(start_month, end_month + 1):
                balance = leave_balances.filter(month=month).first()
                if not balance and month <= current_month:
                    balance = ManagerLeaveBalance.get_balance(manager, current_year, month)
                    if not balance:
                        balance = ManagerLeaveBalance.create_balance(manager, current_year, month)
                if balance:
                    # Validate used_leaves for the month
                    max_used_leaves = balance.allocated_leaves + balance.carried_forward
                    if balance.used_leaves > max_used_leaves:
                        balance.used_leaves = max_used_leaves
                        balance.save()
                    total_used_leaves += balance.used_leaves

            # Adjust yearly_total_allocated_leaves by subtracting total used leaves
            yearly_total_allocated_leaves -= total_used_leaves

            # Process monthly leave balances for display in the table
            for month in range(start_month, 13):
                if current_year == joining_year and month < joining_month:
                    continue
                balance = leave_balances.filter(month=month).first()
                if not balance and month <= current_month:
                    balance = ManagerLeaveBalance.get_balance(manager, current_year, month)
                    if not balance:
                        balance = ManagerLeaveBalance.create_balance(manager, current_year, month)
                if balance:
                    yearly_leave_data.append({
                        'month': datetime(current_year, month, 1).strftime('%B'),
                        'allocated_leaves': balance.allocated_leaves,
                        'carried_forward': balance.carried_forward,
                        'used_leaves': balance.used_leaves,
                        'available_leaves': balance.total_available_leaves()
                    })
                    if month == current_month:
                        total_available_leaves = balance.total_available_leaves()

    logger.debug(f"Leave Balance - Year: {current_year}, Total Allocated: {yearly_total_allocated_leaves}, Total Used: {total_used_leaves}, Total Available (Current Month): {total_available_leaves}")

    context = {
        'page_title': 'Leave Balance',
        'manager': manager,
        'yearly_leave_data': yearly_leave_data,
        'total_available_leaves': round(total_available_leaves, 1),
        'yearly_total_allocated_leaves': round(yearly_total_allocated_leaves, 1),
    }
    return render(request, 'manager_template/manager_leave_balance.html', context) 
 

@login_required
def manager_todays_attendance(request):
    manager = get_object_or_404(Manager, admin=request.user)
    today = timezone.now()
    
    # if manager.department.name.strip().lower() in ['hr','h r']:
    #     team_members = Employee.objects.all()
    # else:
    #     team_members = Employee.objects.filter(team_lead=manager)
    
    team_members = Employee.objects.all()    
    employee_users = CustomUser.objects.filter(employee__in=team_members)
    
    today_attendances = AttendanceRecord.objects.filter(
        user__in=employee_users,
        date=today
    ).select_related('user__employee__department').order_by('-clock_in')

    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(today_attendances, 10)
    
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        'page_title': "Clocked-In Employees",
        'page_obj': page_obj,
        'current_date': today.strftime('%d-%m-%y'),
        'total_clocked_in': today_attendances.values('user').distinct().count()
    }
    return render(request, 'manager_template/todays_attendance.html', context)


@login_required   
def manager_take_attendance(request):
    manager = get_object_or_404(Manager, admin=request.user)
    print("manager",manager)
    departments = Department.objects.filter(division=manager.division)
    context = {
        'departments': departments,
        'page_title': 'Take Attendance',
    }
    return render(request, 'manager_template/manager_take_attendance.html', context)


@login_required   
@csrf_exempt
def get_employees(request):
    department_id = request.POST.get('department')
    try:
        if department_id == 'all':
            employees = Employee.objects.all()
        else:
            department = get_object_or_404(Department, id=department_id)
            employees = Employee.objects.filter(department=department)
        
        employee_data = []
        for employee in employees:
            data = {
                "id": employee.admin.id,
                "name": employee.admin.first_name + " " + employee.admin.last_name
            }
            employee_data.append(data)
        return JsonResponse(json.dumps(employee_data), content_type='application/json', safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required   
@csrf_exempt
def get_managers(request):
    print("sd fsdf","*"*20)
    department_id = request.POST.get('department')
    print(department_id,"*"*20)
    try:
        if department_id == 'all':
            managers = Manager.objects.all()
        else:
            department = get_object_or_404(Department, id=department_id)
            managers = Manager.objects.filter(department=department)
        manager_data = []
        for manager in managers:
            data = {
                "id": manager.admin.id,
                "name": manager.admin.first_name + " " + manager.admin.last_name
            }
            manager_data.append(data)
        return JsonResponse(json.dumps(manager_data), content_type='application/json', safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required   
@csrf_exempt
def save_attendance(request):
    employee_data = request.POST.get('employee_ids')
    date_str = request.POST.get('date')
    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    department_id = request.POST.get('department')
    half_full_day = request.POST.get('half_full_day')
    which_half = request.POST.get('which_half')
    today = date_obj.today()
    current_month = today.month
    current_year = today.year
    
    start_date = today.replace(day=1)
    if today.month == 12:
        next_month = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_month = today.replace(month=today.month + 1, day=1)

    end_date = next_month - timedelta(days=1)
    
    # Log incoming data for debugging
    print("$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$",request.user.id )
    print("start_date", start_date)
    print("end_date", end_date)
    print("Employee Data:", employee_data)
    print("half_full_day:", half_full_day)
    print("Date:", date_str)
    print("Department ID:", department_id)

    try:
        employees = json.loads(employee_data)
        
        department = get_object_or_404(Department, id=department_id)

        for emp in employees:
            if half_full_day:
                employee = CustomUser.objects.filter(id = int(emp)).first()
            else:
                employee = get_object_or_404(CustomUser, id=emp.get('id'))
            user = employee  # CustomUser linked
            # if half_full_day:
            status = 'present'
            # else:
            #     status = 'present' if emp.get('status') == 1 else 'late'

            # Only create if not already exists
            # created = False
            # try:
            #     attendance_record, created = AttendanceRecord.objects.get_or_create(
            #         user=user,
            #         date=date_obj,
            #         defaults={
            #             'clock_in': timezone.make_aware(datetime.combine(date_obj, datetime.min.time())),  # Make the datetime aware
            #             'status': status,
            #             'department': department,
            #             'is_primary_record': True,
            #         }
            #     )
            # except:
            #     pass
            # print("createdcreated",created)
            # if not created:
            #     # Update status if already exists
            #     attendance_record.status = status
            #     attendance_record.save()

            # Update the present day count in employee's dashboard
            # exist_data = AttendanceRecord.objects.filter( date__range=(start_date, end_date), department=department,user = employee.admin)
            # print("exist_data>>>>>>>>>>>>>>>>>>>>>>>>>>",exist_data)
            # LeaveReportEmployee.objects.filter(
            #     employee=employee,
            #     status=1,  # Approved leaves
            #     start_date__month=current_month,
            #     start_date__year=current_year
            # )
            # if exist_data:
            #     present_dates = exist_data.filter(
            #         status='present'
            #     ).values_list('date', flat=True).distinct().count()

            #     late_dates = exist_data.filter(
            #         status='late'
            #     ).values_list('date', flat=True).distinct().count()
            #     print("late_dates",late_dates)
            #     print("present_dates",present_dates)
            # if status == 'present':
            #     employee.present_days += 1
            # employee.save()
            
            if half_full_day == "full":
                leave_status = "Full-Day"
                total_work = 8*60*60
                status = "present"
                clock_in = datetime.combine(date_obj, time(14, 30, 0)) 
                clock_out = datetime.combine(date_obj, time(23, 30, 0)) 
            if half_full_day == "half":
                total_work = 4*60*60
                leave_status = "Half-Day"
                if which_half =="first":
                    # pass
                    status = "present"
                    clock_in = datetime.combine(date_obj, time(9, 00, 0)) 
                    clock_out = datetime.combine(date_obj, time(13, 00, 0))
                else:
                    status = "late"
                    clock_in = datetime.combine(date_obj, time(14, 00, 0)) 
                    clock_out = datetime.combine(date_obj, time(18, 00, 0)) 
            employee = Employee.objects.get(admin = employee)
            leave_record = LeaveReportEmployee.objects.create(
                employee = employee,
                leave_type = leave_status,
                start_date = date_obj,
                end_date = date_obj,
                message = f"Added From {request.user}",
                status = 1,
                created_at = today,
                updated_at = today
            )
            leave_record.save()
            user_id = int(emp)
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            manager_id = request.user.id
            attendance = AttendanceRecord.objects.create(
                date=date_obj,
                clock_in=clock_in,
                clock_out=clock_out,  # or provide clock_out datetime
                status=status,
                total_worked=total_work,  # e.g., 8 hours in seconds
                regular_hours=0,
                overtime_hours=0,
                is_primary_record=True,
                requires_verification=False,
                is_verified=True,
                verification_time=None,
                created_at=timezone.now(),
                updated_at=timezone.now(),
                user_id=user_id,
                verified_by_id=manager_id,
                department_id=department_id
            )
            print(">>>>>>>>>>>>>>>>>>>INSERTION",user_id, manager_id)
            attendance.save()

    

        return HttpResponse("OK")
    except Exception as e:
        import traceback
        # Log the exception for debugging
        print("Error:", str(e))
        exc_type, exc_value, exc_tb = traceback.format_exc().splitlines()[-1], e, e.__traceback__
    
        # Print the error message
        print(f"Error: {exc_value}")
        
        # Print the line number and traceback details
        print("Traceback details:")
        print(f"File: {exc_tb.tb_frame.f_code.co_filename}, Line: {exc_tb.tb_lineno}")
        
        # Print the complete traceback for debugging
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=400)



@login_required
def manager_update_attendance(request):
    current_date = datetime.now()
    current_year = current_date.year
    current_month = current_date.month

    years = [current_year + i for i in range(5)]
    months = [
        (f"{i:02}", datetime(current_year, i, 1).strftime('%B'))
        for i in range(1, 13)
    ]

    # Determine user access
    if hasattr(request.user, 'manager'):
        manager = request.user.manager
        departments = Department.objects.filter(division=manager.division)
        employees = Employee.objects.filter(department__in=departments).select_related('department')
        managers = Manager.objects.filter(department__in=departments).select_related('department')
    else:
        departments = Department.objects.all()
        employees = Employee.objects.all().select_related('department')
        managers = Manager.objects.all().select_related('department')

    context = {
        'departments': departments,
        'employees': employees,
        'managers': managers,
        'page_title': 'View Attendance',
        'months': months,
        'years': years,
        'current_year': current_year,
        'current_month': current_month
    }
    return render(request, 'manager_template/manager_update_attendance.html', context)





@login_required   
@csrf_exempt
def update_attendance(request):
    if request.method == 'POST':
        try:
            employee_ids = json.loads(request.POST.get('employee_ids', '[]'))
            date_str = request.POST.get('date')
            half_full_day = request.POST.get('half_full_day')  # 'half' or 'full'
            which_half = request.POST.get('which_half', '')  # 'first' or 'second'
            
            if not employee_ids or not date_str:
                return JsonResponse({"error": "Employee IDs and date are required"}, status=400)
            
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({"error": "Invalid date format. Use YYYY-MM-DD"}, status=400)
            
            updated_count = 0
            for emp_id in employee_ids:
                try:
                    # Fetch the employee
                    employee = Employee.objects.get(employee_id=emp_id)

                    # Calculate times based on attendance type
                    if half_full_day == 'full':
                        # Full day timing (9:00 AM to 6:00 PM)
                        status = 'present'
                        clock_in = datetime.combine(date_obj, time(9, 0))  # 9:00 AM
                        clock_out = datetime.combine(date_obj, time(18, 0))  # 6:00 PM
                        total_work = 9 * 60 * 60  # 9 hours in seconds
                    else:
                        # Half day timing
                        if which_half == 'first':
                            # First half (9:00 AM to 1:30 PM)
                            status = 'half_day_first'
                            clock_in = datetime.combine(date_obj, time(9, 0))
                            clock_out = datetime.combine(date_obj, time(13, 30))
                            total_work = 4.5 * 60 * 60  # 4.5 hours
                        else:
                            # Second half (1:30 PM to 6:00 PM)
                            status = 'half_day_second'
                            clock_in = datetime.combine(date_obj, time(13, 30))
                            clock_out = datetime.combine(date_obj, time(18, 0))
                            total_work = 4.5 * 60 * 60  # 4.5 hours
                    
                    # Save previous record snapshot (optional)
                    old_record = AttendanceRecord.objects.filter(user=employee.admin, date=date_obj).first()
                    if old_record:
                        old_data = model_to_dict(old_record)
                        print("Previous record:", old_data)

                    # Update or create the attendance record
                    record, created = AttendanceRecord.objects.update_or_create(
                        user=employee.admin,  # Correct reference to employee's admin (CustomUser)
                        date=date_obj,
                        defaults={
                            'status': status,
                            'clock_in': clock_in,
                            'clock_out': clock_out,
                            'total_worked': total_work,
                            'is_primary_record': True,
                            'requires_verification': False,
                            'is_verified': True,
                            'verified_by': request.user,
                            'updated_at': timezone.now()
                        }
                    )

                    # Save updated record snapshot (optional)
                    print("Updated record:", model_to_dict(record))
                    updated_count += 1
                    
                except Exception as e:
                    print(f"Error updating attendance for employee {emp_id}: {str(e)}")
                    continue
            
            return JsonResponse({
                "message": f"Attendance updated successfully for {updated_count} employees",
                "updated_count": updated_count
            })
            
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)
    
    return JsonResponse({"error": "Invalid request method"}, status=400)



logger = logging.getLogger(__name__)
User = get_user_model()


@login_required
@csrf_exempt
def get_employee_attendance(request):
    if request.method != 'POST':
        return JsonResponse({"error": "Invalid request method"}, status=405)

    try:
        # Retrieve POST parameters
        employee_id = request.POST.get('employee_id')
        department_id = request.POST.get('department_id')
        manager_id = request.POST.get('manager_id')
        month = request.POST.get('month')
        year = request.POST.get('year')
        week = request.POST.get('week')
        from_date = request.POST.get('from_date')
        to_date = request.POST.get('to_date')
        page = int(request.POST.get('page', 1))
        per_page = request.POST.get('per_page', 10)
        try:
            per_page = int(per_page)
            per_page = min(per_page, 10000)  # Cap per_page
        except ValueError:
            per_page = 10

        if not year and not (from_date and to_date):
            return JsonResponse({"error": "Year or date range is required"}, status=400)

        # Base queryset with related models
        queryset = AttendanceRecord.objects.select_related(
            'user__employee',
            'user__manager',
            'user__employee__department',
            'user__manager__department'
        ).prefetch_related('breaks').all()

        # Apply filters
        if employee_id and employee_id != 'all':
            try:
                employee = Employee.objects.get(employee_id=employee_id)
                if not employee.admin:
                    return JsonResponse({"error": "Employee has no associated user"}, status=400)
                queryset = queryset.filter(user=employee.admin)
            except Employee.DoesNotExist:
                return JsonResponse({"error": "Employee not found"}, status=400)
        elif manager_id and manager_id != 'all':
            try:
                manager = Manager.objects.filter(id=manager_id).first()
                if not manager:
                    manager = Manager.objects.filter(admin_id=manager_id).first()
                if not manager:
                    return JsonResponse({"error": "Manager not found"}, status=400)
                queryset = queryset.filter(user=manager.admin)
            except Exception as e:
                return JsonResponse({"error": f"Manager lookup error: {str(e)}"}, status=400)
        elif department_id and department_id != 'all':
            queryset = queryset.filter(
                Q(user__employee__department_id=department_id) |
                Q(user__manager__department_id=department_id)
            )
        else:
            # Handle 'all' cases for employees and/or managers
            employee_users = []
            manager_users = []
            if employee_id == 'all':
                employee_filter = Employee.objects.filter(department_id=department_id) if department_id and department_id != 'all' else Employee.objects.all()
                employee_users = [e.admin for e in employee_filter if e.admin]
            if manager_id == 'all':
                manager_filter = Manager.objects.filter(department_id=department_id) if department_id and department_id != 'all' else Manager.objects.all()
                manager_users = [m.admin for m in manager_filter if m.admin]
            # Combine and deduplicate users
            users = list(set(employee_users + manager_users))
            queryset = queryset.filter(user__in=users)

        # Date filtering
        holiday_dates = set()
        start_date = None
        end_date = None
        today = get_ist_date()
        current_year = today.year
        current_month = today.month

        # Apply date filters
        if from_date and to_date:
            try:
                start_date = datetime.strptime(from_date, '%Y-%m-%d').date()
                end_date = datetime.strptime(to_date, '%Y-%m-%d').date()
                queryset = queryset.filter(date__range=(start_date, end_date))
                holiday_dates = set(Holiday.objects.filter(
                    date__range=(start_date, end_date)
                ).values_list('date', flat=True))
            except ValueError:
                return JsonResponse({"error": "Invalid date format. Use YYYY-MM-DD"}, status=400)
        else:
            try:
                if year:
                    year = int(year)  # Convert year to integer
                    if week:
                        week = int(week)
                        first_day_of_year = datetime(year, 1, 1).date()
                        start_date = first_day_of_year + timedelta(weeks=week - 1)
                        end_date = start_date + timedelta(days=6)
                        if end_date > today:
                            end_date = today
                        queryset = queryset.filter(date__range=(start_date, end_date))
                        holiday_dates = set(Holiday.objects.filter(
                            date__range=(start_date, end_date)
                        ).values_list('date', flat=True))
                    elif month:
                        month = int(month)
                        start_date = datetime(year, month, 1).date()
                        days_in_month = monthrange(year, month)[1]
                        end_date = datetime(year, month, days_in_month).date()
                        queryset = queryset.filter(date__month=month, date__year=year)
                        holiday_dates = set(Holiday.objects.filter(
                            date__year=year,
                            date__month=month
                        ).values_list('date', flat=True))
                    else:
                        start_date = datetime(year, 1, 1).date()
                        end_date = datetime(year, 12, 31).date()
                        queryset = queryset.filter(date__year=year)
                        holiday_dates = set(Holiday.objects.filter(
                            date__year=year
                        ).values_list('date', flat=True))
                else:
                    start_date = datetime(current_year, current_month, 1).date()
                    end_date = today
                    queryset = queryset.filter(date__range=(start_date, end_date))
                    holiday_dates = set(Holiday.objects.filter(
                        date__range=(start_date, end_date)
                    ).values_list('date', flat=True))

            except ValueError as e:
                return JsonResponse({"error": "Invalid year or month format"}, status=400)

        # Calculate total working days and holiday count
        total_working_days = 0
        holiday_count = 0
        weekend_days = set()
        current_date = start_date
        while current_date <= end_date:
            weekday = current_date.weekday()
            is_sunday = weekday == 6
            is_saturday = weekday == 5
            is_2nd_or_4th_saturday = is_saturday and ((current_date.day - 1) // 7) in [1, 3]
            is_holiday = current_date in holiday_dates
            if is_sunday or is_2nd_or_4th_saturday or is_holiday:
                holiday_count += 1
                if is_sunday or is_2nd_or_4th_saturday:
                    weekend_days.add(current_date)
            else:
                total_working_days += 1
            current_date += timedelta(days=1)

        queryset = queryset.order_by('-date')

        # Initialize attendance and leave balance statistics
        present_days = 0
        late_days = 0
        half_days = 0
        absent_days = 0
        total_available_leaves = 0.0
        all_yearly_total_allocated_leaves = 0.0
        all_monthly_and_weekly_available_leaves = 0.0

        if start_date and end_date:
            user_stats = {}
            users = []

            if employee_id and employee_id != 'all':
                try:
                    employee = Employee.objects.get(employee_id=employee_id)
                    if not employee.admin:
                        return JsonResponse({"error": "Employee has no associated user"}, status=400)
                    users = [employee.admin]
                except Employee.DoesNotExist:
                    return JsonResponse({"error": "Employee not found"}, status=400)
            elif manager_id and manager_id != 'all':
                try:
                    manager = Manager.objects.filter(id=manager_id).first()
                    if not manager:
                        manager = Manager.objects.filter(admin_id=manager_id).first()
                    if manager:
                        users = [manager.admin]
                    else:
                        users = []
                except Exception:
                    users = []
            else:
                # Handle 'all' cases for employees and/or managers
                employee_users = []
                manager_users = []
                if employee_id == 'all':
                    employee_filter = Employee.objects.filter(department_id=department_id) if department_id and department_id != 'all' else Employee.objects.all()
                    employee_users = [e.admin for e in employee_filter if e.admin]
                if manager_id == 'all':
                    manager_filter = Manager.objects.filter(department_id=department_id) if department_id and department_id != 'all' else Manager.objects.all()
                    manager_users = [m.admin for m in manager_filter if m.admin]
                # Combine and deduplicate users
                users = list(set(employee_users + manager_users))

           # Inside the get_manager_and_employee_attendance view, replace the user stats loop (starting at "for user in users:") with this:
        for user in users:
            employee_for_user = Employee.objects.filter(admin=user).first()
            manager_for_user = Manager.objects.filter(admin=user).first()
            joining_date = employee_for_user.date_of_joining if employee_for_user else (manager_for_user.date_of_joining if manager_for_user else today)
            first_clock_in = AttendanceRecord.objects.filter(
                user=user,
                status__in=['present', 'late', 'half_day', 'leave']
            ).order_by('date').first()
            first_clock_in_date = first_clock_in.date if first_clock_in else None

            user_stats[user.id] = {
                'joining_date': joining_date,
                'first_clock_in_date': first_clock_in_date,
                'present_days': 0,
                'late_days': 0,
                'half_days': 0,
                'absent_days': 0,
                'available_leaves': 0.0,
                'leave_history': [],
                'yearly_total_allocated_leaves': 0.0,
                'yearly_total_used_leaves': 0.0,
                'monthly_and_weekly_available_leaves': 0.0,
                'carried_forward_leaves': 0.0
            }

            # Calculate leave balance
            if joining_date <= end_date and first_clock_in_date:
                joining_year = joining_date.year
                joining_month = joining_date.month
                year_for_calculation = int(year) if year else current_year

                # Initialize leave variables
                monthly_available_leaves = 0.0
                carried_forward_leaves = 0.0
                yearly_total_allocated_leaves = 0.0
                monthly_and_weekly_available_leaves = 0.0

                logger.info(f"Calculating leaves for user {user.id}, year {year_for_calculation}, joining_date {joining_date}")

                if year and not month and not week:
                    # Yearly view: Allocate 1 leave per month from joining month to December
                    start_month = joining_month if year_for_calculation == joining_year else 1
                    end_month = 12
                    monthly_available_leaves = max(0, end_month - start_month + 1)
                    previous_year = year_for_calculation - 1
                    previous_leave_balance = LeaveReportEmployee.objects.filter(
                        employee=employee_for_user,
                        start_date__year=previous_year,
                        status=1
                    ).last() if employee_for_user else LeaveReportManager.objects.filter(
                        manager=manager_for_user,
                        start_date__year=previous_year,
                        status=1
                    ).last()
                    carried_forward_leaves = previous_leave_balance.available_leaves if previous_leave_balance and hasattr(previous_leave_balance, 'available_leaves') and previous_leave_balance.available_leaves > 0 else 0.0
                    yearly_total_allocated_leaves = monthly_available_leaves + carried_forward_leaves
                    monthly_and_weekly_available_leaves = yearly_total_allocated_leaves
                    logger.info(f"Yearly view: start_month={start_month}, end_month={end_month}, monthly_available_leaves={monthly_available_leaves}, carried_forward_leaves={carried_forward_leaves}, yearly_total_allocated_leaves={yearly_total_allocated_leaves}")
                else:
                    # Month/week view: Allocate 1 leave if joining_date is before or on end_date
                    monthly_available_leaves = 1.0 if joining_date <= end_date else 0.0
                    previous_year = year_for_calculation - 1
                    previous_leave_balance = LeaveReportEmployee.objects.filter(
                        employee=employee_for_user,
                        start_date__year=previous_year,
                        status=1
                    ).last() if employee_for_user else LeaveReportManager.objects.filter(
                        manager=manager_for_user,
                        start_date__year=previous_year,
                        status=1
                    ).last()
                    carried_forward_leaves = previous_leave_balance.available_leaves if previous_leave_balance and hasattr(previous_leave_balance, 'available_leaves') and previous_leave_balance.available_leaves > 0 else 0.0
                    yearly_total_allocated_leaves = monthly_available_leaves + carried_forward_leaves
                    monthly_and_weekly_available_leaves = monthly_available_leaves
                    logger.info(f"Month/week view: monthly_available_leaves={monthly_available_leaves}, carried_forward_leaves={carried_forward_leaves}, yearly_total_allocated_leaves={yearly_total_allocated_leaves}")

                total_used = 0.0
                available_carried_forward = carried_forward_leaves
                monthly_leave_counted = {}
                leave_balances = LeaveReportEmployee.objects.filter(
                    employee=employee_for_user,
                    status=1,
                    start_date__year=year_for_calculation,
                    start_date__gte=joining_date,
                    start_date__lte=end_date,
                    end_date__gte=start_date
                ).order_by('start_date') if employee_for_user else LeaveReportManager.objects.filter(
                    manager=manager_for_user,
                    status=1,
                    start_date__year=year_for_calculation,
                    start_date__gte=joining_date,
                    start_date__lte=end_date,
                    end_date__gte=start_date
                ).order_by('start_date')

                
                for leave in leave_balances:
                    leave_start = max(leave.start_date, start_date, joining_date)
                    leave_end = min(leave.end_date, end_date)
                    leave_amount_per_day = 1.0 if leave.leave_type == 'Full-Day' else 0.5
                    current_date = leave_start
                    while current_date <= leave_end:
                        if current_date not in weekend_days and current_date >= joining_date:
                            month_key = current_date.month
                            if month_key not in monthly_leave_counted:
                                user_stats[user.id]['leave_history'].append({
                                    'date': current_date,
                                    'leave_amount': leave_amount_per_day,
                                    'leave_id': leave.id,
                                    'leave_type': leave.leave_type,
                                    'is_free_leave': True
                                })
                                total_used += leave_amount_per_day
                                monthly_leave_counted[month_key] = True
                            elif available_carried_forward >= leave_amount_per_day:
                                user_stats[user.id]['leave_history'].append({
                                    'date': current_date,
                                    'leave_amount': leave_amount_per_day,
                                    'leave_id': leave.id,
                                    'leave_type': leave.leave_type,
                                    'is_carried_forward': True
                                })
                                total_used += leave_amount_per_day
                                available_carried_forward -= leave_amount_per_day
                              
                            else:
                                user_stats[user.id]['leave_history'].append({
                                    'date': current_date,
                                    'leave_amount': leave_amount_per_day,
                                    'leave_id': leave.id,
                                    'leave_type': leave.leave_type,
                                    'is_ignored': True
                                })
                               
                        current_date += timedelta(days=1)

                user_stats[user.id]['leave_history'].sort(key=lambda x: x['date'])
                user_stats[user.id]['yearly_total_allocated_leaves'] = yearly_total_allocated_leaves
                user_stats[user.id]['yearly_total_used_leaves'] = total_used
                user_stats[user.id]['available_leaves'] = max(0, yearly_total_allocated_leaves - total_used)
                user_stats[user.id]['monthly_and_weekly_available_leaves'] = max(0, monthly_and_weekly_available_leaves - total_used)
                user_stats[user.id]['carried_forward_leaves'] = carried_forward_leaves
                total_available_leaves += user_stats[user.id]['available_leaves']
                all_yearly_total_allocated_leaves += user_stats[user.id]['yearly_total_allocated_leaves']
                all_monthly_and_weekly_available_leaves += user_stats[user.id]['monthly_and_weekly_available_leaves']
               
    
                # Process leave sufficiency
                available_leaves = monthly_and_weekly_available_leaves + carried_forward_leaves
                for entry in user_stats[user.id]['leave_history']:
                    leave_amount = entry['leave_amount']
                    entry['available_before'] = available_leaves
                    if available_leaves >= leave_amount and not entry.get('is_ignored', False):
                        available_leaves -= leave_amount
                        entry['was_sufficient'] = True
                    else:
                        entry['was_sufficient'] = False
                    entry['available_after'] = max(0, available_leaves)

            date_status_map = {}
            for record in queryset:
                user_id = record.user.id
                if user_id not in date_status_map:
                    date_status_map[user_id] = {}
                date_status_map[user_id][record.date] = record.status

            # Process attendance and leave
            current_date = max(start_date, joining_date)
            if not first_clock_in_date or today < first_clock_in_date:
                user_stats[user.id]['absent_days'] = total_working_days
                continue

            while current_date <= end_date:
                if current_date in weekend_days or current_date in holiday_dates:
                    current_date += timedelta(days=1)
                    continue
                if current_date < joining_date:
                    user_stats[user.id]['absent_days'] += 1.0
                    current_date += timedelta(days=1)
                    continue
                if current_date < first_clock_in_date:
                    user_stats[user.id]['absent_days'] += 1.0
                    current_date += timedelta(days=1)
                    continue

                user_date_status = date_status_map.get(user.id, {}).get(current_date)
                leave_entry = next((entry for entry in user_stats[user.id]['leave_history'] if entry['date'] == current_date), None)

                if leave_entry:
                    leave_amount = leave_entry['leave_amount']
                    leave_type = leave_entry['leave_type']
                    was_sufficient = leave_entry.get('was_sufficient', False)
                    if leave_type == 'Full-Day':
                        if was_sufficient:
                            user_stats[user.id]['present_days'] += 1.0
                        else:
                            user_stats[user.id]['absent_days'] += 1.0
                    else:  # Half-Day
                        if was_sufficient:
                            user_stats[user.id]['present_days'] += 0.5
                            user_stats[user.id]['half_days'] += 1
                            user_stats[user.id]['absent_days'] += 0.5
                           
                        else:
                            user_stats[user.id]['absent_days'] += 1.0
                            user_stats[user.id]['half_days'] += 1
                          
                elif user_date_status == 'leave':
                    if user_stats[user.id]['monthly_and_weekly_available_leaves'] >= 1.0 and not (year and not month and not week):
                        user_stats[user.id]['present_days'] += 1.0
                        user_stats[user.id]['monthly_and_weekly_available_leaves'] = max(0, user_stats[user.id]['monthly_and_weekly_available_leaves'] - 1.0)
                        user_stats[user.id]['available_leaves'] = max(0, user_stats[user.id]['available_leaves'] - 1.0)
                       
                    else:
                        user_stats[user.id]['absent_days'] += 1.0
                        
                elif user_date_status == 'present':
                    user_stats[user.id]['present_days'] += 1
                 
                elif user_date_status == 'late':
                    user_stats[user.id]['present_days'] += 1
                    user_stats[user.id]['late_days'] += 1
                  
                elif user_date_status == 'half_day':
                    user_stats[user.id]['present_days'] += 1
                    user_stats[user.id]['half_days'] += 1
                    user_stats[user.id]['absent_days'] += 0.5
                  
                elif current_date <= today:
                    user_stats[user.id]['absent_days'] += 1.0
                  

                current_date += timedelta(days=1)

            present_days += user_stats[user.id]['present_days']
            late_days += user_stats[user.id]['late_days']
            half_days += user_stats[user.id]['half_days']
            absent_days += user_stats[user.id]['absent_days']
        # Calculate attendance percentage
        attendance_percentage = (present_days / total_working_days * 100) if total_working_days > 0 else 0
        attendance_percentage = round(attendance_percentage, 1)

        attendance_list = []
        attendance_dates = set(queryset.values_list('date', flat=True))

        for record in queryset:
            if hasattr(record.user, 'employee'):
                user = record.user.employee
                name = f"{user.admin.first_name} {user.admin.last_name}"
                department = user.department.name if user.department else "HR"
                user_type = "Employee"
                user_id_field = user.employee_id
            elif hasattr(record.user, 'manager'):
                user = record.user.manager
                name = f"{user.admin.first_name} {user.admin.last_name}"
                department = user.department.name if user.department else "HR"
                user_type = "Manager"
                user_id_field = getattr(user, 'manager_id', None) or getattr(user, 'admin_id', None) or str(user.id)
            else:
                continue

            status = record.status.capitalize() if record.status == 'leave' else record.status
            hours = "0h 0m"
            if record.total_worked:
                total_seconds = record.total_worked.total_seconds()
                hours_worked = int(total_seconds // 3600)
                minutes_worked = int((total_seconds % 3600) // 60)
                hours = f"{hours_worked}h {minutes_worked}m"

            attendance_list.append({
                "date": record.date.isoformat(),
                "day": record.date.strftime('%a'),
                "status": status,
                "clock_in": record.clock_in.isoformat() if record.clock_in else None,
                "clock_out": record.clock_out.isoformat() if record.clock_out else None,
                "hours": hours,
                "name": name,
                "department": department,
                "user_type": user_type,
                "user_id": user_id_field,
            })

        # Add leave entries
        for user_id, stats in user_stats.items():
            user = User.objects.get(id=user_id)
            employee_for_user = Employee.objects.filter(admin=user).first()
            manager_for_user = Manager.objects.filter(admin=user).first()
            joining_date = stats['joining_date']
            name = f"{user.first_name} {user.last_name}"
            department = employee_for_user.department.name if employee_for_user and employee_for_user.department else (manager_for_user.department.name if manager_for_user and manager_for_user.department else "HR")
            user_type = "Employee" if employee_for_user else "Manager"
            user_id_field = employee_for_user.employee_id if employee_for_user else (getattr(manager_for_user, 'manager_id', None) or getattr(manager_for_user, 'admin_id', None) or str(manager_for_user.id))

            for leave_entry in stats['leave_history']:
                leave_date = leave_entry['date']
                if leave_date >= start_date and leave_date <= end_date and leave_date >= joining_date and leave_date not in attendance_dates:
                    status = "Leave" if leave_entry['leave_type'] == 'Full-Day' else "Half-Day"
                    attendance_list.append({
                        "date": leave_date.isoformat(),
                        "day": leave_date.strftime('%a'),
                        "status": status,
                        "clock_in": None,
                        "clock_out": None,
                        "hours": "0h 0m",
                        "name": name,
                        "department": department,
                        "user_type": user_type,
                        "user_id": user_id_field,
                    })

        attendance_list = sorted(attendance_list, key=lambda x: x['date'], reverse=True)

        paginator = Paginator(attendance_list, per_page)
        try:
            page_obj = paginator.page(page)
        except:
            return JsonResponse({"error": "Invalid page number"}, status=400)

        pagination_data = {
            "current_page": page_obj.number,
            "total_pages": paginator.num_pages,
            "total_records": paginator.count,
            "has_previous": page_obj.has_previous(),
            "has_next": page_obj.has_next(),
            "previous_page": page_obj.previous_page_number() if page_obj.has_previous() else None,
            "next_page": page_obj.next_page_number() if page_obj.has_next() else None,
            "start_index": page_obj.start_index(),
            "end_index": page_obj.end_index(),
        }

        response_data = {
            "data": page_obj.object_list,
            "pagination": pagination_data,
            "stats": {
                "holidays": holiday_count,
                "total_working_days": total_working_days,
                "present_days": round(present_days, 1),
                "late_days": late_days,
                "half_days": half_days,
                "absent_days": round(absent_days, 1),
                "attendance_percentage": attendance_percentage,
                "total_available_leaves": round(total_available_leaves, 1),
                "yearly_total_allocated_leaves": round(sum(user_stats[u]['yearly_total_allocated_leaves'] for u in user_stats), 1),
                "yearly_total_used_leaves": round(sum(user_stats[u]['yearly_total_used_leaves'] for u in user_stats), 1),
                "all_yearly_total_allocated_leaves": round(all_yearly_total_allocated_leaves, 1),
                "all_monthly_and_weekly_available_leaves": round(all_monthly_and_weekly_available_leaves, 1)
            }
        }
        return JsonResponse(response_data, safe=False)

    except Exception as e:
        return JsonResponse({"error": f"Server error: {str(e)}"}, status=500)
    
    
    
    

@login_required
def manager_apply_leave(request):
    manager = get_object_or_404(Manager, admin_id=request.user.id)

    unread_ids = Notification.objects.filter(
        user=request.user,
        role="manager",
        is_read=False,
        notification_type="manager-leave-notification"
    ).values_list('leave_or_notification_id', flat=True)

    leave_list = LeaveReportManager.objects.filter(manager=manager).order_by('-created_at')
    paginator = Paginator(leave_list, 5)

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
            return redirect(reverse('manager_apply_leave'))

        existing_leaves = LeaveReportManager.objects.filter(
            manager=manager,
            start_date__lte=date.fromisoformat(end_date_) if end_date_ else date.fromisoformat(start_date_),
            end_date__gte=date.fromisoformat(start_date_),
            status__in=[0, 1]
        ).exists()

        if existing_leaves:
            messages.error(request, "You already applied or have approved leave for these dates.")
            return redirect(reverse('manager_apply_leave'))

        try:
            start_date = date.fromisoformat(start_date_)
            end_date = date.fromisoformat(end_date_ if end_date_ else start_date_)
            if end_date < start_date:
                messages.error(request, "End date cannot be before start date.")
                return redirect('manager_apply_leave')
        except ValueError:
            messages.error(request, "Invalid date format.")
            return redirect('manager_apply_leave')

        try:
            leave_request = LeaveReportManager.objects.create(
                manager=manager,
                leave_type=leave_type_,
                half_day_type=half_day_type_ if half_day_type_ else None,
                start_date=start_date,
                end_date=end_date,
                message=message_
            )
            messages.success(request, "Your leave request has been submitted.")

            # email content template
            email_subject = f"New Leave Request from {manager.admin.get_full_name().title()}"
            email_content = f"""
            I would like to request leave with the following details:
            
            Employee: {manager.admin.get_full_name().title()}
            Department: {manager.department.name.capitalize()}
            Leave Type: {leave_type_}
            Dates: {start_date.strftime('%d-%m-%Y')} to {end_date.strftime('%d-%m-%Y')}
            Message: {message_}
            
            Kind regards,
            {manager.admin.get_full_name().title()}
            """
            
            # notify CEO
            admin_users = CustomUser.objects.filter(is_superuser=True)
            admin_emails = list(CustomUser.objects.filter(
                is_superuser=True
            ).values_list('email', flat=True))
            
            if admin_emails:
                send_emails_in_background(
                    recipients=admin_emails,
                    subject=email_subject,
                    content=email_content,
                    from_email=manager.admin.email
                )
            
            if admin_users.exists():
                for admin_user in admin_users:
                    send_notification(admin_user, "Leave Applied", "manager-leave-notification", leave_request.id, "ceo")

            return redirect(reverse('manager_apply_leave'))
        except Exception as e:
            messages.error(request, f"Error submitting leave: {str(e)}")
            return redirect('manager_apply_leave')

    context = {
        'leave_page': leave_page,
        'unread_ids': list(unread_ids),
        'page_title': 'Apply for Leave',
    }

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        html = render_to_string("manager_template/manager_apply_leave.html", context, request=request)
        return HttpResponse(html)

    return render(request, "manager_template/manager_apply_leave.html", context)



@login_required   
def manage_employee_by_manager(request):
    manager = get_object_or_404(Manager, admin=request.user)
    search_ = request.GET.get("search", '').strip()
    gender = request.GET.get("gender", '')
    department_id = request.GET.get("department", '')
    division_id = request.GET.get("division", '')
    page_number = request.GET.get('page', 1)

    employees = Employee.objects.all().annotate(
        asset_count=Count('admin__assetsissuance'),
    ).select_related('admin', 'department', 'division', 'team_lead')

    # Apply filters
    if search_:
        employees = employees.filter(
            Q(admin__first_name__icontains=search_) |
            Q(admin__last_name__icontains=search_) |
            Q(admin__email__icontains=search_)
        )
    
    if gender:
        employees = employees.filter(admin__gender=gender)
    
    if department_id:
        employees = employees.filter(department__id=department_id)
    
    if division_id:
        employees = employees.filter(division__id=division_id)

    # Get all departments and divisions for filter dropdowns
    departments = Department.objects.all()
    divisions = Division.objects.all()

    paginator = Paginator(employees, 10)
    page_obj = paginator.get_page(page_number)

    context = {
        'employees': page_obj,
        'page_title': 'Manage Employees',
        'location_choices': dict(LOCATION_CHOICES),
        'is_paginated': page_obj.has_other_pages(),
        'search': search_,
        'departments': departments,
        'divisions': divisions,
    }

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        html = render_to_string(
            "manager_template/manage_employee_by_manager.html",
            context,
            request=request
        )
        return HttpResponse(html)

    if not employees:
        messages.warning(request, "No employees found")
    return render(request, 'manager_template/manage_employee_by_manager.html', context)


@login_required   
@require_GET
def get_asset_categories(request):
    try:
        categories = AssetCategory.objects.all()
        categories_data = [{'id': category.id, 'name': category.category} for category in categories]
        return JsonResponse({'success': True, 'categories': categories_data})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required   
@require_GET
def get_available_assets(request):
    try:
        category_id_ = request.GET.get('category_id','')
        search_ = request.GET.get('search','')

        available_assets = Assets.objects.filter(
            is_asset_issued=False,
        ).select_related('asset_category')

        if category_id_:
            available_assets = available_assets.filter(asset_category_id=category_id_)
        
        if search_:
            available_assets = available_assets.filter(
                Q(asset_name__icontains=search_) |
                Q(asset_serial_number__icontains=search_) |
                Q(asset_brand__icontains=search_)
            )

        assets_data = [{
            'id': asset.id,
            'asset_name': asset.asset_name,
            'asset_serial_number': asset.asset_serial_number,
            'asset_category': asset.asset_category.category,
            'asset_brand': asset.asset_brand,
            'status': "Available"
        } for asset in available_assets]

        
        bundle_categories = ['Laptop', 'Keyboard', 'Mouse', 'Cooling Pad', 'Monitor']
        bundle_assets = []

        for category in bundle_categories:
            asset = Assets.objects.filter(
                is_asset_issued=False,
                asset_category__category__icontains=category.lower()
            ).select_related('asset_category').first()
            if asset:
                bundle_assets.append({
                    'id': asset.id,
                    'asset_name': asset.asset_name,
                    'asset_serial_number': asset.asset_serial_number,
                    'asset_category': asset.asset_category.category,
                    'asset_brand': asset.asset_brand,
                    'status': "Available"
                })
        print(bundle_assets)
        
        return JsonResponse({'assets': assets_data,'bundle_assets': bundle_assets, 'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})



@login_required   
@require_GET
def get_assigned_assets(request):
    employee_id = request.GET.get('employee_id')
    try:
        employee = Employee.objects.get(admin_id=employee_id)
        assigned_assets = AssetsIssuance.objects.filter(
            asset_assignee=employee.admin,
        ).select_related('asset')


        assets_data = [{
            'id': issuance.asset.id,
            'asset_name': issuance.asset.asset_name,
            'asset_serial_number': issuance.asset.asset_serial_number,
            'issuance_id': issuance.id,
            'location': issuance.asset_location,
            'date_issued': issuance.date_issued.strftime('%Y-%m-%d')
        } for issuance in assigned_assets]
        
        return JsonResponse({'assets': assets_data, 'success': True})
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})



@login_required   
@csrf_exempt
@require_POST
def assign_assets(request):
    try:
        data = json.loads(request.body)
        employee_id = data.get('employee_id')
        asset_ids = data.get('asset_ids', [])
        location = data.get('location')

        if not employee_id:
            return JsonResponse({'success': False, 'error': 'Employee ID is required'})
        
        if not asset_ids:
            return JsonResponse({'success': False, 'error': 'Asset IDs are required'})

        employee = Employee.objects.get(admin_id=employee_id)

        assets = Assets.objects.filter(
            id__in=asset_ids, 
            is_asset_issued=False,
        )

        if not assets.exists():
            return JsonResponse({'success': False, 'error': 'No available assets found to assign'})

        created_issuances = []
        for asset in assets:
            issuance = AssetsIssuance.objects.create(
                asset=asset,
                asset_location=location,
                asset_assignee=employee.admin,
                assigned_by = get_object_or_404(CustomUser,id=request.user.id)
            )
            asset.is_asset_issued = True
            asset.save()

            created_issuances.append({
                'issuance_id': issuance.id,
                'asset_id': asset.id,
                'asset_name': asset.asset_name,
                'serial_number': asset.asset_serial_number
            })
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully assigned {len(created_issuances)} asset(s)',
            'issuances': created_issuances
        })
        
    except Employee.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Employee not found'})
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})



@login_required   
@csrf_exempt
@require_POST
def remove_asset_assignment(request):
    try:
        data = json.loads(request.body)
        issuance_id = data.get('issuance_id')
        asset_id = data.get('asset_id')

        # Verify the asset belongs to this manager before removal
        asset = Assets.objects.get(
            id=asset_id,
        )
        
        issuance = AssetsIssuance.objects.select_for_update().get(
            id=issuance_id,
            asset=asset
        )

        asset.return_date = timezone.now()        
        asset.is_asset_issued = False
        asset.save()

        AssetAssignmentHistory.objects.create(
            asset = asset,
            assignee = issuance.asset_assignee,
            date_assigned = issuance.date_issued,
            date_returned = timezone.now(),
            location = issuance.asset_location,
            manager = request.user
        )

        issuance.delete()
        
        return JsonResponse({
            'success': True, 
            'message': 'Asset assignment removed successfully',
            'return_date': asset.return_date.strftime('%Y-%m-%d %H:%M:%S'),
            'asset_status': asset.status 
        })
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})



@login_required   
@csrf_exempt
@require_POST
def remove_selected_asset_assignment(request):
    try:
        data = json.loads(request.body)
        assets = data.get('assets',[])

        if not assets:
            return JsonResponse({"success":False , 'error' : 'No Assets Selected for Return'})

        returned_count = 0

        for asset in assets:
            issuance_id = asset.get('issuance_id')
            asset_id = asset.get('asset_id')

            asset = Assets.objects.get(id=asset_id)
            issuance = AssetsIssuance.objects.select_for_update().get(
                id=issuance_id,
                asset=asset
            )
            asset.return_date = timezone.now()
            asset.is_asset_issued = False
            asset.save()

            AssetAssignmentHistory.objects.create(
                asset=asset,
                assignee=issuance.asset_assignee,
                date_assigned=issuance.date_issued,
                date_returned=timezone.now(),
                location=issuance.asset_location,
                manager=request.user
            )

            issuance.delete()
            returned_count += 1
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully returned {returned_count} asset(s)'
        })
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})



@login_required   
@csrf_exempt
@require_POST
def remove_all_asset_assignment(request):
    try:
        data = json.loads(request.body)
        employee_id = data.get('employee_id')

        if not employee_id:
            return JsonResponse({'success': False, 'error': 'Employee ID is required'})

        employee = Employee.objects.get(admin_id=employee_id)
        issuances = AssetsIssuance.objects.filter(asset_assignee=employee.admin).select_related('asset')

        if not issuances.exists():
            return JsonResponse({'success': False, 'error': 'No assets assigned to this employee'})

        returned_count = 0

        for issuance in issuances:
            asset = issuance.asset
            asset.return_date = timezone.now()
            asset.is_asset_issued = False
            asset.save()

            AssetAssignmentHistory.objects.create(
                asset=asset,
                assignee=issuance.asset_assignee,
                date_assigned=issuance.date_issued,
                date_returned=timezone.now(),
                location=issuance.asset_location,
                manager=request.user
            )

            issuance.delete()
            returned_count += 1
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully returned {returned_count} asset(s)'
        })
    except Employee.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Employee not found'})
    
    except Exception as e:
        return JsonResponse({'success' : False,'error' : str(e)})


@login_required   
def add_employee_by_manager(request):
    # Only managers can add employees to their department
    manager = get_object_or_404(Manager, admin=request.user)

    # Form to add a new employee
    employee_form = EmployeeForm(request.POST or None, request.FILES or None)
    context = {'form': employee_form, 'page_title': 'Add Employee'}

    if request.method == 'POST':
        if employee_form.is_valid():
            email = employee_form.cleaned_data.get('email')
            address = employee_form.cleaned_data.get('address')
            phone_number = employee_form.cleaned_data.get('phone_number')
            first_name = employee_form.cleaned_data.get('first_name')
            last_name = employee_form.cleaned_data.get('last_name')
            gender = employee_form.cleaned_data.get('gender')
            password = employee_form.cleaned_data.get('password')
            division = employee_form.cleaned_data.get('division')
            department = employee_form.cleaned_data.get('department')
            designation = employee_form.cleaned_data.get('designation')
            
            date_of_joining = employee_form.cleaned_data.get('date_of_joining')
            emergency_phone = employee_form.cleaned_data.get('emergency_phone')
            emergency_name = employee_form.cleaned_data.get('emergency_name')
            emergency_relationship = employee_form.cleaned_data.get('emergency_relationship')
            emergency_address = employee_form.cleaned_data.get('emergency_address')

            aadhar_card = employee_form.cleaned_data.get('aadhar_card')
            pan_card = employee_form.cleaned_data.get('pan_card')
            bond_start = employee_form.cleaned_data.get('bond_start')
            bond_end = employee_form.cleaned_data.get('bond_end')
            

            passport_url = None

            if 'profile_pic' in request.FILES:
                passport = request.FILES['profile_pic']
                fs = FileSystemStorage()
                filename = fs.save(passport.name, passport)
                passport_url = fs.url(filename)

            try:
                # Create the user (employee)
                user = CustomUser.objects.create_user(
                    email=email, 
                    password=password, 
                    user_type=3, 
                    first_name=first_name, 
                    last_name=last_name, 
                    profile_pic=passport_url if passport_url else ""
                )
                user.gender = gender
                user.address = address
                user.save()

                employee = user.employee
                employee.division = division
                employee.department = department
                employee.team_lead = manager  # Assign manager as the team lead
                employee.phone_number = phone_number
                employee.designation = designation
                employee.date_of_joining = date_of_joining

                emergency_contact = {
                    "name" : emergency_name or "",
                    "relationship" : emergency_relationship or "",
                    "phone" : emergency_phone or "",
                    "address" : emergency_address or ""
                }

                employee.emergency_contact = emergency_contact
                employee.aadhar_card = aadhar_card
                employee.pan_card = pan_card
                employee.bond_start = bond_start
                employee.bond_end = bond_end
                
                employee.save()

                messages.success(request, "Successfully Added Employee")
                return redirect(reverse('manage_employee_by_manager'))  # Redirect to employee management page
            except Exception as e:
                messages.error(request, "Could Not Add Employee: " + str(e))
        else:
            messages.error(request, "Please fill all the details correctly.")

    return render(request, 'manager_template/add_employee_by_manager.html', context)


@login_required
def view_employee_by_manager(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)
    context = {
        'employee': employee,
        'page_title': f'Profile - {employee}'
    }
    return render(request, 'ceo_template/view_employee.html' , context)


@login_required   
def edit_employee_by_manager(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)
    
    # if employee.team_lead != request.user.manager:
    #     messages.error(request, "You do not have permission to edit this employee.")
    #     return redirect('manage_employee_by_manager')

    form = EmployeeForm(request.POST or None, instance=employee)
    context = {
        'form': form,
        'employee_id': employee_id,
        'user_object': employee,
        'page_title': 'Edit Employee'
    }

    if request.method == 'POST':
        if form.is_valid():
            first_name = form.cleaned_data.get('first_name')
            last_name = form.cleaned_data.get('last_name')
            address = form.cleaned_data.get('address')
            username = form.cleaned_data.get('username')
            email = form.cleaned_data.get('email')
            gender = form.cleaned_data.get('gender')
            password = form.cleaned_data.get('password') or None
            division = form.cleaned_data.get('division')
            department = form.cleaned_data.get('department')
            designation = form.cleaned_data.get('designation')
            phone_number = form.cleaned_data.get('phone_number')
            team_lead = form.cleaned_data.get('team_lead')
            passport = request.FILES.get('profile_pic') or None

            emergency_name = form.cleaned_data.get('emergency_name')
            emergency_relationship = form.cleaned_data.get('emergency_relationship')
            emergency_phone = form.cleaned_data.get('emergency_phone')
            emergency_address = form.cleaned_data.get('emergency_address')

            aadhar_card = form.cleaned_data.get('aadhar_card')
            pan_card = form.cleaned_data.get('pan_card')
            bond_start = form.cleaned_data.get('bond_start')
            bond_end = form.cleaned_data.get('bond_end')
            is_second_shift = form.cleaned_data.get('is_second_shift')

            try:
                if emergency_phone and (not emergency_phone.isdigit() or len(emergency_phone) != 10):
                    raise ValidationError("Emergency phone number must be exactly 10 digits.")

                # Get the related CustomUser instance
                user = CustomUser.objects.get(id=employee.admin.id)

                # Update profile picture if provided
                if passport:
                    fs = FileSystemStorage()
                    filename = fs.save(passport.name, passport)
                    passport_url = fs.url(filename)
                    user.profile_pic = passport_url

                # Update the CustomUser fields
                user.username = username
                user.email = email
                if password:
                    user.set_password(password)
                user.first_name = first_name
                user.last_name = last_name
                user.gender = gender
                user.address = address
                user.is_second_shift = is_second_shift

                # Save the CustomUser instance
                user.save()

                # Update the Employee model fields
                employee.division = division
                employee.department = department
                employee.designation = designation
                employee.phone_number = phone_number
                employee.team_lead = team_lead

                # Update emergency contact information
                employee.emergency_contact = {
                    'name': emergency_name or "Not provided",
                    'relationship': emergency_relationship or "Not provided",
                    'phone': emergency_phone or "Not provided",
                    'address': emergency_address or "Not provided"
                }
                employee.aadhar_card = aadhar_card
                employee.pan_card = pan_card
                employee.bond_start = bond_start
                employee.bond_end = bond_end

                employee.save()

                messages.success(request, "Employee information updated successfully.")
                return redirect(reverse('manage_employee_by_manager'))
            except Exception as e:
                messages.error(request, "Could not update employee: " + str(e))
        else:
            messages.error(request, "Please fill out the form correctly.")

    return render(request, 'manager_template/edit_employee_by_manager.html', context)


@login_required   
def delete_employee_by_manager(request, employee_id):
    # Get the employee object
    employee = get_object_or_404(Employee, id=employee_id)

    # Ensure that the logged-in manager is the team lead of the employee
    if employee.team_lead != request.user.manager:
        messages.error(request, "You do not have permission to delete this employee.")
        return redirect('manage_employee_by_manager')
   
    issuances = AssetsIssuance.objects.filter(asset_assignee=employee.admin)
    if issuances.exists():
        for issuance in issuances:
            asset = issuance.asset
            asset.is_asset_issued = False
            asset.return_date = timezone.now()
            asset.save()

            AssetAssignmentHistory.objects.create(
                asset=asset,
                assignee=issuance.asset_assignee,
                manager=request.user,
                date_assigned=issuance.date_issued,
                date_returned=timezone.now(),
                location=issuance.asset_location,
                notes="Automatically returned due to employee deletion"
            )
            # delete issuance record
            issuance.delete()

    # Delete the employee
    user = employee.admin
    employee.delete()
    if user:
        user.delete()

    messages.success(request, "Employee deleted successfully.")
    return redirect(reverse('manage_employee_by_manager'))


@login_required   
def manager_feedback(request):
    form = FeedbackManagerForm(request.POST or None)
    manager = get_object_or_404(Manager, admin_id=request.user.id)
    feedbacks_list = FeedbackManager.objects.filter(manager=manager).order_by('-created_at')
    paginator = Paginator(feedbacks_list, 5)  # 5 items per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context = {
        'form': form,
        'page_obj': page_obj,
        'page_title': 'Add Feedback'
    }
    if request.method == 'POST':
        if form.is_valid():
            try:
                obj = form.save(commit=False)
                obj.manager = manager
                obj.save()
                messages.success(request, "Feedback submitted for review")
                return redirect(reverse('manager_feedback'))
            except Exception:
                messages.error(request, "Could not Submit!")
        else:
            messages.error(request, "Form has errors!")
    
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        html = render_to_string(
            'manager_template/manager_feedback.html',
            context,
            request=request
        )
        return HttpResponse(html)
    
    return render(request, 'manager_template/manager_feedback.html', context)


@login_required
def manager_notify_employee(request):
    employee_list = CustomUser.objects.filter(user_type=3)
    
    paginator = Paginator(employee_list, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_title': "Send Notifications To Employees",
        'employees': page_obj,
    }

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        html = render_to_string(
            "manager_template/employee_notification.html",
            context,
            request=request
        )
        return JsonResponse({'success': True, 'html': html})

    return render(request, "manager_template/employee_notification.html", context)


@login_required
@csrf_exempt
def manager_send_employee_notification(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=405)
    
    id = request.POST.get('id')
    message = request.POST.get('message', '').strip()
    
    if not message:
        return JsonResponse({'success': False, 'message': 'Message cannot be empty'}, status=400)
    
    try:
        # Retrieve CustomUser and corresponding Employee
        user = get_object_or_404(CustomUser, id=id, user_type=3)
        employee = get_object_or_404(Employee, admin=user)
        notification = NotificationEmployee(employee=employee, message=message, created_by=request.user)
        notification.save()
        
        # Assuming send_notification is a custom function; ensure it's defined
        try:
            send_notification(user, message, "notification-from-manager", notification.id, "employee")
        except Exception as e:
            print(f"send_notification failed: {str(e)}")
        
        return JsonResponse({'success': True, 'message': 'Notification sent successfully'})
    except Exception as e:
        print(f"Error: {str(e)}")
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@login_required
@csrf_exempt
def send_bulk_employee_notification_by_manager(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=405)
    
    message = request.POST.get('message', '').strip()
    
    if not message:
        return JsonResponse({'success': False, 'message': 'Message cannot be empty'}, status=400)
    
    try:
        employees = Employee.objects.all()
        if not employees.exists():
            return JsonResponse({'success': False, 'message': 'No employees found'}, status=400)
        
        for employee in employees:
            user = employee.admin
            notification = NotificationEmployee(employee=employee, message=message, created_by=request.user)
            notification.save()
            try:
                send_notification(user, message, "notification-from-manager", notification.id, "employee")
            except Exception as e:
                print(f"send_notification failed: {str(e)}")
        
        return JsonResponse({'success': True, 'message': 'Bulk notification sent successfully'})
    except Exception as e:
        print(f"Error: {str(e)}")
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

@login_required
@csrf_exempt
def send_selected_employee_notification_by_manager(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=405)
    
    message = request.POST.get('message', '').strip()
    try:
        employee_ids = json.loads(request.POST.get('employee_ids', '[]'))
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'Invalid employee IDs format'}, status=400)
    
    if not message:
        return JsonResponse({'success': False, 'message': 'Message cannot be empty'}, status=400)
    
    if not employee_ids:
        return JsonResponse({'success': False, 'message': 'No employees selected'}, status=400)
    
    try:
        for emp_id in employee_ids:
            employee = get_object_or_404(Employee, admin_id=emp_id)
            user = employee.admin
            notification = NotificationEmployee(employee=employee, message=message, created_by=request.user)
            notification.save()

            try:
                send_notification(user, message, "notification-from-manager", notification.id, "employee")
            except Exception as e:
                print(f"send_notification failed: {str(e)}")
        
        return JsonResponse({'success': True, 'message': 'Notification sent to selected employees'})
    except Exception as e:
        print(f"Error: {str(e)}")
        return JsonResponse({'success': False, 'message': str(e)}, status=500)



logger = logging.getLogger(__name__)

@login_required
def manager_view_profile(request):
    manager = get_object_or_404(Manager, admin=request.user)
    form = ManagerEditForm(request.POST or None, request.FILES or None, instance=manager)
    context = {'form': form, 'page_title': 'View/Update Profile', 'user_object': manager.admin}
    
    if request.method == 'POST':
        try:
            if form.is_valid():
                first_name = form.cleaned_data.get('first_name')
                last_name = form.cleaned_data.get('last_name')
                email = form.cleaned_data.get('email')
                password = form.cleaned_data.get('password') or None
                address = form.cleaned_data.get('address')
                gender = form.cleaned_data.get('gender')
                passport = request.FILES.get('profile_pic') or None
                admin = manager.admin
                
                # Track if any changes were made
                changes_made = False
                
                # Update email
                if email and email != admin.email:
                    admin.email = email.lower()
                    logger.info(f"Email updated for user {admin.username} to {email}")
                    changes_made = True
                
                # Update password only if provided and non-empty
                if password and password.strip():
                    admin.set_password(password)
                    update_session_auth_hash(request, admin)
                    logger.info(f"Password updated for user {admin.username}, session updated")
                    changes_made = True
                
                if passport is not None:
                    fs = FileSystemStorage()
                    safe_filename = get_valid_filename(passport.name)
                    filename = fs.save(safe_filename, passport)
                    passport_url = fs.url(filename)
                    admin.profile_pic = passport_url
                    logger.info(f"Profile picture updated for user {admin.username}: {passport_url}")
                    changes_made = True
                
                # Update other fields if changed
                if admin.first_name != first_name:
                    admin.first_name = first_name
                    changes_made = True
                if admin.last_name != last_name:
                    admin.last_name = last_name
                    changes_made = True
                if admin.address != address:
                    admin.address = address
                    changes_made = True
                if admin.gender != gender:
                    admin.gender = gender
                    changes_made = True
                
                # Save only if changes were made
                if changes_made:
                    admin.save()
                    manager.save()
                    messages.success(request, "Profile updated successfully!")
                    logger.info(f"Profile update successful for user {admin.username}")
                    return redirect(reverse('manager_view_profile'))
                else:
                    
                    logger.info(f"No changes made for user {admin.username}")
                    return redirect(reverse('manager_view_profile'))
            else:
                messages.error(request, "Invalid Data Provided")
                logger.warning(f"Invalid form data for user {request.user.username}")
                return render(request, "manager_template/manager_view_profile.html", context)
        except Exception as e:
            logger.error(f"Error updating profile for user {request.user.username}: {str(e)}")
            messages.error(request, "Error Occurred While Updating Profile: " + str(e))
            return render(request, "manager_template/manager_view_profile.html", context)

    return render(request, "manager_template/manager_view_profile.html", context)



@login_required   
@csrf_exempt
def manager_fcmtoken(request):
    token = request.POST.get('token')
    try:
        manager_user = get_object_or_404(CustomUser, id=request.user.id)
        manager_user.fcm_token = token
        manager_user.save()
        return HttpResponse("True")
    except Exception as e:
        return HttpResponse("False")



@login_required   
def manager_view_notification(request):
    manager = get_object_or_404(Manager, admin=request.user)
    manager_department = manager.department.name.lower().strip()

    # notification from admin
    notification_from_admin = NotificationManager.objects.filter(manager=manager).order_by('-created_at')

    # Get all unread notifications for manager
    unread_notifications = Notification.objects.filter(
        user=request.user,
        role="manager",
        is_read=False
    ).order_by('-timestamp')

    leave_request_from_employee_notification = unread_notifications.filter(notification_type='leave-notification')

    general_request_from_admin_notification = unread_notifications.filter(notification_type='general-notification',user=request.user)

    clockout_request_from_employee_notification = unread_notifications.filter(notification_type='clockout-notification')

    # Handle "Mark All as Read"
    if request.method == 'POST' and request.POST.get('mark_all_read'):
        with transaction.atomic():
            Notification.objects.filter(
                user=request.user,
                role="manager",
                notification_type="general-notification",
                is_read=False
            ).update(is_read=True)

    # Pending and history for early clock-out requests
    pending_early_clock_out_requests = EarylyClockOutRequest.objects.filter(status='pending').order_by('-submitted_at')
    early_clock_out_history = EarylyClockOutRequest.objects.filter(status__in=['approved', 'denied']).order_by('-reviewed_at')

    # Pending and history
    if manager_department in ['hr','h r']:
        pending_leave_requests = LeaveReportEmployee.objects.filter(status=0).order_by('-created_at')
    else:
        pending_leave_requests = LeaveReportEmployee.objects.filter(
            status=0,
            employee__department=manager.department
        ).order_by('-created_at')

    leave_history = LeaveReportEmployee.objects.filter(status__in=[1, 2]).order_by('-updated_at')

    # Pagination
    notification_from_admin_paginator = Paginator(notification_from_admin, 3)
    leave_paginator = Paginator(leave_history, 3)
    early_clock_out_paginator = Paginator(early_clock_out_history, 3)
    early_clock_out_requests_paginator = Paginator(pending_early_clock_out_requests, 3)

    # Get page Numbers
    notification_from_admin_obj = request.GET.get('notification_from_admin_obj')
    leave_notification_page = request.GET.get('leave_notification_page')
    leave_page_number = request.GET.get('leave_history_page')
    early_clock_out_page_number = request.GET.get('early_clock_out_history_page')
    early_clock_out_requests_page = request.GET.get('early_clock_out_requests_page')

    # IDs for Highlighting
    leave_unread_ids = pending_leave_requests.values_list('id',flat=True)
    pending_early_clockout_ids = pending_early_clock_out_requests.values_list('id',flat=True)
    # notification_from_admin_ids = notification_from_admin.values_list('id',flat=True)

    notification_unread_ids = Notification.objects.filter(
        user=request.user,
        role="manager",
        notification_type="general-notification",
        is_read=False
    ).values_list('leave_or_notification_id', flat=True)

    context = {
        
        'notification_from_admin_obj' : notification_from_admin_paginator.get_page(notification_from_admin_obj),
        'pending_leave_requests': pending_leave_requests,
        'leave_history': leave_paginator.get_page(leave_page_number),
        'pending_early_clock_out_requests': early_clock_out_requests_paginator.get_page(early_clock_out_requests_page),
        'early_clock_out_history': early_clock_out_paginator.get_page(early_clock_out_page_number),
        'page_title': "View Notifications",
        'LOCATION_CHOICES': LOCATION_CHOICES,

        'leave_unread_ids' : list(leave_unread_ids),
        'pending_early_clockout_ids' : list(pending_early_clockout_ids),
        'notification_from_admin_ids' : list(notification_unread_ids),
    }

    return render(request, "manager_template/manager_view_notification.html", context)

@login_required
@csrf_exempt
def manager_view_by_employee_feedback_message(request):
    if request.method != 'POST':
        # Handle GET request to display feedback list
        feedback_list = FeedbackEmployee.objects.all().order_by('-id')
        page = request.GET.get('page', 1)
        paginator = Paginator(feedback_list, 10)
        try:
            feedbacks = paginator.page(page)
        except PageNotAnInteger:
            feedbacks = paginator.page(1)
        except EmptyPage:
            feedbacks = paginator.page(paginator.num_pages)

        unread_ids = list(
            Notification.objects.filter(
                user=request.user,
                is_read=False,
                notification_type='employee feedback'
            ).values_list('leave_or_notification_id', flat=True)
        )

        context = {
            'feedbacks': feedbacks,
            'page_title': 'Employee Feedback Messages',
            'unread_ids': unread_ids
        }

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string(
                'manager_template/manager_view_by_employee_feedback_template.html',
                context,
                request=request
            )
            return JsonResponse({'success': True, 'html': html})

        return render(request, 'manager_template/manager_view_by_employee_feedback_template.html', context)

    # Handle POST request
    if request.POST.get('_method') == 'DELETE':
        feedback_ids = request.POST.getlist('ids[]')
        action = request.POST.get('action')

        try:
            if action == 'delete_all':
                FeedbackEmployee.objects.all().delete()
                Notification.objects.filter(
                    notification_type='employee feedback'
                ).delete()
                return JsonResponse({'success': True, 'message': 'All feedback deleted successfully'})
            elif feedback_ids:
                FeedbackEmployee.objects.filter(id__in=feedback_ids).delete()
                Notification.objects.filter(
                    leave_or_notification_id__in=feedback_ids,
                    notification_type='employee feedback'
                ).delete()
                return JsonResponse({'success': True, 'message': f'Deleted {len(feedback_ids)} feedback entries'})
            else:
                return JsonResponse({'success': False, 'message': 'No feedback IDs provided'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)

    # Handle feedback reply
    feedback_id = request.POST.get('id')
    try:
        feedback = get_object_or_404(FeedbackEmployee, id=feedback_id)
        reply = request.POST.get('reply')
        feedback.reply = reply
        feedback.updated_at = timezone.now()
        feedback.save()
        
        notify = Notification.objects.filter(
            user=request.user,
            role="admin",
            is_read=False,
            leave_or_notification_id=feedback_id,
            notification_type='employee feedback'
        ).first()
        
        if notify:
            notify.is_read = True
            notify.save()
            
        return JsonResponse({
            'success': True,
            'message': 'Reply sent successfully',
            'reply': feedback.reply,
            'updated_at': feedback.updated_at.strftime('%b %d, %Y %H:%M')
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)
    
    
@login_required
@csrf_exempt
def manager_view_by_employee_leave(request):
    if request.method != 'POST':
        all_leave = LeaveReportEmployee.objects.all().order_by('-created_at')
        paginator = Paginator(all_leave, 10)  
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        context = {
            'allLeave': page_obj,
            'page_title': 'Leave Applications From Employees'
        }

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string(
                "manager_template/manager_view_by_employee_leave_view.html",
                context,
                request=request
            )
            return HttpResponse(html)

        return render(request, "manager_template/manager_view_by_employee_leave_view.html", context)
    else:
        id = request.POST.get('id')
        status = request.POST.get('status')
        status = 1 if status == '1' else -1
        try:
            leave = get_object_or_404(LeaveReportEmployee, id=id)
            leave.status = status
            leave.save()
            return HttpResponse("True")
        except Exception:
            return HttpResponse("False")


@login_required   
def manager_asset_view_notification(request):
    manager = get_object_or_404(Manager, admin=request.user)
    manager_department = manager.department.name.lower().strip()

    if manager_department in ['hr','h r']:
        # Recently resolved recurring asset issues
        all_resolved_recurring = AssetIssue.objects.filter(
            status='resolved',
        ).order_by('-resolved_date')[:5]

        # Asset claim notifications pending approval
        pending_asset_notifications = Notify_Manager.objects.filter(
            # manager=request.user,
            approved__isnull=True
        ).order_by('-timestamp')
        print(pending_asset_notifications)

        # Get all unread notifications for manager
        unread_notifications = Notification.objects.filter(
            # user=request.user,
            role="manager",
            is_read=False,
            notification_type = 'asset-notification'
        ).values_list('leave_or_notification_id' , flat=True)

        ## Asset claim notification history 
        asset_notification_history = Notify_Manager.objects.filter(
            manager = request.user,
        ).exclude(approved__isnull=True).order_by('-timestamp')

        # Asset issues with pending or in-progress status
        pending_asset_issues = AssetIssue.objects.filter(
            status__in=['pending', 'in_progress']
        ).order_by('-reported_date')

        # Pagination for asset claim notifications
        asset_notification_paginator = Paginator(pending_asset_notifications, 5)
        asset_notification_page_obj = asset_notification_paginator.get_page(request.GET.get('asset_page'))

        # Pagination for asset ckain notification history
        asset_history_claim_notication_paginator = Paginator(asset_notification_history,5)
        asset_history_claim_notication_obj = asset_history_claim_notication_paginator.get_page(request.GET.get('asset_claim_notification_history'))
        print(asset_history_claim_notication_obj)

        # Pagination for resolved recurring issues
        resolved_issues_paginator = Paginator(all_resolved_recurring, 5)
        resolved_issues_page_obj = resolved_issues_paginator.get_page(request.GET.get('resolved_page'))
        # IDs of unread notifications for potential frontend use
        manager_unread_ids = pending_asset_notifications.values_list('id', flat=True)

        # Count of unread asset-related notifications
        unread_asset_notification_count = pending_asset_notifications.count() + pending_asset_issues.count()

        context = {
            'asset_notifications': pending_asset_notifications,
            'asset_issue_notifications': pending_asset_issues,
            'pending_issue': pending_asset_issues.filter(status='pending'),
            'in_progress_issue': pending_asset_issues.filter(status='in_progress'),
            'all_resolved_recurring': all_resolved_recurring,
            'asset_notification_page_obj': asset_notification_page_obj,
            'resolved_issues_page_obj': resolved_issues_page_obj,
            'page_title': "Asset Notifications",
            'manager_unread_ids': manager_unread_ids,
            'LOCATION_CHOICES': LOCATION_CHOICES,
            'unread_asset_notification_count': unread_asset_notification_count,
            'unread_asset_request_count': pending_asset_notifications.count(),
            'unread_asset_issue_count': pending_asset_issues.count(),
            'asset_history_claim_notication_obj' : asset_history_claim_notication_obj,
            'unread_notifications' : list(unread_notifications)
        }

        return render(request, "manager_template/manager_asset_view_notification.html", context)
    else:
        return render(request, "manager_template/manager_asset_view_notification.html")




@login_required   
def approve_assest_request(request, notification_id):
    if request.method == 'POST':
        asset_location_  = request.POST.get("asset_location" , "Main Room")
        notification = get_object_or_404(Notify_Manager, id=notification_id)

        if notification.approved is None or notification.approved is False:
            asset = notification.asset
            employee = notification.employee 

            # check if asset is already assigned to someone
            if asset.is_asset_issued == True:
                messages.warning(request,'This asset is already assigned to another employee.')
                return redirect('manager_asset_view_notification')
            try:
                AssetsIssuance.objects.create(
                    asset=asset,
                    asset_location=asset_location_,
                    asset_assignee=employee,
                    assigned_by = request.user
                )
            
                my_asset = Assets.objects.get(id=asset.id)
                # my_asset.manager = request.user
                my_asset.is_asset_issued = True
                my_asset.save()
                notification.approved = True
                notification.save()
                messages.success(request, "Asset request approved successfully.")
                    
                # Update existing notifications for the employee to mark as read
                Notification.objects.filter(
                    notification_type__in = ['asset-notification'],
                    leave_or_notification_id = notification.id,
                    is_read = False 
                ).update(is_read=True)
                
                # Send notification to employee
                employee_user = notification.employee.id

                Notification.objects.create(
                    user=get_object_or_404(CustomUser , id=employee_user),
                    message="Asset request approved.",
                    notification_type="asset-notification",
                    leave_or_notification_id=notification.id,
                    role="employee"
                )

            except:
                messages.error(request,"This Asset is not Found in Inventry")

        else:
            messages.info(request, "This request was already approved.")

    return redirect('manager_asset_view_notification')




@login_required   
def reject_assest_request(request, notification_id):
    notification = get_object_or_404(Notify_Manager, id=notification_id)
    if notification.approved is None or notification.approved is False:
        notification.approved = False
        notification.save()
        messages.success(request, "Asset request rejected successfully.")
        
        # Update existing notifications for the employee to mark as read
        Notification.objects.filter(
            notification_type__in = ['asset-notification'],
            leave_or_notification_id = notification.id,
            is_read = False 
        ).update(is_read=True)
        
        # Send notification to employee
        employee_user_id = notification.employee.id

        Notification.objects.create(
            user=get_object_or_404(CustomUser , id=employee_user_id),
            message="Asset request rejected.",
            notification_type="asset-notification",
            leave_or_notification_id=notification.id,
            role="employee"
        )
        notification.save()
    else:
        messages.info(request, "This request was already approved or rejected.")

    return redirect('manager_asset_view_notification')




@login_required
def approve_leave_request(request, leave_id):
    if request.method == 'POST':
        try:
            leave = get_object_or_404(LeaveReportEmployee, id=leave_id)
            if leave.status != 0:  # 0 = Pending
                messages.info(request, "This leave request has already been processed.")
                return redirect('manager_view_notification')
 
            employee = leave.employee
            start_date = leave.start_date
            end_date = leave.end_date or start_date
            leave_amount = 0.5 if leave.leave_type == 'Half-Day' else 1.0
 
            # Process leave approval
            with transaction.atomic():
                current_date = start_date
                while current_date <= end_date:
                    # Deduct leave
                    success, remaining_leaves = LeaveBalance.deduct_leave(employee, current_date, leave.leave_type)
                    if not success:
                        logger.error(f"Failed to deduct leave for {current_date}")
                        messages.error(request, f"Failed to deduct leave for {current_date.strftime('%d-%m-%Y')}")
                        return redirect('manager_view_notification')
 
                    #  for half-day leaves , just mark as approved but don't create attendance record
 
                    if leave.leave_type == 'Full-Day':
                        # for full_day leaves, create attendance record
                        record, created = AttendanceRecord.objects.update_or_create(
                            user=employee.admin,
                            date=current_date,
                            defaults={
                                'status': 'leave',
                                'department': employee.department,
                                'clock_in': None,
                                'clock_out': None,
                                'total_worked': None,
                                'regular_hours': None,
                                'overtime_hours': None
                            }
                        )
 
                    current_date += timedelta(days=1)
 
                # Update leave status to Approved
                leave.status = 1
                leave.save()
 
                if leave.leave_type == 'Half-Day':
                    messages.success(request, "Half-Day leave approved.")
                else:
                    messages.success(request, "Full-Day leave approved.")
                msg = "Leave request Approved."
 
                # Update existing notifications for the employee to mark as read
                Notification.objects.filter(
                    notification_type__in = ['leave-notification' , 'employee-leave-notification'],
                    leave_or_notification_id = leave.id,
                    is_read = False
                ).update(is_read=True)
                
                # Send notification to employee
                employee_user = leave.employee.admin
                Notification.objects.create(
                    user=employee_user,
                    message=msg,
                    notification_type="leave-notification",
                    leave_or_notification_id=leave_id,
                    role="employee"
                )
 
            return redirect('manager_view_notification')
 
        except Exception as e:
            logger.error(f"Error approving leave ID {leave_id}: {str(e)}")
            messages.error(request, "Error approving leave")
            return redirect('manager_view_notification')
        
    return redirect('manager_view_notification')
            
 
 
            

@login_required   
def reject_leave_request(request, leave_id):
    if request.method == 'POST':
        leave_request = get_object_or_404(LeaveReportEmployee, id=leave_id)
        
        if leave_request.status == 0:
            leave_request.status = 2
            leave_request.save()
            msg = "Leave request rejected."
            messages.warning(request, msg)

            # Update existing notifications for the employee to mark as read
            Notification.objects.filter(
                notification_type__in = ['leave-notification' , 'employee-leave-notification'],
                leave_or_notification_id = leave_request.id,
                is_read = False 
            ).update(is_read=True)

            # Send notification to employee
            employee_user = leave_request.employee.admin
            Notification.objects.create(
                user=employee_user,
                message=msg,
                notification_type="leave-notification",
                leave_or_notification_id=leave_id,
                role="employee"
            )
            
        else:
            messages.info(request, "This leave request has already been processed.")
    return redirect('manager_view_notification')


@login_required   
def manager_add_salary(request):
    manager = get_object_or_404(Manager, admin=request.user)
    departments = Department.objects.filter(division=manager.division)
    context = {
        'page_title': 'Salary Upload',
        'departments': departments
    }
    if request.method == 'POST':
        try:
            employee_id = request.POST.get('employee_list')
            department_id = request.POST.get('department')
            base = request.POST.get('base')
            ctc = request.POST.get('ctc')
            employee = get_object_or_404(Employee, id=employee_id)
            department = get_object_or_404(Department, id=department_id)
            try:
                data = EmployeeSalary.objects.get(
                    employee=employee, department=department)
                data.ctc = ctc
                data.base = base
                data.save()
                messages.success(request, "Scores Updated")
            except:
                salary = EmployeeSalary(employee=employee, department=department, base=base, ctc=ctc)
                salary.save()
                messages.success(request, "Scores Saved")
        except Exception as e:
            messages.warning(request, "Error Occured While Processing Form")
    return render(request, "manager_template/manager_add_salary.html", context)


@login_required   
def resolve_asset_issue(request,asset_issu_id):
    if request.method == "POST":
        issue_asset = get_object_or_404(AssetIssue,pk=asset_issu_id)
        issue_asset.status = request.POST.get('status')
        issue_asset.notes = request.POST.get('notes')
        issue_asset.resolution_method = request.POST.get('resolution_method')
        issue_asset.is_recurring = request.POST.get('is_recurring') == "on"
        issue_asset.resolved_date = datetime.now()
        issue_asset.save()

        if issue_asset.status in ["resolved" , 'in_progress']:
            # Update existing notifications for the employee to mark as read
            if issue_asset.status == 'resolved':
                Notification.objects.filter(
                    notification_type__in = ['asset-notification'],
                    leave_or_notification_id = issue_asset.id,
                    is_read = False 
                ).update(is_read=True)
            
            # Send notification to employee
            employee_user = issue_asset.reported_by

            Notification.objects.create(
                user=employee_user,
                message=issue_asset.notes,
                notification_type="asset-notification",
                leave_or_notification_id=issue_asset.id,
                role="employee"
            
            )
        messages.success(request,f"Asset Issue {issue_asset.status}!!")
    
    return redirect('manager_asset_view_notification')


@login_required   
@csrf_exempt
def fetch_employee_salary(request):
    try:
        department_id = request.POST.get('department')
        employee_id = request.POST.get('employee')
        employee = get_object_or_404(Employee, id=employee_id)
        department = get_object_or_404(Department, id=department_id)
        salary = EmployeeSalary.objects.get(employee=employee, department=department)
        salary_data = {
            'ctc': salary.ctc,
            'base': salary.base
        }
        return HttpResponse(json.dumps(salary_data))
    except Exception as e:
        return HttpResponse('False')
    
    
    
