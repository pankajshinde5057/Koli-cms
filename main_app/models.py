from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import UserManager
from django.db import models
from django.db.models import Sum,Min,Max
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import timedelta
from django.core.exceptions import ValidationError

class CustomUserManager(UserManager):
    def _create_user(self, email, password, **extra_fields):
        email = self.normalize_email(email)
        user = CustomUser(email=email, **extra_fields)
        user.password = make_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        assert extra_fields["is_staff"]
        assert extra_fields["is_superuser"]
        return self._create_user(email, password, **extra_fields)


class CustomUser(AbstractUser):
    USER_TYPE = ((1, "CEO"), (2, "Manager"), (3, "Employee"))
    GENDER = [("M", "Male"), ("F", "Female")]
    
    
    username = None  # Removed username, using email instead
    email = models.EmailField(unique=True)
    user_type = models.CharField(default=1, choices=USER_TYPE, max_length=1)
    gender = models.CharField(max_length=1, choices=GENDER)
    profile_pic = models.ImageField()
    address = models.TextField()
    fcm_token = models.TextField(default="")  # For firebase notifications
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = CustomUserManager()

    def __str__(self):
        return self.first_name + " " + self.last_name


class Admin(models.Model):
    admin = models.OneToOneField(CustomUser, on_delete=models.CASCADE,related_name='admin')



class Division(models.Model):
    name = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name



class Department(models.Model):
    name = models.CharField(max_length=120)
    division = models.ForeignKey(Division, on_delete=models.CASCADE)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Manager(models.Model):
    division = models.ForeignKey(Division, on_delete=models.DO_NOTHING, null=True, blank=False)
    department = models.ForeignKey(Department, on_delete=models.DO_NOTHING, null=True, blank=False)

    admin = models.OneToOneField(CustomUser, on_delete=models.CASCADE,related_name='manager')

    def __str__(self):
        return self.admin.last_name + " " + self.admin.first_name


class Employee(models.Model):
    admin = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='employee')
    division = models.ForeignKey(Division, on_delete=models.DO_NOTHING, null=True, blank=False)
    department = models.ForeignKey(Department, on_delete=models.DO_NOTHING, null=True, blank=False)

    def __str__(self):
        return self.admin.first_name +" "+self.admin.last_name 


class LeaveReportEmployee(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    date = models.CharField(max_length=60)
    message = models.TextField()
    status = models.SmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class LeaveReportManager(models.Model):
    manager = models.ForeignKey(Manager, on_delete=models.CASCADE)
    date = models.CharField(max_length=60)
    message = models.TextField()
    status = models.SmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class FeedbackEmployee(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    feedback = models.TextField()
    reply = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class FeedbackManager(models.Model):
    manager = models.ForeignKey(Manager, on_delete=models.CASCADE)
    feedback = models.TextField()
    reply = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class NotificationManager(models.Model):
    manager = models.ForeignKey(Manager, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class NotificationEmployee(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class EmployeeSalary(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    base = models.FloatField(default=0)
    ctc = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)



class AttendanceRecord(models.Model):
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('half_day', 'Half Day'),
        ('on_leave', 'On Leave'),
    ]
    
    user = models.ForeignKey('CustomUser', on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField(auto_now_add=True)
    clock_in = models.DateTimeField()
    clock_out = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='present')
    department = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    location = models.CharField(max_length=255, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    
    # Time calculations
    total_worked = models.DurationField(null=True, blank=True)
    regular_hours = models.DurationField(null=True, blank=True)
    overtime_hours = models.DurationField(null=True, blank=True)
    
    # Flags
    is_primary_record = models.BooleanField(default=False)
    requires_verification = models.BooleanField(default=False)
    
    # Verification
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey('CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_attendances')
    verification_time = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', 'user__email']
        indexes = [
            models.Index(fields=['user', 'date']),
            models.Index(fields=['date', 'department']),
            models.Index(fields=['status']),
        ]
        unique_together = [['user', 'date', 'clock_in']]  # Prevent duplicate clock-ins
    
    def clean(self):
        if self.clock_out and self.clock_in and self.clock_out < self.clock_in:
            raise ValidationError("Clock out time cannot be before clock in time.")
        
        # Ensure clock-in is on the same date
        if self.clock_in.date() != self.date:
            raise ValidationError("Clock in time must be on the same date as the attendance record.")
        
        if self.clock_out and self.clock_out.date() != self.date:
            raise ValidationError("Clock out time must be on the same date as the attendance record.")
    
    def save(self, *args, **kwargs):
        # Calculate time durations if clock_out exists
        if self.clock_out:
            self.total_worked = self.clock_out - self.clock_in
            
            # Calculate regular vs overtime (assuming 8 hours is regular)
            regular_hours_limit = timezone.timedelta(hours=8)
            
            # For individual records, we'll calculate partial regular/overtime
            if self.total_worked > regular_hours_limit:
                self.regular_hours = regular_hours_limit
                self.overtime_hours = self.total_worked - regular_hours_limit
            else:
                self.regular_hours = self.total_worked
                self.overtime_hours = timezone.timedelta()
        
        # Check if this is the first record of the day
        if not self.pk:  # Only for new records
            existing_records = AttendanceRecord.objects.filter(
                user=self.user, 
                date=self.date
            ).exists()
            
            # Mark as primary if it's the first record of the day
            self.is_primary_record = not existing_records
        
        super().save(*args, **kwargs)
    
    @property
    def break_time(self):
        return sum(
            (b.duration for b in self.breaks.all() if b.duration), 
            timezone.timedelta()
        )
    
    @classmethod
    def get_daily_summary(cls, user, date):
        """Get aggregated data for a user on a specific date"""
        records = cls.objects.filter(user=user, date=date)
        
        if not records.exists():
            return None
        
        aggregates = records.aggregate(
            first_clock_in=Min('clock_in'),
            last_clock_out=Max('clock_out'),
            total_worked=Sum('total_worked'),
            total_regular=Sum('regular_hours'),
            total_overtime=Sum('overtime_hours')
        )
        
        return {
            'date': date,
            'user': user,
            'first_clock_in': aggregates['first_clock_in'],
            'last_clock_out': aggregates['last_clock_out'],
            'total_worked': aggregates['total_worked'] or timezone.timedelta(),
            'total_regular': aggregates['total_regular'] or timezone.timedelta(),
            'total_overtime': aggregates['total_overtime'] or timezone.timedelta(),
            'records': records,
            'is_present': records.filter(status='present').exists(),
        }
    
    def __str__(self):
        return f"{self.user} - {self.date} ({self.status}) {self.clock_in.time()} to {self.clock_out.time() if self.clock_out else ''}"

class Break(models.Model):
    BREAK_TYPE_CHOICES = [
        ('lunch', 'Lunch Break'),
        ('short', 'Short Break'),
    ]
    
    attendance_record = models.ForeignKey(AttendanceRecord, on_delete=models.CASCADE, related_name='breaks')
    break_type = models.CharField(max_length=20, choices=BREAK_TYPE_CHOICES, default='lunch')
    break_start = models.DateTimeField()
    break_end = models.DateTimeField(null=True, blank=True)
    is_paid = models.BooleanField(default=True)
    reason = models.CharField(max_length=255, null=True, blank=True)
    duration = models.DurationField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['break_start']
    
    def clean(self):
        if self.break_end and self.break_start and self.break_end < self.break_start:
            raise ValidationError("Break end time cannot be before break start time.")
        
        if self.attendance_record.clock_in and self.break_start < self.attendance_record.clock_in:
            raise ValidationError("Break cannot start before clock in time.")
            
        if self.attendance_record.clock_out and self.break_end and self.break_end > self.attendance_record.clock_out:
            raise ValidationError("Break cannot end after clock out time.")
    
    def save(self, *args, **kwargs):
        if self.break_end:
            self.duration = self.break_end - self.break_start
        super().save(*args, **kwargs)
        
        # Update the parent attendance record
        if self.attendance_record:
            self.attendance_record.save()
    
    def __str__(self):
        return f"{self.get_break_type_display()} for {self.attendance_record.user} ({self.duration})"

class ActivityFeed(models.Model):
    ACTIVITY_TYPES = [
        ('clock_in', 'Clock In'),
        ('clock_out', 'Clock Out'),
        ('break_start', 'Break Start'),
        ('break_end', 'Break End'),
        ('status_change', 'Status Change'),
        ('correction', 'Time Correction'),
        ('verification', 'Verification'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    activity_type = models.CharField(max_length=50, choices=ACTIVITY_TYPES)
    timestamp = models.DateTimeField(auto_now_add=True)
    related_record = models.ForeignKey(AttendanceRecord, on_delete=models.SET_NULL, null=True, blank=True)
    details = models.JSONField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['activity_type']),
        ]
    
    def __str__(self):
        return f"{self.user} {self.get_activity_type_display()} at {self.timestamp}"

class AttendanceSummary(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='attendance_summaries')
    month = models.PositiveSmallIntegerField()
    year = models.PositiveSmallIntegerField()
    
    total_days = models.PositiveSmallIntegerField()
    present_days = models.PositiveSmallIntegerField()
    absent_days = models.PositiveSmallIntegerField()
    late_days = models.PositiveSmallIntegerField()
    half_days = models.PositiveSmallIntegerField()
    leave_days = models.PositiveSmallIntegerField()
    
    total_worked = models.DurationField()
    regular_hours = models.DurationField()
    overtime_hours = models.DurationField()
    total_breaks = models.DurationField()
    
    class Meta:
        unique_together = ('user', 'month', 'year')
        verbose_name_plural = 'Attendance Summaries'
    
    def __str__(self):
        return f"{self.user} - {self.month}/{self.year} Summary"