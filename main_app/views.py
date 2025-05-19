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

# Set up logging for debugging
logger = logging.getLogger(__name__)

@login_required
def clock_in_out(request):
    if request.method == 'POST':
        now = timezone.now()
        today = now.date()
        logger.debug(f"Processing clock_in_out for user {request.user} on {today}")

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
            
            late_time = datetime.combine(ist_time.date(), time(9, 15)).replace(tzinfo=ist)
            half_day_time = datetime.combine(ist_time.date(), time(13, 0)).replace(tzinfo=ist)

            print(f"IST Time Now: {ist_time}, Late Time: {late_time}, Half Day Time: {half_day_time}")

            if request.user.user_type == "3":  # Employee
                earliest_clock_in = ist.localize(datetime.combine(ist_time.date(), time(8, 45)))
            elif request.user.user_type == "2":  # Manager
                earliest_clock_in = ist.localize(datetime.combine(ist_time.date(), time(8, 30)))
            else:
                earliest_clock_in = ist.localize(datetime.combine(ist_time.date(), time(0, 0)))  # No restriction for other types

            if ist_time < earliest_clock_in:
                logger.warning(f"User {request.user} (type {request.user.user_type}) attempted to clock in too early at {ist_time}")
                return JsonResponse({
                    'status': 'error',
                    'message': f"Clock-in is not allowed before {'8:45 AM' if request.user.user_type == '3' else '8:30 AM'} IST."
                }, status=400)
            
            # Proceed with clock-in logic
            department_id = request.POST.get('department')
            department = Department.objects.get(id=department_id) if department_id else None
            
            # Create 9:15 AM and 1:00 PM on the same IST date
       

            # # Determine status
            # if ist_time > half_day_time:
            #     status = 'half_day'
            # elif ist_time > late_time:
            #     status = 'late'
            # else:
            #     status = 'present'

            logger.debug(f"Creating new attendance record for {request.user} with status {status}")
            print('half_day' if ist_time > half_day_time else 'late' if ist_time > late_time else 'present', "*"*20)
            # Create new attendance record
            new_record = AttendanceRecord.objects.create(
                user=request.user,
                date=today,
                clock_in=now,
                department=department,
                notes=request.POST.get('notes', ''),
                ip_address=request.META.get('REMOTE_ADDR'),
                status=  'half_day' if ist_time > half_day_time else 'late' if ist_time > late_time else 'present'
            )

            # Log activity
            ActivityFeed.objects.create(
                user=request.user,
                activity_type='clock_in',
                related_record=new_record
            )

            return JsonResponse({'status': 'success'})

        elif 'clock_out' in request.POST:
            current_record = AttendanceRecord.objects.filter(
                user=request.user,
                date=today,
                clock_out__isnull=True
            ).first()

            if not current_record:
                logger.warning(f"User {request.user} attempted to clock out on {today} with no active record")
                return JsonResponse({
                    'status': 'error',
                    'message': 'No active clock-in record found to clock out.'
                }, status=400)

            # Clock out
            current_record.clock_out = now
            current_record.notes = request.POST.get('notes', '')
            current_record.save()

            # Log activity
            ActivityFeed.objects.create(
                user=request.user,
                activity_type='clock_out',
                related_record=current_record
            )

            logger.debug(f"User {request.user} clocked out successfully on {today}")

            return JsonResponse({'status': 'success'})

        else:
            logger.error(f"Invalid POST request for {request.user}: {request.POST}")
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid request.'
            }, status=400)

    logger.debug(f"Redirecting {request.user} to employee_home")
    return HttpResponseRedirect('employee_home')

@login_required
def break_action(request):
    if request.method == 'POST':
        current_record = AttendanceRecord.objects.filter(
            user=request.user, 
            clock_out__isnull=True
        ).first()
        
        if not current_record:
            return JsonResponse({'error': 'You must be clocked in to take a break'}, status=400)
        
        current_break = Break.objects.filter(
            attendance_record=current_record,
            break_end__isnull=True
        ).first()
        
        if current_break:
            # End break
            current_break.break_end = timezone.now()
            current_break.save()
            ActivityFeed.objects.create(
                user=request.user,
                activity_type='break_end',
                related_record=current_record
            )
            action = 'break_ended'
        else:
            # Start break
            data = json.loads(request.body)
            break_type = data.get('break_type', 'short')
            
            # Check if trying to take lunch break and already took one today
            if break_type == 'lunch':
                today = timezone.now().date()
                lunch_taken = Break.objects.filter(
                    attendance_record__user=request.user,
                    break_type='lunch',
                    break_start__date=today
                ).exists()
                
                if lunch_taken:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'You can only take one lunch break per day'
                    }, status=400)
            
            new_break = Break.objects.create(
                attendance_record=current_record,
                break_start=timezone.now(),
                break_type=break_type
            )
            
            activity_type = 'break_start_short' if break_type == 'short' else 'break_start_lunch'
            ActivityFeed.objects.create(
                user=request.user,
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

