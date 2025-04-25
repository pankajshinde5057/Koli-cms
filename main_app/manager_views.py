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


def manager_take_attendance(request):
    manager = get_object_or_404(Manager, admin=request.user)
    departments = Department.objects.filter(division=manager.division)
    context = {
        'departments': departments,
        'page_title': 'Take Attendance'
    }

    return render(request, 'manager_template/manager_take_attendance.html', context)


@csrf_exempt
def get_employees(request):
    department_id = request.POST.get('department')
    try:
        department = get_object_or_404(Department, id=department_id)
        employees = Employee.objects.filter(division_id=department.division.id)
        employee_data = []
        for employee in employees:
            data = {
                "id": employee.id,
                "name": employee.admin.last_name + " " + employee.admin.first_name
            }
            employee_data.append(data)
        return JsonResponse(json.dumps(employee_data), content_type='application/json', safe=False)
    except Exception as e:
        return e


@csrf_exempt
def save_attendance(request):
    employee_data = request.POST.get('employee_ids')
    date = request.POST.get('date')
    department_id = request.POST.get('department')
    employees = json.loads(employee_data)
    try:
        department = get_object_or_404(Department, id=department_id)
        attendance, created = AttendanceRecord.objects.get_or_create(department=department, date=date)

        for employee_dict in employees:
            employee = get_object_or_404(Employee, id=employee_dict.get('id'))
            attendance_report, report_created = AttendanceReport.objects.get_or_create(employee=employee, attendance=attendance)
            if report_created:
                attendance_report.status = employee_dict.get('status')
                attendance_report.save()

    except Exception as e:
        return None

    return HttpResponse("OK")


def manager_update_attendance(request):
    manager = get_object_or_404(Manager, admin=request.user)
    departments = Department.objects.filter(division=manager.division)
    context = {
        'departments': departments,
        'page_title': 'Update Attendance'
    }

    return render(request, 'manager_template/manager_update_attendance.html', context)


@csrf_exempt
def get_employee_attendance(request):
    attendance_date_id = request.POST.get('attendance_date_id')
    try:
        date = get_object_or_404(AttendanceRecord, id=attendance_date_id)
        attendance_data = AttendanceReport.objects.filter(attendance=date)
        employee_data = []
        for attendance in attendance_data:
            data = {"id": attendance.employee.admin.id,
                    "name": attendance.employee.admin.last_name + " " + attendance.employee.admin.first_name,
                    "status": attendance.status}
            employee_data.append(data)
        return JsonResponse(json.dumps(employee_data), content_type='application/json', safe=False)
    except Exception as e:
        return e


@csrf_exempt
def update_attendance(request):
    employee_data = request.POST.get('employee_ids')
    date = request.POST.get('date')
    employees = json.loads(employee_data)
    try:
        attendance = get_object_or_404(AttendanceRecord, id=date)

        for employee_dict in employees:
            employee = get_object_or_404(
                Employee, admin_id=employee_dict.get('id'))
            attendance_report = get_object_or_404(AttendanceReport, employee=employee, attendance=attendance)
            attendance_report.status = employee_dict.get('status')
            attendance_report.save()
    except Exception as e:
        return None

    return HttpResponse("OK")


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
    
