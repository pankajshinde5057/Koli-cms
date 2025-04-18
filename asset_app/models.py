from django.db import models
from django.utils import timezone
from django.conf import settings
from django.urls import reverse
from io import BytesIO
from django.core.files import File
import qrcode
from .utils import generate_qr_code

ASSET_CHOICES = (
    ("Desk", "Desk"),
    ("Laptop", "Laptop"),
    ("IP Phone", "IP Phone"),
    ("Project", "Project"),
)

LOCATION_CHOICES = (
    ("Main Room" , "Main Room"),
    ("Meeting Room", "Meeting Room"),
)

class Assets(models.Model):
    asset_name = models.CharField(max_length=100, choices=ASSET_CHOICES)
    asset_serial_No = models.CharField(max_length=100, unique=True)
    asset_manufacturer = models.CharField(max_length=100)
    date_purchased = models.DateTimeField(null=True, blank=True,default=timezone.now())
    asset_issued = models.BooleanField(default=False)
    asset_image = models.ImageField(upload_to='images/', blank=True, null=True)
    asset_assignee = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name='claimed_assets')
    manager = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='managed_assets')

    qr_code = models.ImageField(upload_to='qr_codes/', blank=True, null=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        qr_data = f"http://192.168.1.56:8000/asset-app/api/asset/{self.id}/detail/" 
        qr_file = generate_qr_code(qr_data, f"{self.asset_serial_No}_qr.png")

        if not self.qr_code:
            self.qr_code.save(qr_file.name, qr_file, save=False)
            super().save(update_fields=['qr_code'])

    @property
    def status(self):
        return "Active" if self.asset_issued else "Not Active"
    

    def __str__(self):
        return f"{self.asset_name} ({self.asset_serial_No})"

    def get_absolute_url(self):
        return reverse('assets-detail', kwargs={'pk': self.pk})


class Assetssearch(models.Model):
    name = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    description = models.TextField()

    def __str__(self):
        return self.name


class AssetsIssuance(models.Model):
    asset = models.ForeignKey(Assets, on_delete=models.PROTECT)
    asset_location = models.CharField(max_length=100, choices=LOCATION_CHOICES)
    date_issued = models.DateTimeField(default=timezone.now)
    asset_assignee = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)

    def __str__(self):
        return str(self.asset)

    def get_absolute_url(self):
        return reverse('assets-detail', kwargs={'pk': self.pk})


class Notify_Manager(models.Model):
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='manager_notifications')
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='asset_requests',null=True)
    asset = models.ForeignKey(Assets, on_delete=models.CASCADE, related_name='manager_notifications',null=True)  # <-- ADD THIS
    message = models.TextField()
    approved = models.BooleanField(default=False,null=True)  # <-- optional, if you are using 'note.approved' in template
    timestamp = models.DateTimeField(default=timezone.now)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"Notification to {self.manager.first_name} {self.manager.last_name} at {self.timestamp}"

    @property
    def status(self):
        if self.approved is True:
            return "Approved"
        elif self.approved is False:
            return "Rejected"
        return "Pending"


class Notify_Employee(models.Model):
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='employee_notifications')
    message = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"Notification to {self.employee.first_name} {self.employee.last_name} at {self.timestamp}"

    class Meta:
        verbose_name = "Employee Notification"
        verbose_name_plural = "Employee Notifications"
        ordering = ['-timestamp'] 
