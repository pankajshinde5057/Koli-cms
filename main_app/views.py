import json
import requests
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render, reverse
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
# Create your views here.


def login_page(request):
    if request.user.is_authenticated:
        if request.user.user_type == "1":
            return redirect(reverse("admin_home"))
        elif request.user.user_type == "2":
            return redirect(reverse("manager_home"))
        else:
            return redirect(reverse("employee_home"))
    return render(request, "main_app/login.html")


def doLogin(request, **kwargs):
    if request.method != "POST":
        return HttpResponse("<h4>Denied</h4>")
    else:
        # Google recaptcha
        captcha_token = request.POST.get("g-recaptcha-response")
        captcha_url = "https://www.google.com/recaptcha/api/siteverify"
        captcha_key = "6LcccxsrAAAAAOe4_jxUb9yj1Tu4gqxaIG5U_HCh"
        data = {"secret": captcha_key, "response": captcha_token}
        # Make request
        try:
            captcha_server = requests.post(url=captcha_url, data=data)
            response = json.loads(captcha_server.text)
            if response["success"] == False:
                messages.error(request, "Invalid Captcha. Try Again")
                return redirect("/")
        except:
            messages.error(request, "Captcha could not be verified. Try Again")
            return redirect("/")

        # Authenticate
        user = authenticate(
            request,
            username=request.POST.get("email"),
            password=request.POST.get("password"),
        )
        if user != None:
            login(request, user)
            if user.user_type == "1":
                return redirect(reverse("admin_home"))
            elif user.user_type == "2":
                return redirect(reverse("manager_home"))
            else:
                return redirect(reverse("employee_home"))
        else:
            messages.error(request, "Invalid details")
            return redirect("/")


def logout_user(request):
    if request.user != None:
        logout(request)
    return redirect("/")


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


@login_required
def clock_in_out(request):
    if request.method == 'POST':
        current_record = AttendanceRecord.objects.filter(
            user=request.user, 
            clock_out__isnull=True
        ).first()
        
        if current_record:
            # Clock out
            current_record.clock_out = timezone.now()
            current_record.notes = request.POST.get('notes', '')
            current_record.save()
            
            ActivityFeed.objects.create(
                user=request.user,
                activity_type='clock_out',
                related_record=current_record
            )
        else:
            # Clock in
            department_id = request.POST.get('department')
            department = Department.objects.get(id=department_id) if department_id else None
            
            new_record = AttendanceRecord.objects.create(
                user=request.user,
                clock_in=timezone.now(),
                department=department,
                notes=request.POST.get('notes', ''),
                ip_address= get_router_ip()
            )
            
            ActivityFeed.objects.create(
                user=request.user,
                activity_type='clock_in',
                related_record=new_record
            )
        
        return JsonResponse({'status': 'success'})
    
    # For GET requests, redirect to dashboard
    return redirect('home')

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
            new_break = Break.objects.create(
                attendance_record=current_record,
                break_start=timezone.now()
            )
            ActivityFeed.objects.create(
                user=request.user,
                activity_type='break_start',
                related_record=current_record
            )
            action = 'break_started'
        
        return JsonResponse({'status': 'success', 'action': action})
    
    return JsonResponse({'error': 'Invalid request'}, status=400)


@csrf_exempt
def get_attendance(request):
    department_id = request.POST.get("department")
    try:
        department = get_object_or_404(Department, id=department_id)
        attendance = AttendanceRecord.objects.filter(department=department)

        attendance_list = []
        for attd in attendance:
            data = {"id": attd.id, "attendance_date": str(attd.date)}
            attendance_list.append(data)
        return JsonResponse(json.dumps(attendance_list), safe=False)
    except Exception as e:
        return None


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

