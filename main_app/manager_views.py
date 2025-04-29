from calendar import calendar
import json
from django.contrib import messages
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404,redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from .forms import *
from .models import *
from asset_app.models import Notify_Manager,AssetsIssuance,Assets
from django.utils.dateparse import parse_date

LOCATION_CHOICES = (
    ("Main Room" , "Main Room"),
    ("Meeting Room", "Meeting Room"),
    ("Main Office", "Main Office"),
)

def manager_home(request):
    manager = get_object_or_404(Manager, admin=request.user)

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

    if start_date and end_date:
        date_range = [parse_date(start_date), parse_date(end_date)]
        filtered_records = filtered_records.filter(date__range=date_range)

    time_history_data = []

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

        time_history_data.append({
            'employee_name': employee.get_full_name(),
            'department': employee.employee.department.name if hasattr(employee, 'employee') and employee.employee.department else '',
            'present': total_present,
            'late': total_late,
            'leave': total_leave,
            'working_days': total_present + total_late
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
    }
    return render(request, 'manager_template/home_content.html', context)


# def manager_take_attendance(request):
#     manager = get_object_or_404(Manager, admin=request.user)
#     departments = Department.objects.filter(division=manager.division)
#     context = {
#         'departments': departments,
#         'page_title': 'Take Attendance'
#     }

#     return render(request, 'manager_template/manager_take_attendance.html', context)


# @csrf_exempt
# def get_employees(request):
#     department_id = request.POST.get('department')
#     try:
#         department = get_object_or_404(Department, id=department_id)
#         employees = Employee.objects.filter(division_id=department.division.id)
#         employee_data = []
#         for employee in employees:
#             data = {
#                 "id": employee.id,
#                 "name": employee.admin.last_name + " " + employee.admin.first_name
#             }
#             employee_data.append(data)
#         return JsonResponse(json.dumps(employee_data), content_type='application/json', safe=False)
#     except Exception as e:
#         return e


# @csrf_exempt
# def save_attendance(request):
#     employee_data = request.POST.get('employee_ids')
#     date = request.POST.get('date')
#     department_id = request.POST.get('department')
#     employees = json.loads(employee_data)
#     try:
#         department = get_object_or_404(Department, id=department_id)
#         attendance, created = AttendanceRecord.objects.get_or_create(department=department, date=date)

#         for employee_dict in employees:
#             employee = get_object_or_404(Employee, id=employee_dict.get('id'))
#             attendance_report, report_created = AttendanceReport.objects.get_or_create(employee=employee, attendance=attendance)
#             if report_created:
#                 attendance_report.status = employee_dict.get('status')
#                 attendance_report.save()

#     except Exception as e:
#         return None

#     return HttpResponse("OK")

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from .models import Manager, Department, Employee, AttendanceRecord, CustomUser
import json
from datetime import datetime, time, timedelta

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
        department = get_object_or_404(Department, id=department_id)
        employees = Employee.objects.filter(department=department)
        employee_data = []
        for employee in employees:
            data = {
                "id": employee.id,
                "name": employee.admin.last_name + " " + employee.admin.first_name
            }
            employee_data.append(data)
        return JsonResponse(json.dumps(employee_data), content_type='application/json', safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
def save_attendance(request):
    employee_data = request.POST.get('employee_ids')
    date_str = request.POST.get('date')
    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    department_id = request.POST.get('department')
    half_full_day = request.POST.get('half_full_day')
    today = date_obj.today()
    current_month = today.month
    current_year = today.year
    
    start_date = today.replace(day=1)

    # Add a month, then subtract days until we get back to the last day of the current month
    if today.month == 12:
        next_month = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_month = today.replace(month=today.month + 1, day=1)

    end_date = next_month - timedelta(days=1)
    manager_id = request.user.id
    # Log incoming data for debugging
    print("$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$", )
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
                employee = Employee.objects.filter(id = int(emp)).first()
            else:
                employee = get_object_or_404(Employee, id=emp.get('id'))
            print("employee.admin",employee)
            user = employee.admin  # CustomUser linked
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
                total_work = 8*60*60
                clock_in = datetime.combine(date_obj, time(9, 0, 0)) 
                clock_out = datetime.combine(date_obj, time(18, 0, 0)) 
            if half_full_day == "half":
                total_work = 4*60*60
                clock_in = datetime.combine(date_obj, time(9, 0, 0)) 
                clock_out = datetime.combine(date_obj, time(13, 0, 0)) 
            is_primary_record = 1
            required_verfication = 0
            user_id = int(emp)
            verified_by_id = user
            attendance = AttendanceRecord.objects.create(
                date=date_obj,
                clock_in=clock_in,
                clock_out=clock_out,  # or provide clock_out datetime
                status='Present',
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





# def manager_update_attendance(request):
#     manager = get_object_or_404(Manager, admin=request.user)
#     departments = Department.objects.filter(division=manager.division)
#     context = {
#         'departments': departments,
#         'page_title': 'Update Attendance'
#     }

#     return render(request, 'manager_template/manager_update_attendance.html', context)


# @csrf_exempt
# def get_employee_attendance(request):
#     attendance_date_id = request.POST.get('attendance_date_id')
#     try:
#         date = get_object_or_404(AttendanceRecord, id=attendance_date_id)
#         attendance_data = AttendanceReport.objects.filter(attendance=date)
#         employee_data = []
#         for attendance in attendance_data:
#             data = {"id": attendance.employee.admin.id,
#                     "name": attendance.employee.admin.last_name + " " + attendance.employee.admin.first_name,
#                     "status": attendance.status}
#             employee_data.append(data)
#         return JsonResponse(json.dumps(employee_data), content_type='application/json', safe=False)
#     except Exception as e:
#         return e


# @csrf_exempt
# def update_attendance(request):
#     employee_data = request.POST.get('employee_ids')
#     date = request.POST.get('date')
#     employees = json.loads(employee_data)
#     try:
#         attendance = get_object_or_404(AttendanceRecord, id=date)

#         for employee_dict in employees:
#             employee = get_object_or_404(
#                 Employee, admin_id=employee_dict.get('id'))
#             attendance_report = get_object_or_404(AttendanceReport, employee=employee, attendance=attendance)
#             attendance_report.status = employee_dict.get('status')
#             attendance_report.save()
#     except Exception as e:
#         return None

#     return HttpResponse("OK")

# View to update attendance for the manager
def manager_update_attendance(request):
    manager = get_object_or_404(Manager, admin=request.user)
    departments = Department.objects.filter(division=manager.division)
    context = {
        'departments': departments,
        'page_title': 'Update Attendance'
    }

    return render(request, 'manager_template/manager_update_attendance.html', context)


# View to get employee attendance details based on selected date
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from .models import AttendanceRecord, Employee
 
@csrf_exempt
def get_employee_attendance(request):
    attendance_date_id = request.POST.get('attendance_date_id')
    try:
        # Fetch the AttendanceRecord using the provided id
        date_record = get_object_or_404(AttendanceRecord, id=attendance_date_id)
       
        # Fetch all attendance records for the same date
        attendance_data = AttendanceRecord.objects.filter(date=date_record.date)
       
        # Prepare response data
        employee_data = [
            {
                "id": attendance.user.id,  # The user is related to CustomUser
                "name": f"{attendance.user.last_name} {attendance.user.first_name}",
                "status": attendance.status
            }
            for attendance in attendance_data
        ]
       
        return JsonResponse(employee_data, safe=False)
 
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


# View to update attendance status
@csrf_exempt
def update_attendance(request):
    employee_data = request.POST.get('employee_ids')
    date = request.POST.get('date')
    employees = json.loads(employee_data)

    try:
        attendance = get_object_or_404(AttendanceRecord, id=date)

        for employee_dict in employees:
            employee = get_object_or_404(Employee, admin_id=employee_dict.get('id'))
            attendance_report = get_object_or_404(AttendanceRecord, employee=employee, attendance=attendance)
            attendance_report.status = employee_dict.get('status')
            attendance_report.save()

        return JsonResponse({"message": "Attendance updated successfully!"})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


# View to get attendance records for a department


def manager_apply_leave(request):
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
                messages.success(
                    request, "Application for leave has been submitted for review")
                return redirect(reverse('manager_apply_leave'))
            except Exception:
                messages.error(request, "Could not apply!")
        else:
            messages.error(request, "Form has errors!")
    return render(request, "manager_template/manager_apply_leave.html", context)

def manage_employee_by_manager(request):

    manager = get_object_or_404(Manager, admin=request.user)

    employees = Employee.objects.filter(team_lead=manager)
    
    if not employees:
        messages.warning(request, "No employees found for your team.")
    
    context = {
        'employees': employees,
        'page_title': 'Manage Employees'
    }
    return render(request, 'manager_template/manage_employee_by_manager.html', context)



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
            department = manager.department  # The department of the manager
            passport = request.FILES['profile_pic']
            
            fs = FileSystemStorage()
            filename = fs.save(passport.name, passport)
            passport_url = fs.url(filename)

            try:
                # Create the user (employee)
                user = CustomUser.objects.create_user(
                    email=email, password=password, user_type=3, first_name=first_name, last_name=last_name, profile_pic=passport_url)
                user.gender = gender
                user.address = address
                user.employee.division = division
                user.employee.department = department
                user.employee.team_lead = manager  # Assign manager as the team lead
                user.save()

                messages.success(request, "Successfully Added Employee")
                return redirect(reverse('manage_employee_by_manager'))  # Redirect to employee management page
            except Exception as e:
                messages.error(request, "Could Not Add Employee: " + str(e))
        else:
            messages.error(request, "Please fill all the details correctly.")

    return render(request, 'manager_template/add_employee_by_manager.html', context)



def edit_employee_by_manager(request, employee_id):
    # Get the employee object
    employee = get_object_or_404(Employee, id=employee_id)

    # Ensure that the logged-in manager is the team lead of the employee
    if employee.team_lead != request.user.manager:
        messages.error(request, "You do not have permission to edit this employee.")
        return redirect('manage_employee_by_manager')

    form = EmployeeForm(request.POST or None, instance=employee)
    context = {
        'form': form,
        'employee_id': employee_id,
        'page_title': 'Edit Employee'
    }

    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, "Employee information updated successfully.")
            return redirect(reverse('manage_employee_by_manager'))
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


from django.templatetags.static import static
import requests
 
@csrf_exempt
def manager_send_employee_notification(request):
    id = request.POST.get('id')
    message = request.POST.get('message')
    # employee = get_object_or_404(Employee, team_lead_id=id)
    employee = CustomUser.objects.filter(id = id).first()
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
        notification = NotificationEmployee(employee=employee, message=message)
        notification.save()
        return HttpResponse("True")
    except Exception as e:
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
    context = {'form': form, 'page_title': 'View/Update Profile'}
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
    pending_leave_requests = LeaveReportEmployee.objects.filter(status=0).order_by('-created_at')
    asset_notifications = Notify_Manager.objects.filter(manager=request.user, approved__isnull=True)
    
    context = {
        'pending_leave_requests': pending_leave_requests,
        'asset_notifications': asset_notifications,
        'page_title': "View Notifications",
        'LOCATION_CHOICES': LOCATION_CHOICES
    }
    
    return render(request, "manager_template/manager_view_notification.html",context)


def approve_assest_request(request, notification_id):
    if request.method == 'POST':
        asset_location_  = request.POST.get("asset_location" , "Main Room")
        notification = get_object_or_404(Notify_Manager, id=notification_id, manager=request.user)

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
                my_asset.is_asset_issued = True
                my_asset.save()
                print(my_asset.is_asset_issued)

                notification.approved = True
                notification.save()
                messages.success(request, "Asset request approved successfully.")

            except:
                messages.error(request,"This Asset is not Found in Inventry")

        else:
            messages.info(request, "This request was already approved.")

    return redirect('manager_view_notification')



def reject_assest_request(request, notification_id):
    notification = get_object_or_404(Notify_Manager, id=notification_id, manager=request.user)
    if notification.approved is None or notification.approved is False:
        notification.approved = False
        notification.save()
        messages.success(request, "Asset request rejected successfully.")
    else:
        messages.info(request, "This request was already approved or rejected.")

    return redirect('manager_view_notification')


def approve_leave_request(request, leave_id):
    if request.method == 'POST':
        leave_request = get_object_or_404(LeaveReportEmployee, id=leave_id)
        if leave_request.status == 0:
            leave_request.status = 1
            leave_request.save()
            messages.success(request, "Leave request approved.")
        else:
            messages.info(request, "This leave request has already been processed.")
    return redirect('manager_view_notification')


def reject_leave_request(request, leave_id):
    if request.method == 'POST':
        leave_request = get_object_or_404(LeaveReportEmployee, id=leave_id)
        if leave_request.status == 0:
            leave_request.status = 2
            leave_request.save()
            messages.warning(request, "Leave request rejected.")
        else:
            messages.info(request, "This leave request has already been processed.")
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
    
