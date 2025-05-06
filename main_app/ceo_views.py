from django.contrib import messages
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse, JsonResponse
from django.shortcuts import (HttpResponse,get_object_or_404, redirect, render)
import requests,json
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from .forms import *
from .models import *
from collections import defaultdict
from xhtml2pdf import pisa
from calendar import monthrange
from datetime import datetime,timedelta
from decimal import Decimal
from django.template.loader import get_template


def admin_home(request):
    total_manager = Manager.objects.all().count()
    total_employees = Employee.objects.all().count()
    departments = Department.objects.all()
    total_department = departments.count()
    total_division = Division.objects.all().count()
    attendance_list = AttendanceRecord.objects.filter(department__in=departments)
    total_attendance = attendance_list.count()
    attendance_list = []
    department_list = []
    for department in departments:
        attendance_count = AttendanceRecord.objects.filter(department=department).count()
        department_list.append(department.name[:7])
        attendance_list.append(attendance_count)
    context = {
        'page_title': "Administrative Dashboard",
        'total_employees': total_employees,
        'total_manager': total_manager,
        'total_division': total_division,
        'total_department': total_department,
        'department_list': department_list,
        'attendance_list': attendance_list

    }
    return render(request, 'ceo_template/home_content.html', context)


def add_manager(request):
    form = ManagerForm(request.POST or None, request.FILES or None)
    context = {'form': form, 'page_title': 'Add Manager'}
    if request.method == 'POST':
        if form.is_valid():
            first_name = form.cleaned_data.get('first_name')
            last_name = form.cleaned_data.get('last_name')
            address = form.cleaned_data.get('address')
            email = form.cleaned_data.get('email')
            gender = form.cleaned_data.get('gender')
            password = form.cleaned_data.get('password')
            division = form.cleaned_data.get('division')
            passport = request.FILES.get('profile_pic')
            fs = FileSystemStorage()
            filename = fs.save(passport.name, passport)
            passport_url = fs.url(filename)
            try:
                user = CustomUser.objects.create_user(
                    email=email, password=password, user_type=2, first_name=first_name, last_name=last_name, profile_pic=passport_url)
                user.gender = gender
                user.address = address
                user.manager.division = division
                user.save()
                messages.success(request, "Successfully Added")
                return redirect(reverse('add_manager'))

            except Exception as e:
                messages.error(request, "Could Not Add " + str(e))
        
        else:
            messages.error(request, "Please fill all the details correctly.")
    return render(request, 'ceo_template/add_manager_template.html', context)


def add_employee(request):
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
            department = employee_form.cleaned_data.get('department')
            team_lead = employee_form.cleaned_data.get('team_lead')
            
            passport = request.FILES['profile_pic']
            fs = FileSystemStorage()
            filename = fs.save(passport.name, passport)
            passport_url = fs.url(filename)
            try:
                user = CustomUser.objects.create_user(
                    email=email, password=password, user_type=3, first_name=first_name, last_name=last_name, profile_pic=passport_url)
                user.gender = gender
                user.address = address
                user.employee.division = division
                user.employee.department = department
                if team_lead:
                    user.employee.team_lead = team_lead
                user.save()
                messages.success(request, "Successfully Added")
                return redirect(reverse('add_employee'))
            except Exception as e:
                messages.error(request, "Could Not Add: " + str(e))
        else:
            messages.error(request, "Please fill all the details correctly.")
        
    return render(request, 'ceo_template/add_employee_template.html', context)


def add_division(request):
    form = DivisionForm(request.POST or None)
    context = {
        'form': form,
        'page_title': 'Add Division'
    }
    if request.method == 'POST':
        if form.is_valid():
            name = form.cleaned_data.get('name')
            try:
                division = Division()
                division.name = name
                division.save()
                messages.success(request, "Successfully Added")
                return redirect(reverse('add_division'))
            except:
                messages.error(request, "Could Not Add")
        else:
            messages.error(request, "Could Not Add")
    return render(request, 'ceo_template/add_division_template.html', context)


def add_department(request):
    form = DepartmentForm(request.POST or None)
    context = {
        'form': form,
        'page_title': 'Add Department'
    }
    if request.method == 'POST':
        if form.is_valid():
            name = form.cleaned_data.get('name')
            division = form.cleaned_data.get('division')
            try:
                department = Department()
                department.name = name
                department.division = division
                department.save()
                messages.success(request, "Successfully Added")
                return redirect(reverse('add_department'))

            except Exception as e:
                messages.error(request, "Could Not Add " + str(e))
        else:
            messages.error(request, "Fill Form Properly")

    return render(request, 'ceo_template/add_department_template.html', context)


def manage_manager(request):
    
    allManager = CustomUser.objects.filter(user_type=2)
    context = {
        'allManager': allManager,
        'page_title': 'Manage Manager'
    }
    return render(request, "ceo_template/manage_manager.html", context)


def manage_employee(request):
    employees = CustomUser.objects.filter(user_type=3).select_related('employee')
    valid_employees = [emp for emp in employees if hasattr(emp, 'employee') and emp.employee.id]

    context = {
        'employees': valid_employees,
        'page_title': 'Manage Employees'
    }
    return render(request, "ceo_template/manage_employee.html", context)



def manage_division(request):
    divisions = Division.objects.all()
    context = {
        'divisions': divisions,
        'page_title': 'Manage Divisions'
    }
    return render(request, "ceo_template/manage_division.html", context)


def manage_department(request):
    departments = Department.objects.all()
    context = {
        'departments': departments,
        'page_title': 'Manage Departments'
    }
    return render(request, "ceo_template/manage_department.html", context)


def edit_manager(request, manager_id):
    manager = get_object_or_404(Manager, id=manager_id)
    form = ManagerForm(request.POST or None, instance=manager)
    context = {
        'form': form,
        'manager_id': manager_id,
        'page_title': 'Edit Manager'
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
            passport = request.FILES.get('profile_pic') or None
            try:
                user = CustomUser.objects.get(id=manager.admin.id)
                user.username = username
                user.email = email
                if password != None:
                    user.set_password(password)
                if passport != None:
                    fs = FileSystemStorage()
                    filename = fs.save(passport.name, passport)
                    passport_url = fs.url(filename)
                    user.profile_pic = passport_url
                user.first_name = first_name
                user.last_name = last_name
                user.gender = gender
                user.address = address
                manager.division = division
                user.save()
                manager.save()
                messages.success(request, "Successfully Updated")
                return redirect(reverse('edit_manager', args=[manager_id]))
            except Exception as e:
                messages.error(request, "Could Not Update " + str(e))
        else:
            messages.error(request, "Please fil form properly")
    else:
        user = CustomUser.objects.get(id=manager_id)
        manager = Manager.objects.get(id=user.id)
        return render(request, "ceo_template/edit_manager_template.html", context)


def edit_employee(request, employee_id):
    employee = get_object_or_404(Employee, id=employee_id)
    form = EmployeeForm(request.POST or None, instance=employee)
    context = {
        'form': form,
        'employee_id': employee_id,
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
                user = CustomUser.objects.get(id=employee.admin.id)
                if passport != None:
                    fs = FileSystemStorage()
                    filename = fs.save(passport.name, passport)
                    passport_url = fs.url(filename)
                    user.profile_pic = passport_url
                user.username = username
                user.email = email
                if password != None:
                    user.set_password(password)
                user.first_name = first_name
                user.last_name = last_name
                user.gender = gender
                user.address = address
                employee.division = division
                employee.department = department
                user.save()
                employee.save()
                messages.success(request, "Successfully Updated")
                return redirect(reverse('edit_employee', args=[employee_id]))
            except Exception as e:
                messages.error(request, "Could Not Update " + str(e))
        else:
            messages.error(request, "Please Fill Form Properly!")
    else:
        return render(request, "ceo_template/edit_employee_template.html", context)


def edit_division(request, division_id):
    instance = get_object_or_404(Division, id=division_id)
    form = DivisionForm(request.POST or None, instance=instance)
    context = {
        'form': form,
        'division_id': division_id,
        'page_title': 'Edit Division'
    }
    if request.method == 'POST':
        if form.is_valid():
            name = form.cleaned_data.get('name')
            try:
                division = Division.objects.get(id=division_id)
                division.name = name
                division.save()
                messages.success(request, "Successfully Updated")
            except:
                messages.error(request, "Could Not Update")
        else:
            messages.error(request, "Could Not Update")

    return render(request, 'ceo_template/edit_division_template.html', context)


def edit_department(request, department_id):
    instance = get_object_or_404(Department, id=department_id)
    form = DepartmentForm(request.POST or None, instance=instance)
    context = {
        'form': form,
        'department_id': department_id,
        'page_title': 'Edit Department'
    }
    if request.method == 'POST':
        if form.is_valid():
            name = form.cleaned_data.get('name')
            division = form.cleaned_data.get('division')
            try:
                department = Department.objects.get(id=department_id)
                department.name = name
                department.division = division
                department.save()
                messages.success(request, "Successfully Updated")
                return redirect(reverse('edit_department', args=[department_id]))
            except Exception as e:
                messages.error(request, "Could Not Add " + str(e))
        else:
            messages.error(request, "Fill Form Properly")
    return render(request, 'ceo_template/edit_department_template.html', context)


@csrf_exempt
def check_email_availability(request):
    email = request.POST.get("email")
    try:
        user = CustomUser.objects.filter(email=email).exists()
        if user:
            return HttpResponse(True)
        return HttpResponse(False)
    except Exception as e:
        return HttpResponse(False)


@csrf_exempt
def employee_feedback_message(request):
    if request.method != 'POST':
        feedbacks = FeedbackEmployee.objects.all().order_by('-id')
        unread_ids = list(
            Notification.objects.filter(
                user=request.user,
                is_read=False,
                notification_type='employee feedback'
            ).values_list('leave_or_notification_id', flat=True) 
        )
        print("EMPLOYEEE FEEDBAD",unread_ids)
        context = {
            'feedbacks': feedbacks,
            'page_title': 'Employee Feedback Messages',
            'unread_ids':unread_ids
        }
        return render(request, 'ceo_template/employee_feedback_template.html', context)
    else:
        feedback_id = request.POST.get('id')
        try:
            feedback = get_object_or_404(FeedbackEmployee, id=feedback_id)
            reply = request.POST.get('reply')
            feedback.reply = reply
            feedback.save()
            notify = Notification.objects.filter(user = request.user,role = "admin", is_read = False, leave_or_notification_id = feedback_id).first()
            if notify:
                notify.is_read = True
                notify.save()
                print("OKKKKKKKKKKKKKKK")
            return HttpResponse(True)
        except Exception as e:
            return HttpResponse(False)


@csrf_exempt
def manager_feedback_message(request):
    if request.method != 'POST':
        feedbacks = FeedbackManager.objects.all().order_by('-id')
        context = {
            'feedbacks': feedbacks,
            'page_title': 'Manager Feedback Messages'
        }
        return render(request, 'ceo_template/manager_feedback_template.html', context)
    else:
        feedback_id = request.POST.get('id')
        try:
            feedback = get_object_or_404(FeedbackManager, id=feedback_id)
            reply = request.POST.get('reply')
            feedback.reply = reply
            feedback.save()
            return HttpResponse(True)
        except Exception as e:
            return HttpResponse(False)


@csrf_exempt
def view_manager_leave(request):
    if request.method != 'POST':
        allLeave = LeaveReportManager.objects.all().order_by('-date')
        context = {
            'allLeave': allLeave,
            'page_title': 'Leave Applications From Manager'
        }
        return render(request, "ceo_template/manager_leave_view.html", context)
    else:
        id = request.POST.get('id')
        status = request.POST.get('status')
        if (status == '1'):
            status = 1
        else:
            status = -1
        try:
            leave = get_object_or_404(LeaveReportManager, id=id)
            leave.status = status
            leave.save()
            return HttpResponse(True)
        except Exception as e:
            return False


@csrf_exempt
def view_employee_leave(request):
    if request.method != 'POST':
        allLeave = LeaveReportEmployee.objects.all()
        context = {
            'allLeave': allLeave,
            'page_title': 'Leave Applications From Employees'
        }
        return render(request, "ceo_template/employee_leave_view.html", context)
    else:
        id = request.POST.get('id')
        status = request.POST.get('status')
        if (status == '1'):
            status = 1
        else:
            status = -1
        try:
            leave = get_object_or_404(LeaveReportEmployee, id=id)
            leave.status = status
            leave.save()
            return HttpResponse(True)
        except Exception as e:
            return False


def admin_view_attendance(request):
    departments = Department.objects.all()
    context = {
        'departments': departments,
        'page_title': 'View Attendance'
    }

    return render(request, "ceo_template/admin_view_attendance.html", context)


@csrf_exempt
def get_admin_attendance(request):
    department_id = request.POST.get('department')
    attendance_date_id = request.POST.get('attendance_date_id')
    try:
        department = get_object_or_404(Department, id=department_id)
        attendance = get_object_or_404(AttendanceRecord, id=attendance_date_id)
        attendance_reports = AttendanceRecord.objects.filter(attendance=attendance)
        json_data = []
        for report in attendance_reports:
            data = {
                "status": str(report.status),
                "name": str(report.employee)
            }
            json_data.append(data)
        return JsonResponse(json.dumps(json_data), safe=False)
    except Exception as e:
        return None


def admin_view_profile(request):
    admin = get_object_or_404(Admin, admin=request.user)
    form = AdminForm(request.POST or None, request.FILES or None,
                     instance=admin)
    context = {'form': form,
               'page_title': 'View/Edit Profile'
               }
    if request.method == 'POST':
        try:
            if form.is_valid():
                first_name = form.cleaned_data.get('first_name')
                last_name = form.cleaned_data.get('last_name')
                password = form.cleaned_data.get('password') or None
                passport = request.FILES.get('profile_pic') or None
                custom_user = admin.admin
                if password != None:
                    custom_user.set_password(password)
                if passport != None:
                    fs = FileSystemStorage()
                    filename = fs.save(passport.name, passport)
                    passport_url = fs.url(filename)
                    custom_user.profile_pic = passport_url
                custom_user.first_name = first_name
                custom_user.last_name = last_name
                custom_user.save()
                messages.success(request, "Profile Updated!")
                return redirect(reverse('admin_view_profile'))
            else:
                messages.error(request, "Invalid Data Provided")
        except Exception as e:
            messages.error(
                request, "Error Occured While Updating Profile " + str(e))
    return render(request, "ceo_template/admin_view_profile.html", context)


def admin_notify_manager(request):
    manager = CustomUser.objects.filter(user_type=2)
    context = {
        'page_title': "Send Notifications To Manager",
        'allManager': manager
    }
    return render(request, "ceo_template/manager_notification.html", context)


def admin_notify_employee(request):
    employee = CustomUser.objects.filter(user_type=3)
    context = {
        'page_title': "Send Notifications To Employees",
        'employees': employee
    }
    return render(request, "ceo_template/employee_notification.html", context)


@csrf_exempt
def send_employee_notification(request):
    id = request.POST.get('id')
    message = request.POST.get('message')
    employee = get_object_or_404(Employee, admin_id=id)
    try:
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
        headers = {'Authorization':
                   'key=AAAA3Bm8j_M:APA91bElZlOLetwV696SoEtgzpJr2qbxBfxVBfDWFiopBWzfCfzQp2nRyC7_A2mlukZEHV4g1AmyC6P_HonvSkY2YyliKt5tT3fe_1lrKod2Daigzhb2xnYQMxUWjCAIQcUexAMPZePB',
                   'Content-Type': 'application/json'}
        data = requests.post(url, data=json.dumps(body), headers=headers)
        notification = NotificationEmployee(employee=employee, message=message, created_by=request.user)
        notification.save()
        return HttpResponse("True")
    except Exception as e:
        return HttpResponse("False")


@csrf_exempt
def send_manager_notification(request):
    id = request.POST.get('id')
    message = request.POST.get('message')
    print("******************",id)
    manager = get_object_or_404(Manager, admin_id=id)
    print("******************",manager)
    try:
        url = "https://fcm.googleapis.com/fcm/send"
        body = {
            'notification': {
                'title': "OfficeOps",
                'body': message,
                'click_action': reverse('manager_view_notification'),
                'icon': static('dist/img/AdminLTELogo.png')
            },
            'to': manager.admin.fcm_token
        }
        headers = {'Authorization':
                   'key=AAAA3Bm8j_M:APA91bElZlOLetwV696SoEtgzpJr2qbxBfxVBfDWFiopBWzfCfzQp2nRyC7_A2mlukZEHV4g1AmyC6P_HonvSkY2YyliKt5tT3fe_1lrKod2Daigzhb2xnYQMxUWjCAIQcUexAMPZePB',
                   'Content-Type': 'application/json'}
        data = requests.post(url, data=json.dumps(body), headers=headers)
        notification = NotificationManager(manager=manager, message=message)
        notification.save()
        return HttpResponse("True")
    except Exception as e:
        return HttpResponse("False")


def delete_manager(request, manager_id):
    manager = get_object_or_404(CustomUser, manager__id=manager_id)
    manager.delete()
    messages.success(request, "Manager deleted successfully!")
    return redirect(reverse('manage_manager'))


def delete_employee(request, employee_id):
    employee = get_object_or_404(CustomUser, employee__id=employee_id)
    employee.delete()
    messages.success(request, "Employee deleted successfully!")
    return redirect(reverse('manage_employee'))


def delete_division(request, division_id):
    division = get_object_or_404(Division, id=division_id)
    try:
        division.delete()
        messages.success(request, "Division deleted successfully!")
    except Exception:
        messages.error(
            request, "Sorry, some employees are assigned to this division already. Kindly change the affected employee division and try again")
    return redirect(reverse('manage_division'))


def delete_department(request, department_id):
    department = get_object_or_404(Department, id=department_id)
    department.delete()
    messages.success(request, "Department deleted successfully!")
    return redirect(reverse('manage_department'))


def generate_performance_report(request):
    departments = Department.objects.all()
    
    if request.method == 'POST':
        employee_ids = request.POST.getlist('employee')
        month = request.POST.get('month')
        year = request.POST.get('year')
        department_id = request.POST.get('department')

        if not month or not year:
            messages.error(request, "Month and Year are required fields")
            return redirect('generate_performance_report')
            
        if not department_id and not employee_ids:
            messages.error(request, "Please select at least one filter (Department or Employee)")
            return redirect('generate_performance_report')
        
        try:
            year = int(year)
            month = int(month)
            
            # Get employees based on selection
            employees = Employee.objects.all()
            if department_id and department_id != 'all':
                employees = employees.filter(department_id=department_id)
            if employee_ids:
                employees = employees.filter(admin__id__in=employee_ids)
            
            # Process each employee
            all_reports = []
            for employee in employees:
                user = employee.admin
                # Get the number of days in the selected month
                num_days = monthrange(year, month)[1]
                start_date = datetime(year, month, 1).date()
                end_date = datetime(year, month, num_days).date()
                
                # Initialize counters
                working_days = 0
                present_days = 0
                late_days = 0
                half_days = 0
                absent_days = 0
                total_worked = timedelta()
                total_regular = timedelta()
                total_overtime = timedelta()
                daily_records = []

                # Get all attendance records for the month in one query
                attendance_records = AttendanceRecord.objects.filter(
                    user=user,
                    date__range=(start_date, end_date)
                ).order_by('date').select_related('user')
                # Get all leave records for the month in one query
                leave_records = LeaveReportEmployee.objects.filter(
                    employee=employee,
                    status=1,
                    start_date__lte=end_date,
                    end_date__gte=start_date
                )
                # Create a dictionary to track leave days
                leave_days = defaultdict(Decimal)
                for leave in leave_records:
                    current_date = max(leave.start_date, start_date)
                    end_date_leave = min(leave.end_date, end_date)
                    while current_date <= end_date_leave:
                        if leave.leave_type == "Full-Day":
                            leave_days[current_date] += Decimal('1.0')
                        elif leave.leave_type == "Half-Day":
                            leave_days[current_date] += Decimal('0.5')
                        current_date += timedelta(days=1)

                # Prefetch break records for all attendance records
                attendance_ids = [ar.id for ar in attendance_records]
                break_records = Break.objects.filter(
                    attendance_record_id__in=attendance_ids
                )
                # Create a mapping of attendance ID to break records
                breaks_map = defaultdict(list)
                for br in break_records:
                    breaks_map[br.attendance_record_id].append(br)

                # Process each day of the month
                for day in range(1, num_days + 1):
                    current_date = datetime(year, month, day).date()
                    weekday = current_date.weekday()
                    is_sunday = weekday == 6
                    is_saturday = weekday == 5
                    week_of_month = (day - 1) // 7
                    is_weekend = is_sunday or (is_saturday and week_of_month in [1, 3])
                    
                    # Initialize day_status with default values
                    day_status = {
                        'date': current_date,
                        'is_weekend': is_weekend,
                        'attendance': None,
                        'leave': 0.0,
                        'breaks_taken': 0,
                        'total_break_time': timedelta(),
                        'status': None
                    }

                    if not is_weekend:
                        working_days += 1
                        
                        # Find attendance for this day
                        attendance = next(
                            (ar for ar in attendance_records if ar.date == current_date), 
                            None
                        )
                        leave_hours = leave_days.get(current_date, Decimal('0.0'))
                        
                        if attendance:
                            day_status['attendance'] = attendance
                            day_status['status'] = attendance.status
                            
                            # Process breaks
                            for br in breaks_map.get(attendance.id, []):
                                if br.break_end:
                                    break_duration = br.duration if br.duration else (br.break_end - br.break_start)
                                    day_status['total_break_time'] += break_duration
                                    day_status['breaks_taken'] += 1

                            # Handle attendance status
                            if attendance.status == 'present':
                                present_days += 1
                            elif attendance.status == 'late':
                                late_days += 1

                            # Handle half-day leave with attendance
                            if leave_hours == Decimal('0.5'):
                                day_status['status'] = 'half-day'
                                day_status['leave'] = 0.5
                                half_days += 1

                            # Add working hours
                            if attendance.total_worked:
                                total_worked += attendance.total_worked
                            if attendance.regular_hours:
                                total_regular += attendance.regular_hours
                            if attendance.overtime_hours:
                                total_overtime += attendance.overtime_hours
                        
                        # Handle leave without attendance
                        elif leave_hours > 0:
                            day_status['leave'] = float(leave_hours)
                            if leave_hours == Decimal('0.5'):
                                day_status['status'] = 'half-day'
                                half_days += 1
                            else:
                                day_status['status'] = 'leave'
                                absent_days += 1
                        
                        # No attendance and no leave
                        else:
                            day_status['status'] = 'absent'
                            absent_days += 1

                    daily_records.append(day_status)
                # Convert timedelta to hours
                total_worked_hours = total_worked.total_seconds() / 3600
                total_regular_hours = total_regular.total_seconds() / 3600
                total_overtime_hours = total_overtime.total_seconds() / 3600
                
                # Calculate percentages
                present_percentage = round((present_days / working_days) * 100, 2) if working_days else 0
                absent_percentage = round((absent_days / working_days) * 100, 2) if working_days else 0
                
                report_data = {
                    'employee': employee,
                    'month': month,
                    'month_name': datetime(year, month, 1).strftime('%B'),
                    'year': year,
                    'daily_records': daily_records,
                    'present_days': present_days,
                    'half_days': half_days,
                    'late_days': late_days,
                    'absent_days': absent_days,
                    'total_worked_hours': round(total_worked_hours, 2),
                    'total_regular_hours': round(total_regular_hours, 2),
                    'total_overtime_hours': round(total_overtime_hours, 2),
                    'total_working_days': working_days,
                    'present_percentage': present_percentage,
                    'absent_percentage': absent_percentage,
                }
                all_reports.append(report_data)
            # For HTML preview
            if 'generate_html' in request.POST:
                if len(all_reports) == 1:
                    return render(request, 'ceo_template/attendance_report_pdf.html', all_reports[0])
                else:
                    return render(request, 'ceo_template/multi_employee_report.html', {
                        'all_reports': all_reports,
                        'month_name': datetime(year, month, 1).strftime('%B'),
                        'year': year,
                    })
            
            # For PDF generation
            if 'generate_pdf' in request.POST:
                if len(all_reports) == 1:
                    template = get_template('ceo_template/attendance_report_pdf.html')
                    filename = f"attendance_report_{all_reports[0]['employee'].admin.get_full_name()}_{month}_{year}.pdf"
                else:
                    template = get_template('ceo_template/multi_employee_report.html')
                    filename = f"attendance_report_{month}_{year}.pdf"
                
                html = template.render({
                    'all_reports': all_reports,
                    'month_name': datetime(year, month, 1).strftime('%B'),
                    'year': year,
                } if len(all_reports) > 1 else all_reports[0])
                
                response = HttpResponse(content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                
                pisa_status = pisa.CreatePDF(html, dest=response)
                if pisa_status.err:
                    messages.error(request, 'Error generating PDF')
                    return redirect('generate_performance_report')
                return response
            
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            return redirect('generate_performance_report')
    
    # GET request handling
    all_months = [
        (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
        (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
        (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')
    ]
    current_month = datetime.now().month
    months = all_months[current_month-1:] + all_months[:current_month-1]
    
    context = {
        'departments': departments,
        "page_title": 'Generate Report',
        'months': months,
        'years': range(datetime.now().year, datetime.now().year - 6, -1),
    }
    return render(request, 'ceo_template/generate_report.html', context)