from django.db import models
from django.utils import timezone
from django.conf import settings
from django.urls import reverse
from io import BytesIO
from django.core.files import File
import qrcode
from .utils import generate_barcode


LOCATION_CHOICES = (
    ("Main Room" , "Main Room"),
    ("Meeting Room", "Meeting Room"),
    ("Main Office", "Main Office"),
)

ASSET_CONDITION_CHOICES = [
    ('new', 'New'),
    ('used', 'Used'),
]

DEPARTMENT_CHOICE = [
    ('hr', 'HR'),
    ('python', 'Python'),
    ('admin', 'Admin'),
    ('javascript','JavaScript')
]


class AssetCategory(models.Model):
    category = models.CharField(max_length=100,unique=True)

    def save(self,*args,**kwargs):
        self.category = self.category.lower()
        super().save(*args,**kwargs)

    def __str__(self):
        return self.category

class Assets(models.Model):
    asset_category = models.ForeignKey(AssetCategory, on_delete=models.CASCADE)
    asset_name = models.CharField(max_length=100,blank=True,null=True)
    asset_serial_number = models.CharField(max_length=100, unique=True)
    asset_brand = models.CharField(max_length=100)
    asset_image = models.ImageField(upload_to='images/', blank=True, null=True)
    manager = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='managed_assets')
    
    is_asset_issued = models.BooleanField(default=False)
    asset_added_date = models.DateTimeField(default=timezone.now)
    updated_date = models.DateTimeField(auto_now=True)
    return_date = models.DateTimeField(null=True, blank=True)

    asset_condition = models.CharField(max_length=100, choices=ASSET_CONDITION_CHOICES, blank=True, null=True)
    os_version = models.CharField(max_length=100, blank=True, null=True,default=None)
    ip_address = models.CharField(blank=True, null=True,default=None)
    
    barcode = models.ImageField(upload_to='barcodes/', blank=True, null=True)


    def save(self, *args, **kwargs):
        if not self.pk:
            super().save(*args, **kwargs)

        if not self.barcode:
            barcode_file = generate_barcode(self.id)
            self.barcode.save(barcode_file.name, barcode_file, save=False)

        super().save(*args, **kwargs)
    

    @property
    def status(self):
       return "Active" if self.is_asset_issued else "Not Active"
    

    def __str__(self):
        return f"{self.asset_name} ({self.asset_serial_number})"

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
        return f"{self.asset.asset_name} issued to {self.asset_assignee}"

    def get_absolute_url(self):
        return reverse('assets-detail', kwargs={'pk': self.pk})


class Notify_Manager(models.Model):
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='manager_notifications')
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='asset_requests',null=True)
    asset = models.ForeignKey(Assets, on_delete=models.CASCADE, related_name='manager_notifications',null=True)  # <-- ADD THIS
    message = models.TextField()
    approved = models.BooleanField(null=True,default=None)
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
