from django.core.mail import send_mail
from django.conf import settings
import threading


def send_leave_email(recipients, subject, content,from_email):
    if not recipients:
        return
    
    try:
        send_mail(
            subject=subject,
            message=content,
            from_email=from_email,
            recipient_list=recipients,
            fail_silently=False
        )
        print("email sending successfully!!",from_email,recipients)
    except Exception as e:
        print(f"Failed to send email: {str(e)}")



def send_emails_in_background(*args,**kwargs):
    thread = threading.Thread(target=send_leave_email,args=args,kwargs=kwargs)
    thread.daemon = True
    thread.start()
