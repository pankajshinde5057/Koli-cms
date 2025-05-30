import json
import pytz
import requests
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils import timezone
import psutil
from .forms import *
from .models import *
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import BasicAuthentication
from rest_framework import status
from datetime import datetime, time
from dotenv import load_dotenv
import os
from django.urls import reverse
from django.http import JsonResponse, HttpResponseRedirect
from django.http import HttpResponseForbidden
from django.db.models import Q
from django.contrib.auth.models import User

load_dotenv()

SITE_KEY = os.getenv('SITE_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')

def login_page(request):
    if request.user.is_authenticated:
        if request.user.user_type == "1":
            return redirect(reverse("admin_home"))
        elif request.user.user_type == "2":
            return redirect(reverse("manager_home"))
        else:
            return redirect(reverse("employee_home"))
    return render(request, "main_app/login.html",{'SITE_KEY' : SITE_KEY})


def doLogin(request):
    if request.method != "POST":
        return redirect('login_page')  

    user = authenticate(
        request,
        username=request.POST.get("email"),
        password=request.POST.get("password"),
    )
    if user:
        login(request, user)
        if user.user_type == "1":
            return redirect("admin_home")
        elif user.user_type == "2":
            return redirect("manager_home")
        else:
            return redirect("employee_home")
    else:
        messages.error(request, "Invalid details")
        return redirect('login_page')
    

def logout_user(request):
    if request.user != None:
        logout(request)
    return redirect('login_page')


def get_router_ip():
    for conn in psutil.net_if_addrs().values():
        for snic in conn:
            if snic.family.name == "AF_INET" and snic.address != "127.0.0.1":
                return snic.address
    return None


class AttendanceActionView(APIView):
    authentication_classes = [BasicAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        action = request.data.get('action')
        notes = request.data.get('notes', '')

        current_record = AttendanceRecord.objects.filter(
            user=user, clock_out__isnull=True
        ).first()
        if action == 'clockin':
            if current_record:
                return Response({'error': 'Already clocked in'}, status=status.HTTP_400_BAD_REQUEST)

            new_record = AttendanceRecord.objects.create(
                user=user,
                clock_in=timezone.now(),
                notes=notes,
                ip_address=get_router_ip()
            )

            ActivityFeed.objects.create(
                user=user,
                activity_type='clock_in',
                related_record=new_record
            )

            return Response({'status': 'success', 'action': 'clocked_in'})

        elif action == 'clockout':
            if not current_record:
                return Response({'error': 'You are not clocked in'}, status=status.HTTP_400_BAD_REQUEST)

            current_record.clock_out = timezone.now()
            current_record.notes = notes
            current_record.save()

            ActivityFeed.objects.create(
                user=user,
                activity_type='clock_out',
                related_record=current_record
            )

            return Response({'status': 'success', 'action': 'clocked_out'})

        elif action == 'break':
            if not current_record:
                return Response({'error': 'You must be clocked in to take a break'}, status=status.HTTP_400_BAD_REQUEST)

            current_break = Break.objects.filter(
                attendance_record=current_record,
                break_end__isnull=True
            ).first()

            if current_break:
                # End break
                current_break.break_end = timezone.now()
                current_break.save()

                ActivityFeed.objects.create(
                    user=user,
                    activity_type='break_end',
                    related_record=current_record
                )
                return Response({'status': 'success', 'action': 'break_ended'})

            else:
                # Start break
                Break.objects.create(
                    attendance_record=current_record,
                    break_start=timezone.now()
                )

                ActivityFeed.objects.create(
                    user=user,
                    activity_type='break_start',
                    related_record=current_record
                )
                return Response({'status': 'success', 'action': 'break_started'})

        else:
            return Response({'error': 'Invalid action'}, status=status.HTTP_400_BAD_REQUEST)


# @login_required
# def clock_in_out(request):
#     if request.method == 'POST':
#         now = timezone.now()
#         current_record = AttendanceRecord.objects.filter(
#             user=request.user, 
#             clock_out__isnull=True
#         ).first()

#         if current_record:
#             # Clock out
#             current_record.clock_out = now
#             current_record.notes = request.POST.get('notes', '')
#             current_record.save()
#             ActivityFeed.objects.create(
#                 user=request.user,
#                 activity_type='clock_out',
#                 related_record=current_record
#             )
#         else:
#             department_id = request.POST.get('department')
#             department = Department.objects.get(id=department_id) if department_id else None
#             # Convert to IST
#             ist = pytz.timezone('Asia/Kolkata')
#             ist_time = now.astimezone(ist)

#             # Create 9:15 AM and 1:00 PM on the same IST date
#             late_time = ist.localize(datetime.combine(ist_time.date(), time(9, 15)))
#             half_day_time = ist.localize(datetime.combine(ist_time.date(), time(13, 0)))  # 1:00 PM

#             print("Current IST Time:", ist_time)
#             print("Late Time Threshold:", late_time)
#             print("Half Day Threshold:", half_day_time)

#             # Compare
#             if ist_time > half_day_time:
#                 status = 'half_day'
#             elif ist_time > late_time:
#                 status = 'late'
#             else:
#                 status = 'present'

#             new_record = AttendanceRecord.objects.create(
#                 user=request.user,
#                 date = now.date(),
#                 clock_in=now,
#                 department=department,
#                 notes=request.POST.get('notes', ''),
#                 ip_address=get_router_ip(),
#                 status=status
#             )

#             ActivityFeed.objects.create(
#                 user=request.user,
#                 activity_type='clock_in',
#                 related_record=new_record
#             )

#         return JsonResponse({'status': 'success'})
#     return redirect('home')

import logging



from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from datetime import datetime, time, timedelta
from calendar import monthrange
from django.db.models import Sum, F, ExpressionWrapper, DurationField
from django.db.models.functions import Coalesce
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.contrib import messages
from .models import AttendanceRecord, Employee, Department, DailySchedule, ActivityFeed, Break, Holiday, LeaveReportEmployee
import pytz
import logging

logger = logging.getLogger(__name__)

@login_required
def clock_in_out(request):
    if request.method == 'POST':
        now = timezone.now()
        today = now.date()
        logger.debug(f"Processing clock_in_out for user {request.user} on {today} at {now}")

        # Check for any existing record for today
        existing_record = AttendanceRecord.objects.filter(
            user=request.user,
            date=today
        ).first()

        if 'clock_in' in request.POST:
            if existing_record:
                logger.warning(f"User {request.user} attempted to clock in again on {today}. Existing record: {existing_record.id}")
                return JsonResponse({
                    'status': 'error',
                    'message': 'You can only clock in once per day.'
                }, status=400)

            # Convert to IST
            ist = pytz.timezone('Asia/Kolkata')
            ist_time = now.astimezone(ist)
            logger.debug(f"Clock-in time in IST: {ist_time}")
            
            # Define time thresholds
            on_time_threshold = datetime.combine(ist_time.date(), time(9, 0)).replace(tzinfo=ist)
            late_threshold = datetime.combine(ist_time.date(), time(9, 15)).replace(tzinfo=ist)
            half_day_threshold = datetime.combine(ist_time.date(), time(13, 0)).replace(tzinfo=ist)
            after_3pm_threshold = datetime.combine(ist_time.date(), time(15, 0)).replace(tzinfo=ist)

            if request.user.user_type == "3":  # Employee
                earliest_clock_in = ist.localize(datetime.combine(ist_time.date(), time(8, 45)))
            elif request.user.user_type == "2":  # Manager
                earliest_clock_in = ist.localize(datetime.combine(ist_time.date(), time(8, 30)))
            else:
                earliest_clock_in = ist.localize(datetime.combine(ist_time.date(), time(0, 0)))

            if ist_time < earliest_clock_in:
                logger.warning(f"User {request.user} (type {request.user.user_type}) attempted to clock in too early at {ist_time}")
                return JsonResponse({
                    'status': 'error',
                    'message': f"Clock-in is not allowed before {'8:45 AM' if request.user.user_type == '3' else '8:30 AM'} IST."
                }, status=400)
            
            # Determine status based on clock-in time
            if ist_time > after_3pm_threshold:
                status = 'present'  # After 3:00 PM, count as present
            elif ist_time > half_day_threshold:
                status = 'half_day'  # Between 1:00 PM and 3:00 PM
            elif ist_time > late_threshold:
                status = 'late'  # After 9:15 AM but before 1:00 PM
            else:
                status = 'present'  # Before 9:15 AM

            logger.debug(f"Assigned status: {status} for clock-in at {ist_time}")

            # Proceed with clock-in logic
            department_id = request.POST.get('department')
            department = Department.objects.get(id=department_id) if department_id else None

            # Create new attendance record
            new_record = AttendanceRecord.objects.create(
                user=request.user,
                date=today,
                clock_in=now,
                department=department,
                notes=request.POST.get('notes', ''),
                ip_address=request.META.get('REMOTE_ADDR'),
                status=status
            )
            try:
                new_record.full_clean()
                new_record.save()
                
                logger.debug(f"Saved record status: {new_record.status} for clock-in at {new_record.clock_in.astimezone(ist)}")
                
                ActivityFeed.objects.create(
                    user=request.user,
                    activity_type='clock_in',
                    related_record=new_record
                )
                
                return JsonResponse({
                    'status': 'success',
                    'message': 'Successfully clocked in! Please create your daily schedule within 30 minutes.'
                })
            except ValidationError as e:
                logger.error(f"Error creating attendance record for {request.user}: {e}")
                return JsonResponse({
                    'status': 'error',
                    'message': f"Error clocking in: {e}"
                }, status=400)

        elif 'clock_out' in request.POST:
            current_record = AttendanceRecord.objects.filter(
                user=request.user,
                date=today,
                clock_out__isnull=True
            ).first()

            if not current_record:
                return JsonResponse({
                    'status': 'error',
                    'message': 'No active clock-in record found to clock out.'
                }, status=400)

            # Check for daily updates
            if request.user.user_type == '3':
                try:
                    employee = Employee.objects.get(admin=request.user)
                    schedule = DailySchedule.objects.get(employee=employee, date=today)
                    if not schedule.updates.exists():
                        return JsonResponse({
                            'status': 'error',
                            'message': 'Cannot clock out without submitting a daily update.',
                            'redirect_url': '/todays_update/'
                        }, status=400)
                except (Employee.DoesNotExist, DailySchedule.DoesNotExist):
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Cannot clock out without a valid schedule and update.',
                        'redirect_url': '/daily_schedule/'
                    }, status=400)
            
            # Clock out
            current_record.clock_out = now
            current_record.notes = request.POST.get('notes', '')
            try:
                current_record.full_clean()
                current_record.save()

                ActivityFeed.objects.create(
                    user=request.user,
                    activity_type='clock_out',
                    related_record=current_record
                )

                return JsonResponse({
                    'status': 'success',
                    'message': 'Successfully clocked out!'
                })
            except ValidationError as e:
                return JsonResponse({
                    'status': 'error',
                    'message': f"Error clocking out: {e}"
                }, status=400)

        else:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid request.'
            }, status=400)

    return HttpResponseRedirect('manager_home' if request.user.user_type == "2" else 'employee_home')



@login_required
def break_action(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        action_type = data.get('action', 'start_or_end')
        user_id = data.get('user_id', None)

        # Determine the user to check (default to current user)
        target_user = request.user
        if user_id and request.user.has_perm('your_app.can_manage_employees'):  # Replace with actual permission
            try:
                target_user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return JsonResponse({'error': 'User not found'}, status=400)

        current_record = AttendanceRecord.objects.filter(
            user=target_user, 
            clock_out__isnull=True
        ).first()
        
        if not current_record:
            return JsonResponse({'error': 'You must be clocked in to take a break'}, status=400)
        
        if action_type == 'check_lunch':
            today = timezone.now().date()
            lunch_taken = Break.objects.filter(
                attendance_record__user=target_user,
                break_type='lunch',
                break_start__date=today
            ).exists()
            return JsonResponse({'lunch_taken': lunch_taken})
        
        current_break = Break.objects.filter(
            attendance_record=current_record,
            break_end__isnull=True
        ).first()
        
        if current_break:
            # End break
            current_break.break_end = timezone.now()
            current_break.save()
            ActivityFeed.objects.create(
                user=target_user,
                activity_type='break_end',
                related_record=current_record
            )
            action = 'break_ended'
        else:
            # Start break
            break_type = data.get('break_type', 'short')
            
            if break_type == 'lunch':
                today = timezone.now().date()
                lunch_taken = Break.objects.filter(
                    attendance_record__user=target_user,
                    break_type='lunch',
                    break_start__date=today
                ).exists()
                
                if lunch_taken:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'You have already taken your lunch break today.',
                        'title': 'Lunch Break Unavailable'
                    }, status=400)
            
            new_break = Break.objects.create(
                attendance_record=current_record,
                break_start=timezone.now(),
                break_type=break_type
            )
            
            activity_type = 'break_start_short' if break_type == 'short' else 'break_start_lunch'
            ActivityFeed.objects.create(
                user=target_user,
                activity_type=activity_type,
                related_record=current_record
            )
            action = f'break_started_{break_type}'
        
        return JsonResponse({'status': 'success', 'action': action})
    
    return JsonResponse({'error': 'Invalid request'}, status=400)



@csrf_exempt
def get_attendance(request):
    department_id = request.POST.get("department")

    if not department_id:
        return JsonResponse({'error': 'Department ID not provided'}, status=400)

    try:
        department = get_object_or_404(Department, id=department_id)
 
        # Get employees in that department
        employees = Employee.objects.filter(department=department)
        user_ids = employees.values_list('admin_id', flat=True)
 
        # Fetch attendance records of those users
        attendance = AttendanceRecord.objects.filter(user_id__in=user_ids)
 
        attendance_list = [
            {"id": attd.id, "attendance_date": str(attd.date)}
            for attd in attendance
        ]
        return JsonResponse(attendance_list, safe=False)
 
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

def showFirebaseJS(request):
    data = """
    // Give the service worker access to Firebase Messaging.
// Note that you can only use Firebase Messaging here, other Firebase libraries
// are not available in the service worker.
importScripts('https://www.gstatic.com/firebasejs/7.22.1/firebase-app.js');
importScripts('https://www.gstatic.com/firebasejs/7.22.1/firebase-messaging.js');

// Initialize the Firebase app in the service worker by passing in
// your app's Firebase config object.
// https://firebase.google.com/docs/web/setup#config-object
firebase.initializeApp({
    apiKey: "AIzaSyBarDWWHTfTMSrtc5Lj3Cdw5dEvjAkFwtM",
    authDomain: "sms-with-django.firebaseapp.com",
    databaseURL: "https://sms-with-django.firebaseio.com",
    projectId: "sms-with-django",
    storageBucket: "sms-with-django.appspot.com",
    messagingSenderId: "945324593139",
    appId: "1:945324593139:web:03fa99a8854bbd38420c86",
    measurementId: "G-2F2RXTL9GT"
});

// Retrieve an instance of Firebase Messaging so that it can handle background
// messages.
const messaging = firebase.messaging();
messaging.setBackgroundMessageHandler(function (payload) {
    const notification = JSON.parse(payload);
    const notificationOption = {
        body: notification.body,
        icon: notification.icon
    }
    return self.registration.showNotification(payload.notification.title, notificationOption);
});
    """
    return HttpResponse(data, content_type='application/javascript')


@login_required
def early_clock_out_request(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            reason = data.get('reason')
            if not reason:
                return JsonResponse({
                    'status' : 'error',
                    'message' : 'Reason is require'
                },status=400)
            attendance_record = AttendanceRecord.objects.filter(
                user = request.user,
                date = timezone.now().date(),
                clock_out__isnull = True
            ).first()

            if not attendance_record:
                return JsonResponse({
                    'status': 'error',
                    'message': 'No active attendance record found'
                }, status=400)
        
            if EarylyClockOutRequest.objects.filter(
                    attendance_record=attendance_record,
                    status__in=['pending', 'approved']
                ).exists():
                    return JsonResponse({
                        'status': 'error', 
                        'message': 'An early clock-out request is already pending or approved for this shift'
                    }, status=400)
            EarylyClockOutRequest.objects.create(
                attendance_record=attendance_record,
                user=request.user,
                reason=reason
            )
            return JsonResponse({'status': 'success', 'message': 'Request submitted'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)
        

@login_required
def check_early_clock_out_status(request):
    try:
        attendance_record = AttendanceRecord.objects.filter(
            user=request.user,
            date=timezone.now().date(),
            clock_out__isnull=True
        ).first()

        if not attendance_record:
            return JsonResponse({'status': 'success', 'request_status': 'none', 'message': ''})

        early_request = EarylyClockOutRequest.objects.filter(
            attendance_record=attendance_record
        ).order_by('-submitted_at').first()

        if not early_request:
            return JsonResponse({'status': 'success', 'request_status': 'none', 'message': ''})

        response = {
            'status': 'success',
            'request_status': early_request.status,
            'message': early_request.notes or ''
        }
        return JsonResponse(response)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    

@login_required
def approve_early_clock_out(request, request_id):
    if request.method == 'POST':
        early_request = get_object_or_404(EarylyClockOutRequest, id=request_id)
        notes = request.POST.get('notes', '')
        early_request.status = 'approved'
        early_request.reviewed_by = request.user
        early_request.notes = notes
        early_request.save()
        return redirect('manager_view_notification')

    return HttpResponseForbidden("Invalid request")


@login_required
def deny_early_clock_out(request, request_id):
    if request.method == 'POST':
        early_request = get_object_or_404(EarylyClockOutRequest, id=request_id)
        notes = request.POST.get('notes', '')
        early_request.status = 'denied'
        early_request.reviewed_by = request.user
        early_request.notes = notes
        early_request.save()
        return redirect('manager_view_notification')

    return HttpResponseForbidden("Invalid request")


@login_required
def all_employees_schedules(request):
    if not request.user.user_type in ['1','2']:
        messages.error(request, "You do not have permission to access this page.")

    # Get filter parameters
    filter_type = request.GET.get('filter_type', 'today')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    department_id = request.GET.get('department_id')
    search_name = request.GET.get('search_name', '').strip()

    # Base queryset: all schedules
    schedules = DailySchedule.objects.all().order_by('-date')

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

    # Apply department filter
    if department_id and department_id != 'all':
        schedules = schedules.filter(employee__department__id=department_id)

    # Apply name search
    if search_name:
        schedules = schedules.filter(
            Q(employee__admin__first_name__icontains=search_name) |
            Q(employee__admin__last_name__icontains=search_name)
        )

    # Get all departments and employees for filters
    departments = Department.objects.all().order_by('name')

    return render(request, 'main_app/employees_schedule.html', {
        'schedules': schedules,
        'today': today,
        'filter_type': filter_type,
        'start_date': start_date,
        'end_date': end_date,
        'department_id': department_id,
        'search_name': search_name,
        'departments': departments
    })

