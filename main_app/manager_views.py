import json
from django.contrib import messages
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404,redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from main_app.notification_badge import send_notification
from .forms import *
from .models import *
from asset_app.models import Notify_Manager,AssetsIssuance,Assets,LOCATION_CHOICES,AssetAssignmentHistory
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET, require_POST
from asset_app.models import AssetIssue
from .models import CustomUser
from django.utils.timezone import localtime
from django.templatetags.static import static
import requests
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from datetime import datetime, time, timedelta
from django.core.paginator import Paginator
from django.forms.models import model_to_dict
from django.http import JsonResponse
from datetime import datetime



LOCATION_CHOICES = (
    ("Main Room" , "Main Room"),
    ("Meeting Room", "Meeting Room"),
    ("Main Office", "Main Office"),
)

def manager_home(request):
    manager = get_object_or_404(Manager, admin=request.user)
    
    today = date.today()
    current_time = timezone.now()

    predefined_names = ['Python Department', 'React JS Department', 'Node JS Department']
    all_departments = Department.objects.all()

    selected_department = request.GET.get('department', 'all').strip().lower()
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    employees = CustomUser.objects.filter(user_type=3)  
    normalized_predefined = [name.lower() for name in predefined_names]

    if selected_department != 'all':
        if selected_department == 'others':
            employees = employees.exclude(employee__department__name__in=predefined_names)
        else:
            employees = employees.filter(employee__department__name__iexact=selected_department.title())

    employee_ids = employees.values_list('id', flat=True)
    filtered_records = AttendanceRecord.objects.filter(user_id__in=employee_ids)
    
    on_break_now = Break.objects.filter(
        attendance_record__user__in=employee_ids,
        break_start__date=today,
        break_start__lte=current_time,
    ).filter(models.Q(break_end__isnull=True) | models.Q(break_end__gte=current_time)).distinct()

    total_on_break = on_break_now.count()

    if start_date and end_date:
        date_range = [parse_date(start_date), parse_date(end_date)]
        filtered_records = filtered_records.filter(date__range=date_range)

    time_history_data = []
    break_entries = []
    
    for employee in employees:
        emp_records = filtered_records.filter(user=employee)
        total_present = emp_records.filter(status='present').count()
        total_late = emp_records.filter(status='late').count()

        emp_leaves = LeaveReportEmployee.objects.filter(employee__admin=employee)
        if start_date and end_date:
            emp_leaves = emp_leaves.filter(
                start_date__lte=parse_date(end_date),
                end_date__gte=parse_date(start_date)
            )
        total_leave = emp_leaves.count()
    
        emp_breaks = Break.objects.filter(
            attendance_record__user=employee,
            break_start__date=today
        ).order_by('break_start')

        for b in emp_breaks:
            if b.break_end:
                duration = int((b.break_end - b.break_start).total_seconds() / 60)
            else:
                duration = 0 

            break_entries.append({
                'employee_id': employee.id,
                'employee_name': employee.get_full_name(),
                'department': employee.employee.department.name if hasattr(employee, 'employee') and employee.employee.department else '',
                'break_start': localtime(b.break_start).strftime('%H:%M'),
                'break_end': localtime(b.break_end).strftime('%H:%M') if b.break_end else 'Ongoing',
                'break_duration': duration,
            })
            # print("break_entries:>>>>",break_entries)
            # After the loop that appends to break_entries
        if break_entries:
            break_entries = sorted(break_entries, key=lambda x: x['break_start'], reverse=True)
        print("break_entries:>>>>",break_entries)
        time_history_data.append({
            'employee_name': employee.get_full_name(),
            'department': employee.employee.department.name if hasattr(employee, 'employee') and employee.employee.department else '',
            'present': total_present,
            'late': total_late,
            'leave': total_leave,
            'working_days': total_present + total_late,
        })

    context = {
        'page_title': f"Manager Panel - {manager.admin.last_name} ({manager.division})",
        'departments': all_departments,
        'time_history_data': time_history_data,
        'selected_department': selected_department,
        'start_date': start_date,
        'end_date': end_date,
        'total_employees': employees.count(),
        'total_attendance': filtered_records.count(),
        'total_leave': sum(item['leave'] for item in time_history_data),
        'total_department': all_departments.count(),
        'total_on_break' : total_on_break,
        'break_entries': break_entries,
    }
    return render(request, 'manager_template/home_content.html', context)

def manager_take_attendance(request):
    manager = get_object_or_404(Manager, admin=request.user)
    print("manager",manager)
    departments = Department.objects.filter(division=manager.division)
    context = {
        'departments': departments,
        'page_title': 'Take Attendance',
    }
    return render(request, 'manager_template/manager_take_attendance.html', context)


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
                "name": employee.admin.last_name + " " + employee.admin.first_name
            }
            employee_data.append(data)
        return JsonResponse(json.dumps(employee_data), content_type='application/json', safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


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
                "name": manager.admin.last_name + " " + manager.admin.first_name
            }
            manager_data.append(data)
        return JsonResponse(json.dumps(manager_data), content_type='application/json', safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

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


# For displaying the update page
# def manager_update_attendance(request):
#     manager = get_object_or_404(Manager, admin=request.user)
#     # employees = Employee.objects.filter(department__in=departments)
#     departments = Department.objects.filter(division=manager.division)
#     context = {
#         'departments': departments,
#         # 'employees': employees,
#         'page_title': 'Update Attendance'
#     }
#     return render(request, 'manager_template/manager_update_attendance.html', context)

# from datetime import datetime


def manager_update_attendance(request):
    manager = get_object_or_404(Manager, admin=request.user)
    departments = Department.objects.filter(division=manager.division)
    employees = Employee.objects.filter(department__in=departments)
    context = {
        'departments': departments,
        'employees': employees,
        'page_title': 'View Attendance',
    }
    
    return render(request, 'manager_template/manager_update_attendance.html', context)



# For handling the AJAX updates
# @csrf_exempt
# def update_attendance(request):
#     if request.method == 'POST':
#         try:
#             employee_ids = json.loads(request.POST.get('employee_ids', '[]'))
#             date_str = request.POST.get('date')
#             half_full_day = request.POST.get('half_full_day')  # 'half' or 'full'
#             which_half = request.POST.get('which_half', '')  # 'first' or 'second'
            
#             if not employee_ids or not date_str:
#                 return JsonResponse({"error": "Employee IDs and date are required"}, status=400)
            
#             try:
#                 date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
#             except ValueError:
#                 return JsonResponse({"error": "Invalid date format. Use YYYY-MM-DD"}, status=400)
            
#             updated_count = 0
#             for emp_id in employee_ids:
#                 try:
#                     # Calculate times based on attendance type
#                     if half_full_day == 'full':
#                         # Full day timing (9:00 AM to 6:00 PM)
#                         status = 'present'
#                         clock_in = datetime.combine(date_obj, time(9, 0))  # 9:00 AM
#                         clock_out = datetime.combine(date_obj, time(18, 0))  # 6:00 PM
#                         total_work = 9 * 60 * 60  # 9 hours in seconds
#                     else:
#                         # Half day timing
#                         if which_half == 'first':
#                             # First half (9:00 AM to 1:30 PM)
#                             status = 'half_day_first'
#                             clock_in = datetime.combine(date_obj, time(9, 0))
#                             clock_out = datetime.combine(date_obj, time(13, 30))
#                             total_work = 4.5 * 60 * 60  # 4.5 hours
#                         else:
#                             # Second half (1:30 PM to 6:00 PM)
#                             status = 'half_day_second'
#                             clock_in = datetime.combine(date_obj, time(13, 30))
#                             clock_out = datetime.combine(date_obj, time(18, 0))
#                             total_work = 4.5 * 60 * 60  # 4.5 hours
                    
#                     # Update or create the attendance record
#                     record, created = AttendanceRecord.objects.update_or_create(
#                         user_id=emp_id,
#                         date=date_obj,
#                         defaults={
#                             'status': status,
#                             'clock_in': clock_in,
#                             'clock_out': clock_out,
#                             'total_worked': total_work,
#                             'is_primary_record': True,
#                             'requires_verification': False,
#                             'is_verified': True,
#                             'verified_by': request.user,
#                             'updated_at': timezone.now()
#                         }
#                     )
#                     updated_count += 1
                    
#                 except Exception as e:
#                     print(f"Error updating attendance for employee {emp_id}: {str(e)}")
#                     continue
            
#             return JsonResponse({
#                 "message": f"Attendance updated successfully for {updated_count} employees",
#                 "updated_count": updated_count
#             })
            
#         except Exception as e:
#             return JsonResponse({"error": str(e)}, status=400)
    
#     return JsonResponse({"error": "Invalid request method"}, status=400)
from django.forms.models import model_to_dict

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
            print(updated_count)
            
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)
    
    return JsonResponse({"error": "Invalid request method"}, status=400)

from datetime import datetime, timedelta
from django.core.paginator import Paginator, EmptyPage
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import AttendanceRecord, Employee, Holiday

@csrf_exempt
def get_employee_attendance(request):
    if request.method == 'POST':
        try:
            employee_id = request.POST.get('employee_id')
            department_id = request.POST.get('department_id')
            month = request.POST.get('month')
            year = request.POST.get('year')
            week = request.POST.get('week')
            from_date = request.POST.get('from_date')
            to_date = request.POST.get('to_date')
            page = int(request.POST.get('page', 1))
            per_page = int(request.POST.get('per_page', 5))

            if not year and not (from_date and to_date):
                return JsonResponse({"error": "Year or date range is required"}, status=400)

            # Build queryset
            if employee_id and employee_id != 'all':
                employee = Employee.objects.select_related('admin', 'department').get(employee_id=employee_id)
                queryset = AttendanceRecord.objects.filter(user__employee=employee)
            elif department_id and department_id != 'all':
                queryset = AttendanceRecord.objects.filter(
                    user__employee__department_id=department_id
                ).select_related('user__employee__admin', 'user__employee__department')
            else:
                queryset = AttendanceRecord.objects.all().select_related(
                    'user__employee__admin', 'user__employee__department'
                )

            # Always filter by year
            if year:
                queryset = queryset.filter(date__year=int(year))

            holiday_dates = set()
            filtered_dates = None

            # Priority: Date range > Week > Month
            if from_date and to_date:
                from_date = datetime.strptime(from_date, '%Y-%m-%d').date()
                to_date = datetime.strptime(to_date, '%Y-%m-%d').date()
                queryset = queryset.filter(date__range=(from_date, to_date))
                holiday_dates = set(Holiday.objects.filter(
                    date__range=(from_date, to_date)
                ).values_list('date', flat=True))
                filtered_dates = (from_date, to_date)

            elif week and week.isdigit():
                week = int(week)
                first_day_of_year = datetime(int(year), 1, 1).date()
                start_of_week = first_day_of_year + timedelta(weeks=week - 1)
                end_of_week = start_of_week + timedelta(days=6)
                queryset = queryset.filter(date__range=(start_of_week, end_of_week))
                holiday_dates = set(Holiday.objects.filter(
                    date__range=(start_of_week, end_of_week)
                ).values_list('date', flat=True))
                filtered_dates = (start_of_week, end_of_week)

            elif month and month.isdigit():
                queryset = queryset.filter(date__month=int(month))
                holiday_dates = set(Holiday.objects.filter(
                    date__year=int(year),
                    date__month=int(month)
                ).values_list('date', flat=True))
                start_date = datetime(int(year), int(month), 1).date()
                end_date = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
                filtered_dates = (start_date, end_date)

            # Collect attendance records
            attendance_list = []
            attendance_dates = set()

            for record in queryset.order_by('-date'):
                employee = record.user.employee
                attendance_dates.add(record.date)
                status = "Holiday" if record.date in holiday_dates else record.status
                attendance_list.append({
                    "date": record.date.isoformat(),
                    "status": status,
                    "clock_in": record.clock_in.isoformat() if record.clock_in else None,
                    "clock_out": record.clock_out.isoformat() if record.clock_out else None,
                    "name": f"{employee.admin.first_name} {employee.admin.last_name}",
                    "department": employee.department.name if employee.department else "",
                    "employee_id": employee.employee_id,
                })

            # Add missing holidays with no attendance record
            if filtered_dates:
                from_date, to_date = filtered_dates
                missing_holiday_dates = holiday_dates - attendance_dates
                for holiday_date in missing_holiday_dates:
                    attendance_list.append({
                        "date": holiday_date.isoformat(),
                        "status": "Holiday",
                        "clock_in": None,
                        "clock_out": None,
                        "name": "",
                        "department": "",
                        "employee_id": "",
                    })

            # Final sort and pagination (important fix)
            attendance_list = sorted(attendance_list, key=lambda x: x['date'], reverse=True)
            paginator = Paginator(attendance_list, per_page)
            try:
                page_obj = paginator.page(page)
            except EmptyPage:
                page_obj = paginator.page(paginator.num_pages)

            return JsonResponse({
                "data": list(page_obj),
                "pagination": {
                    "total_items": paginator.count,
                    "total_pages": paginator.num_pages,
                    "current_page": page_obj.number,
                    "has_next": page_obj.has_next(),
                    "has_previous": page_obj.has_previous(),
                    "next_page_number": page_obj.next_page_number() if page_obj.has_next() else None,
                    "previous_page_number": page_obj.previous_page_number() if page_obj.has_previous() else None,
                    "per_page": per_page,
                },
                "stats": {
                    "holidays": len(holiday_dates),
                }
            })

        except Employee.DoesNotExist:
            return JsonResponse({"error": "Employee not found"}, status=404)
        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=400)
        except Exception as e:
            return JsonResponse({"error": f"An error occurred: {str(e)}"}, status=500)

    return JsonResponse({"error": "Invalid request method"}, status=405)






def manager_apply_leave(request):
    try:
        form = LeaveReportManagerForm(request.POST or None)
        manager = get_object_or_404(Manager, admin_id=request.user.id)
        
        context = {
            'form': form,
            'leave_history': LeaveReportManager.objects.filter(manager=manager),
            'page_title': 'Apply for Leave'
        }   
        if request.method == 'POST':
            if form.is_valid():
                try:
                    obj = form.save(commit=False)
                    obj.manager = manager
                    obj.save()
                    # print("obj.admin.idobj.admin.id?>>>>>>>>>>>>",obj.manager.admin_name.id,type(obj.admin.id))
                    messages.success(
                        request, "Application for leave has been submitted for review")
                    user = CustomUser.objects.get(id = obj.manager.id)
                    send_notification(user, "Leave Appplied from ","notification",obj.id,"admin")
                    return redirect(reverse('manager_apply_leave'))
                except Exception as e:
                    print("ERROR",str(e))
                    messages.error(request, "Could not apply!")
            else:
                messages.error(request, "Form has errors!")
        return render(request, "manager_template/manager_apply_leave.html", context)
    except Exception as e:
        print("ERROR:>>>>>>>>>>>>>>>>>>>>",str(e))
from django.db.models import Count,Q

def manage_employee_by_manager(request):

    # manager instanccce
    manager = get_object_or_404(Manager, admin=request.user)
    search_ = request.GET.get("search",'').strip()

    # get employees with asset count
    employees = Employee.objects.filter(team_lead=manager).annotate(
        asset_count = Count('admin__assetsissuance'),
    ).select_related('admin', 'department', 'division','team_lead')

    location_choices = dict(LOCATION_CHOICES)
    if search_ != None:
        employees = Employee.objects.filter(admin__first_name__icontains = search_)
    context = {
        'employees': employees,
        'page_title': 'Manage Employees',
        'location_choices': location_choices,
    }

    if not employees:
            messages.warning(request, "No employees found")

    return render(request, 'manager_template/manage_employee_by_manager.html', context)

@require_GET
def get_available_assets(request):
    try:
        available_assets = Assets.objects.filter(
            is_asset_issued=False,
        ).select_related('asset_category')

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
                asset_category__category=category.lower()
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



def add_employee_by_manager(request):
    # Only managers can add employees to their department
    manager = get_object_or_404(Manager, admin=request.user)

    # Form to add a new employee
    employee_form = EmployeeForm(request.POST or None, request.FILES or None)
    context = {'form': employee_form, 'page_title': 'Add Employee'}

    if request.method == 'POST':
        if employee_form.is_valid():
            first_name = employee_form.cleaned_data.get('first_name')
            last_name = employee_form.cleaned_data.get('last_name')
            address = employee_form.cleaned_data.get('address')
            email = employee_form.cleaned_data.get('email')
            gender = employee_form.cleaned_data.get('gender')
            password = employee_form.cleaned_data.get('password')
            division = employee_form.cleaned_data.get('division')
            designation = employee_form.cleaned_data.get('designation')
            phone_number = employee_form.cleaned_data.get('phone_number')
            department = employee_form.cleaned_data.get('department')

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
                employee.save()

                messages.success(request, "Successfully Added Employee")
                return redirect(reverse('manage_employee_by_manager'))  # Redirect to employee management page
            except Exception as e:
                messages.error(request, "Could Not Add Employee: " + str(e))
        else:
            messages.error(request, "Please fill all the details correctly.")

    return render(request, 'manager_template/add_employee_by_manager.html', context)



def edit_employee_by_manager(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)
    if employee.team_lead != request.user.manager:
        messages.error(request, "You do not have permission to edit this employee.")
        return redirect('manage_employee_by_manager')

    form = EmployeeForm(request.POST or None, instance=employee)
    context = {
        'form': form,
        'employee_id': employee_id,
        "user_object" : employee,
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
            passport = request.FILES.get('profile_pic') or None
            try:
                # Get the related CustomUser instance
                user = CustomUser.objects.get(id=employee.admin.id)

                # If a new passport image is uploaded, update the profile_pic
                if passport is not None:
                    fs = FileSystemStorage()
                    filename = fs.save(passport.name, passport)
                    passport_url = fs.url(filename)
                    user.profile_pic = passport_url

                # Update the CustomUser fields
                user.username = username
                user.email = email
                if password is not None:
                    user.set_password(password)  # Set the new password
                user.first_name = first_name
                user.last_name = last_name
                user.gender = gender
                user.address = address

                # Save the CustomUser instance
                user.save()

                # Update the Employee model fields
                employee.division = division
                employee.department = department
                employee.save()

                messages.success(request, "Employee information updated successfully.")
                return redirect(reverse('manage_employee_by_manager'))
            except Exception as e:
                messages.error(request, "Could not update employee: " + str(e))
        else:
            messages.error(request, "Please fill out the form correctly.")

    return render(request, 'manager_template/edit_employee_by_manager.html', context)


def delete_employee_by_manager(request, employee_id):
    # Get the employee object
    employee = get_object_or_404(Employee, id=employee_id)

    # Ensure that the logged-in manager is the team lead of the employee
    if employee.team_lead != request.user.manager:
        messages.error(request, "You do not have permission to delete this employee.")
        return redirect('manage_employee_by_manager')

    # Delete the employee
    employee.delete()

    user = employee.admin
    if user:
        user.delete()

    messages.success(request, "Employee deleted successfully.")
    return redirect(reverse('manage_employee_by_manager'))


def manager_feedback(request):
    form = FeedbackManagerForm(request.POST or None)
    manager = get_object_or_404(Manager, admin_id=request.user.id)
    context = {
        'form': form,
        'feedbacks': FeedbackManager.objects.filter(manager=manager),
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
    return render(request, "manager_template/manager_feedback.html", context)
 
@csrf_exempt
def manager_send_employee_notification(request):
    id = request.POST.get('id')
    message = request.POST.get('message')
    # employee = get_object_or_404(Employee, team_lead_id=id)
    employee = user= CustomUser.objects.filter(id = id).first()
    print(id,message,employee)
    try:
        url = "https://fcm.googleapis.com/fcm/send"
        body = {
            'notification': {
                'title': "OfficeOps",
                'body': message,
                'click_action': reverse('employee_view_notification'),
                'icon': static('dist/img/AdminLTELogo.png')
            },
            'to': employee.fcm_token
        }
        employee = Employee.objects.filter(admin = employee).first()
        headers = {'Authorization':
                   'key=dxHXv-hbaBoaO0OyQN0_W3:APA91bH4UU9a727PTFs2kQzSaB3O1UWzEMoWVVrKdNGj1cgBD4vPQHIhaWd_C6o9ocbpLOvR1-_stx52N96ywgex3IDByDpicjQ-hMRLqDJXxEVUFGM3huo',
                   'Content-Type': 'application/json'}
        data = requests.post(url, data=json.dumps(body), headers=headers)
        notification = NotificationEmployee(employee=employee, message=message,created_by=request.user)

        notification.save()
        send_notification(user, message,"notification",notification.id,"employee")
        return HttpResponse("True")
    except Exception as e:
        print(">>>>>>>>>>>>>>>>>>",str(e))
        return HttpResponse("False")
   
   
def manager_notify_employee(request):
    employee = CustomUser.objects.filter(user_type=3)
    context = {
        'page_title': "Send Notifications To Employees",
        'employees': employee
    }
    return render(request, "manager_template/employee_notification.html", context)


def manager_view_profile(request):
    manager = get_object_or_404(Manager, admin=request.user)
    form = ManagerEditForm(request.POST or None, request.FILES or None,instance=manager)
    context = {'form': form, 'page_title': 'View/Update Profile','user_object': manager.admin, }
    if request.method == 'POST':
        try:
            if form.is_valid():
                first_name = form.cleaned_data.get('first_name')
                last_name = form.cleaned_data.get('last_name')
                password = form.cleaned_data.get('password') or None
                address = form.cleaned_data.get('address')
                gender = form.cleaned_data.get('gender')
                passport = request.FILES.get('profile_pic') or None
                admin = manager.admin
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
                manager.save()
                messages.success(request, "Profile Updated!")
                return redirect(reverse('manager_view_profile'))
            else:
                messages.error(request, "Invalid Data Provided")
                return render(request, "manager_template/manager_view_profile.html", context)
        except Exception as e:
            messages.error(
                request, "Error Occured While Updating Profile " + str(e))
            return render(request, "manager_template/manager_view_profile.html", context)

    return render(request, "manager_template/manager_view_profile.html", context)


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


def manager_view_notification(request):
    manager = get_object_or_404(Manager, admin=request.user)
    notification_from_admin = NotificationManager.objects.filter(manager=manager).order_by('-created_at')
    pending_leave_requests = LeaveReportEmployee.objects.filter(status=0).order_by('-created_at')
    pending_asset_notifications = Notify_Manager.objects.filter(manager=request.user, approved__isnull=True).order_by('-timestamp')
    pending_asset_issues = AssetIssue.objects.filter(status__in=['pending', 'in_progress']).order_by('-reported_date')
    
    # all_resolved_recurring = AssetIssue.objects.filter(status='resolved',is_recurring=True).order_by('-resolved_date')[:5]
    
    # manager_unread_ids = []
    # query = Notification.objects.filter(user = request.user, role = "manager", is_read= False, notification_type = "notification")
    notification_ids = Notification.objects.filter(
        user=request.user,
        role="manager",
        is_read=False,
        notification_type="notification"
    ).values_list('leave_or_notification_id', flat=True)

    # Convert to list if needed
    manager_unread_ids = list(notification_ids)
    # this is foor histoory
    leave_history = LeaveReportEmployee.objects.filter(status__in=[1, 2]).order_by('-updated_at')
    # asset_notification_history = Notify_Manager.objects.filter(manager=request.user, approved__isnull=False).order_by('-timestamp')
    # resolved_asset_issues = AssetIssue.objects.filter(status='resolved').order_by('-resolved_date')
    # asset_notifications = Notify_Manager.objects.filter(manager=request.user, approved__isnull=True)
    # asset_issue_notifications = AssetIssue.objects.exclude(status='resolved').order_by('-reported_date')
    
    # context = {
    #     'pending_leave_requests': pending_leave_requests,
    #     'asset_notifications': asset_notifications,
    #     'asset_issue_notifications': asset_issue_notifications,
    #     'notifications': notification_from_admin, 
    #     'page_title': "View Notifications",
    #     'LOCATION_CHOICES': LOCATION_CHOICES
    # }
    

    notification_from_admin_paginator = Paginator(notification_from_admin,3)
    leave_paginator = Paginator(leave_history, 3)  # Show 3 items per page
    # asset_notification_paginator = Paginator(asset_notification_history, 3)
    # resolved_issues_paginator = Paginator(resolved_asset_issues, 3)

    notification_page_number = request.GET.get('notification_page')
    leave_page_number = request.GET.get('leave_page')
    asset_notification_page_number = request.GET.get('asset_notification_page')
    resolved_issues_page_number = request.GET.get('resolved_issues_page')

    notification_from_admin_obj = notification_from_admin_paginator.get_page(notification_page_number)
    leave_page_obj = leave_paginator.get_page(leave_page_number)
    # asset_notification_page_obj = asset_notification_paginator.get_page(asset_notification_page_number)
    # resolved_issues_page_obj = resolved_issues_paginator.get_page(resolved_issues_page_number)
    
    context = {
        'notification_from_admin' : notification_from_admin,
        'pending_leave_requests': pending_leave_requests,
        # 'asset_notifications': pending_asset_notifications,
        # 'asset_issue_notifications': pending_asset_issues,
        # 'pending_issue': pending_asset_issues.filter(status='pending'),
        # 'in_progress_issue': pending_asset_issues.filter(status='in_progress'),
        'notification_from_admin_obj' : notification_from_admin_obj,
        # 'all_resolved_recurring' : all_resolved_recurring,

        # this is for historyy
        'leave_page_obj': leave_page_obj,
        # 'asset_notification_page_obj': asset_notification_page_obj,
        # 'resolved_issues_page_obj': resolved_issues_page_obj,

        # # Filter values for template
        # 'status_filter': status_filter,
        # 'date_from': date_from or '',
        # 'date_to': date_to or '',

        'page_title': "View Notifications",
        'manager_unread_ids': manager_unread_ids,
        'LOCATION_CHOICES': LOCATION_CHOICES,
    }

    return render(request, "manager_template/manager_view_notification.html", context)



def manager_asset_view_notification(request):
    manager = get_object_or_404(Manager, admin=request.user)

    # Recently resolved recurring asset issues
    all_resolved_recurring = AssetIssue.objects.filter(
        status='resolved',
        is_recurring=True
    ).order_by('-resolved_date')[:5]

    # Asset claim notifications pending approval
    pending_asset_notifications = Notify_Manager.objects.filter(
        manager=request.user,
        approved__isnull=True
    ).order_by('-timestamp')

    # Asset issues with pending or in-progress status
    pending_asset_issues = AssetIssue.objects.filter(
        status__in=['pending', 'in_progress']
    ).order_by('-reported_date')

    # Pagination for asset claim notifications
    asset_notification_paginator = Paginator(pending_asset_notifications, 5)
    asset_notification_page_obj = asset_notification_paginator.get_page(request.GET.get('asset_page'))

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
    }

    return render(request, "manager_template/manager_asset_view_notification.html", context)


@csrf_exempt
def send_bulk_employee_notification_by_manager(request):
    if request.method == 'POST':
        message = request.POST.get('message')
        employees = Employee.objects.all()
        success = True
        
        try:
            for employee in employees:
                if employee.admin.fcm_token:
                    url = "https://fcm.googleapis.com/fcm/send"
                    body = {
                        'notification': {
                            'title': "KoliInfoTech",
                            'body': message,
                            'click_action': reverse('employee_view_notification'),
                            'icon': static('dist/img/AdminLTELogo.png')
                        },
                        'to': employee.admin.fcm_token
                    }
                    headers = {
                        'Authorization': 'key=AAAA3Bm8j_M:APA91bElZlOLetwV696SoEtgzpJr2qbxBfxVBfDWFiopBWzfCfzQp2nRyC7_A2mlukZEHV4g1AmyC6P_HonvSkY2YyliKt5tT3fe_1lrKod2Daigzhb2xnYQMxUWjCAIQcUexAMPZePB',
                        'Content-Type': 'application/json'
                    }
                    requests.post(url, data=json.dumps(body), headers=headers)
                
                # Save notification to database
                notification = NotificationEmployee(
                    employee=employee,
                    message=message,
                    created_by=request.user
                )
                notification.save()
                
            return HttpResponse("True")
        except Exception as e:
            print(e)
            return HttpResponse("False")

@csrf_exempt
def send_selected_employee_notification_by_manager(request):
    if request.method == 'POST':
        message = request.POST.get('message')
        employee_ids = json.loads(request.POST.get('employee_ids'))
        print(employee_ids)
        success = True
        
        try:
            for emp_id in employee_ids:
                employee = get_object_or_404(Employee, admin_id=emp_id)
                if employee.admin.fcm_token:
                    url = "https://fcm.googleapis.com/fcm/send"
                    body = {
                        'notification': {
                            'title': "KoliInfoTech",
                            'body': message,
                            'click_action': reverse('employee_view_notification'),
                            'icon': static('dist/img/AdminLTELogo.png')
                        },
                        'to': employee.admin.fcm_token
                    }
                    headers = {
                        'Authorization': 'key=AAAA3Bm8j_M:APA91bElZlOLetwV696SoEtgzpJr2qbxBfxVBfDWFiopBWzfCfzQp2nRyC7_A2mlukZEHV4g1AmyC6P_HonvSkY2YyliKt5tT3fe_1lrKod2Daigzhb2xnYQMxUWjCAIQcUexAMPZePB',
                        'Content-Type': 'application/json'
                    }
                    requests.post(url, data=json.dumps(body), headers=headers)
                
                # Save notification to database
                notification = NotificationEmployee(
                    employee=employee,
                    message=message,
                    created_by=request.user
                )
                notification.save()
                
            return HttpResponse("True")
        except Exception as e:
            print(e)
            return HttpResponse("False")


def approve_assest_request(request, notification_id):
    if request.method == 'POST':
        asset_location_  = request.POST.get("asset_location" , "Main Room")
        notification = get_object_or_404(Notify_Manager, id=notification_id)

        if notification.approved is None or notification.approved is False:
            asset = notification.asset
            employee = notification.employee 
            try:
                AssetsIssuance.objects.create(
                    asset=asset,
                    asset_location=asset_location_,
                    asset_assignee=employee
                )
            
                my_asset = Assets.objects.get(id=asset.id)
                my_asset.manager = request.user
                my_asset.is_asset_issued = True
                my_asset.save()
                notification.approved = True
                notification.save()
                messages.success(request, "Asset request approved successfully.")
                notify = Notification.objects.filter(leave_or_notification_id=notification_id, user=request.user,role = "manager",notification_type = "notification").first()
                if notify:
                    notify.is_read = True
                    notify.save()
            except:
                messages.error(request,"This Asset is not Found in Inventry")

        else:
            messages.info(request, "This request was already approved.")

    return redirect('manager_asset_view_notification')



def reject_assest_request(request, notification_id):
    notification = get_object_or_404(Notify_Manager, id=notification_id)
    if notification.approved is None or notification.approved is False:
        notification.approved = False
        notification.save()
        messages.success(request, "Asset request rejected successfully.")
        notify = Notification.objects.filter(leave_or_notification_id=notification_id, user=request.user,role = "manager",notification_type = "notification").first()
        if notify:
            notify.is_read = True
            notify.save()
        notification.save()
    else:
        messages.info(request, "This request was already approved or rejected.")

    return redirect('manager_asset_view_notification')


def approve_leave_request(request, leave_id):
    if request.method == 'POST':
        leave_request = get_object_or_404(LeaveReportEmployee, id=leave_id)
        msg = "Please check the Leave Request"
        if leave_request.status == 0:
            if not leave_request.end_date:
                leave_request.end_date = leave_request.start_date
                leave_request.save()

            leave_request.status = 1
            leave_request.save()

            if leave_request.leave_type == 'Half-Day':
                messages.success(request, "Half-Day leave approved.")
            else:
                messages.success(request, "Full-Day leave approved.")
            msg = "Leave request approved."
        else:
            messages.info(request, "This leave request has already been processed.")
        user = CustomUser.objects.get(id = leave_request.employee.admin.id)
        send_notification(user, msg,"leave",leave_id,"employee")
    return redirect('manager_view_notification')


def reject_leave_request(request, leave_id):
    if request.method == 'POST':
        msg = "Please check the Leave Request"
        leave_request = get_object_or_404(LeaveReportEmployee, id=leave_id)
        if leave_request.status == 0:
            leave_request.status = 2
            leave_request.save()
            msg = "Leave request rejected."
            messages.warning(request, "Leave request rejected.")
        else:
            messages.info(request, "This leave request has already been processed.")
        user = CustomUser.objects.get(id = leave_request.employee.admin.id)
        send_notification(user, msg,"leave",leave_id,"employee")
    return redirect('manager_view_notification')


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


def resolve_asset_issue(request,asset_issu_id):
    if request.method == "POST":
        issue_asset = get_object_or_404(AssetIssue,pk=asset_issu_id)
        issue_asset.status = request.POST.get('status')
        issue_asset.notes = request.POST.get('notes')
        issue_asset.resolution_method = request.POST.get('resolution_method')
        issue_asset.is_recurring = request.POST.get('is_recurring') == "on"
        issue_asset.resolved_date = datetime.now()
        issue_asset.save()

        if issue_asset.status == "resolved":
            notify = Notification.objects.filter(leave_or_notification_id=asset_issu_id, role = "manager",notification_type = "asset issue").first()
            if notify:
                notify.is_read = True
                notify.save()
        messages.success(request,f"Asset Issue {issue_asset.status}!!")
    
    return redirect('manager_asset_view_notification')


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
    
