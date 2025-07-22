from django import forms
from django.forms.widgets import DateInput
from datetime import date
from .models import *

class FormSettings(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.visible_fields():
            field.field.widget.attrs['class'] = 'form-control'


class CustomUserForm(FormSettings):
    email = forms.EmailField(required=True)
    gender = forms.ChoiceField(choices=[('M', 'Male'), ('F', 'Female')])
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    address = forms.CharField(widget=forms.Textarea)
    password = forms.CharField(widget=forms.PasswordInput, required=False)
    profile_pic = forms.ImageField(required=False, widget=forms.FileInput)
    is_second_shift = forms.ChoiceField(
        required=False,
        label="Is second shift",
        choices=[(False, 'No (means morning shift)'),(True, 'Yes (means afternoon shift)')],
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['password'].widget.attrs['placeholder'] = "Fill this only if you wish to update password"
            user = self.instance.admin
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
            self.fields['email'].initial = user.email
            self.fields['address'].initial = user.address
            self.fields['gender'].initial = user.gender
            self.fields['profile_pic'].initial = user.profile_pic
            self.fields['is_second_shift'].initial = user.is_second_shift

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if self.instance.pk:
            if CustomUser.objects.exclude(id=self.instance.admin.id).filter(email=email).exists():
                raise forms.ValidationError("This email is already registered.")
        else:
            if CustomUser.objects.filter(email=email).exists():
                raise forms.ValidationError("This email is already registered.")
        return email

    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'gender', 'password', 'profile_pic', 'address','is_second_shift']


class AdminForm(CustomUserForm):
    class Meta(CustomUserForm.Meta):
        model = Admin
        fields = CustomUserForm.Meta.fields





class EmployeeForm(CustomUserForm):
    employee_id = forms.CharField(label="Employee ID",max_length=10,required=True,)
    emergency_phone = forms.CharField(label="Emergency Contact Phone", max_length=10, required=False)
    emergency_name = forms.CharField(label="Emergency Contact Name", required=False)
    emergency_relationship = forms.CharField(label="Emergency Contact Relationship", required=False)
    emergency_address = forms.CharField(label="Emergency Contact Address", required=False, widget=forms.Textarea)
    date_of_joining = forms.DateField(
        label="Date of Joining",
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=True
    )
    aadhar_card = forms.CharField(label="Aadhar Card Number", max_length=12, required=True)
    pan_card = forms.CharField(label="PAN Card Number", max_length=10, required=True)
    bond_start = forms.DateField(
        label="Agreement Start Date",
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=True
    )
    bond_end = forms.DateField(
        label="Agreement End Date",
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=True
    )
    team_lead = forms.ModelChoiceField(
        queryset=Manager.objects.all(),
        label="Team Lead ",
        required=True
    )
   
    # remaining_bond = forms.IntegerField(
    #     label="Remaining Bond (Days)",
    #     required=False,
    #     widget=forms.TextInput(attrs={'readonly': 'readonly'})
    # )
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and hasattr(self.instance, 'admin'):
            self.fields['email'].initial = self.instance.admin.email
            self.fields['password'].required = False
        if self.instance and self.instance.emergency_contact:
            ec = self.instance.emergency_contact
            self.fields['emergency_name'].initial = ec.get('name', '')
            self.fields['emergency_relationship'].initial = ec.get('relationship', '')
            self.fields['emergency_phone'].initial = ec.get('phone', '')
            self.fields['emergency_address'].initial = ec.get('address', '')
        if self.instance and self.instance.date_of_joining:
            self.fields['date_of_joining'].initial = self.instance.date_of_joining
        if self.instance:
            self.fields['employee_id'].initial = self.instance.employee_id
            self.fields['aadhar_card'].initial = self.instance.aadhar_card
            self.fields['pan_card'].initial = self.instance.pan_card
            self.fields['bond_start'].initial = self.instance.bond_start
            self.fields['bond_end'].initial = self.instance.bond_end
    
    def clean_employee_id(self):
        employee_id = self.cleaned_data.get('employee_id')
        if employee_id:
            if len(employee_id) < 1 or len(employee_id) > 10:
                raise ValidationError("Employee ID must be between 1 and 10 characters long.")
            existing_employee = Employee.objects.filter(employee_id=employee_id)
            if self.instance and self.instance.pk:
                existing_employee = existing_employee.exclude(pk=self.instance.pk)
            if existing_employee.exists():
                raise ValidationError("Employee ID already exists.")
        return employee_id

    def clean_aadhar_card(self):
        aadhar_card = self.cleaned_data.get('aadhar_card')
        if aadhar_card:
            if not aadhar_card.isdigit():
                raise ValidationError("Aadhar Card number must contain only digits.")
            if len(aadhar_card) != 12:
                raise ValidationError("Aadhar Card number must be exactly 12 digits.")
        return aadhar_card

    def clean_pan_card(self):
        pan_card = self.cleaned_data.get('pan_card')
        if pan_card:
            if not pan_card.isalnum():
                raise ValidationError("PAN Card number must be alphanumeric.")
            if len(pan_card) != 10:
                raise ValidationError("PAN Card number must be exactly 10 characters.")
            if not pan_card[:5].isalpha() or not pan_card[5:9].isdigit() or not pan_card[9].isalpha():
                raise ValidationError("PAN Card number must follow the format: 5 letters, 4 digits, 1 letter.")
        return pan_card

    def clean_bond_end(self):
        bond_start = self.cleaned_data.get('bond_start')
        bond_end = self.cleaned_data.get('bond_end')
        if bond_start and bond_end and bond_end < bond_start:
            raise ValidationError("Bond end date cannot be before bond start date.")
        return bond_end
    # def clean_remaining_bond(self):
    #     bond_start = self.cleaned_data.get('bond_start')
    #     bond_end = self.cleaned_data.get('bond_end')
    #     if bond_start and bond_end:
    #         delta = bond_end - bond_start
    #         return delta.days if delta.days >= 0 else 0
    #     return None
    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number:
            if not phone_number.isdigit():
                raise ValidationError("Phone number must contain only digits.")
            if len(phone_number) != 10:
                raise ValidationError("Phone number must be exactly 10 digits.")
            if phone_number[0] in ['1', '2', '3', '4']:
                raise ValidationError("Phone number cannot start with 1, 2, 3, or 4")
        return phone_number
    def clean_emergency_phone(self):
        emergency_phone = self.cleaned_data.get('emergency_phone')
        phone_number = self.cleaned_data.get('phone_number')
        if emergency_phone:
            if not emergency_phone.isdigit():
                raise ValidationError("Emergency contact phone number must contain only digits.")
            if len(emergency_phone) != 10:
                raise ValidationError("Emergency contact phone number must be exactly 10 digits.")
            if emergency_phone == phone_number:
                raise ValidationError("Emergency contact phone number cannot be the same as the primary phone number.")
            if emergency_phone[0] in ['1', '2', '3', '4']:
                raise ValidationError("Emergency contact phone number cannot start with 1, 2, 3, or 4")
        return emergency_phone
    def clean_date_of_joining(self):
        date_of_joining = self.cleaned_data.get('date_of_joining')
        if not date_of_joining:
            raise ValidationError("Date of Joining is required.")
        return date_of_joining
    def save(self, commit=True):
        instance = super().save(commit=False)
        if hasattr(instance, 'admin'):
            admin = instance.admin
        else:
            admin = CustomUser(
                email=self.cleaned_data.get('email'),
                first_name=self.cleaned_data.get('first_name'),
                last_name=self.cleaned_data.get('last_name'),
                phone_number=self.cleaned_data.get('phone_number'),
                user_type=3,
            )
            if self.cleaned_data.get('password') and self.cleaned_data.get('password').strip():
                admin.set_password(self.cleaned_data.get('password'))
            admin.save()
            instance.admin = admin

        admin.first_name = self.cleaned_data.get('first_name')
        admin.last_name = self.cleaned_data.get('last_name')
        admin.email = self.cleaned_data.get('email')
        admin.phone_number = self.cleaned_data.get('phone_number')
        if self.cleaned_data.get('password') and self.cleaned_data.get('password').strip():
            admin.set_password(self.cleaned_data.get('password'))
        admin.save()

        instance.emergency_contact = {
            'name': self.cleaned_data.get('emergency_name') or '',
            'relationship': self.cleaned_data.get('emergency_relationship') or '',
            'phone': self.cleaned_data.get('emergency_phone') or '',
            'address': self.cleaned_data.get('emergency_address') or '',
        }
        instance.date_of_joining = self.cleaned_data.get('date_of_joining')
        instance.employee_id = self.cleaned_data.get('employee_id')
        instance.aadhar_card = self.cleaned_data.get('aadhar_card') or ''
        instance.pan_card = self.cleaned_data.get('pan_card') or ''
        instance.bond_start = self.cleaned_data.get('bond_start')
        instance.bond_end = self.cleaned_data.get('bond_end')
        if commit:
            try:
                instance.save()
                print(f"Saved Employee: {instance}, date_of_joining: {instance.date_of_joining}")
            except Exception as e:
                print(f"Error saving employee: {e}")
        return instance

    class Meta(CustomUserForm.Meta):
        model = Employee
        fields = CustomUserForm.Meta.fields + [
            'division', 'department', 'designation', 'team_lead', 'phone_number', 'date_of_joining',
            'aadhar_card', 'pan_card', 'bond_start', 'bond_end'
        ]


class ManagerForm(CustomUserForm):
    manager_id = forms.CharField(label="Manager ID",max_length=10,required=True,)
    emergency_phone = forms.CharField(label="Emergency Contact Phone", max_length=10, required=False)
    emergency_name = forms.CharField(label="Emergency Contact Name", required=False)
    emergency_relationship = forms.CharField(label="Emergency Contact Relationship", required=False)
    emergency_address = forms.CharField(label="Emergency Contact Address", required=False, widget=forms.Textarea)
    date_of_joining = forms.DateField(
        label="Date of Joining",
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=True
    )
    aadhar_card = forms.CharField(label="Aadhar Card Number", max_length=12, required=True)
    pan_card = forms.CharField(label="PAN Card Number", max_length=10, required=True)
    bond_start = forms.DateField(
        label="Agreement Start Date",
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=True
    )
    bond_end = forms.DateField(
        label="Agreement End Date",
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=True
    )
    # remaining_bond = forms.IntegerField(
    #     label="Remaining Bond (Days)",
    #     required=False,
    #     widget=forms.TextInput(attrs={'readonly': 'readonly'})
    # )
 
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and hasattr(self.instance, 'admin'):
            self.fields['email'].initial = self.instance.admin.email
            self.fields['password'].required = False
        if self.instance and self.instance.emergency_contact:
            ec = self.instance.emergency_contact
            self.fields['emergency_name'].initial = ec.get('name', '')
            self.fields['emergency_relationship'].initial = ec.get('relationship', '')
            self.fields['emergency_phone'].initial = ec.get('phone', '')
            self.fields['emergency_address'].initial = ec.get('address', '')
        if self.instance and hasattr(self.instance, 'date_of_joining'):
            self.fields['date_of_joining'].initial = self.instance.date_of_joining
        if self.instance:
            self.fields['manager_id'].initial = self.instance.manager_id
            self.fields['aadhar_card'].initial = self.instance.aadhar_card
            self.fields['pan_card'].initial = self.instance.pan_card
            self.fields['bond_start'].initial = self.instance.bond_start
            self.fields['bond_end'].initial = self.instance.bond_end
            # self.fields['remaining_bond'].initial = self.instance.remaining_bond
            
    def clean_manager_id(self):
        manager_id = self.cleaned_data.get('manager_id')
        if manager_id:
            if len(manager_id) < 1 or len(manager_id) > 10:
                raise ValidationError("Manager ID must be between 1 and 10 characters long.")
            existing_Manager = Manager.objects.filter(manager_id=manager_id)
            if self.instance and self.instance.pk:
                existing_Manager = existing_Manager.exclude(pk=self.instance.pk)
            if existing_Manager.exists():
                raise ValidationError("Manager ID already exists.")
        return manager_id
    
    def clean_aadhar_card(self):
        aadhar_card = self.cleaned_data.get('aadhar_card')
        if aadhar_card:
            if not aadhar_card.isdigit():
                raise ValidationError("Aadhar Card number must contain only digits.")
            if len(aadhar_card) != 12:
                raise ValidationError("Aadhar Card number must be exactly 12 digits.")
        return aadhar_card

    def clean_pan_card(self):
        pan_card = self.cleaned_data.get('pan_card')
        if pan_card:
            if not pan_card.isalnum():
                raise ValidationError("PAN Card number must be alphanumeric.")
            if len(pan_card) != 10:
                raise ValidationError("PAN Card number must be exactly 10 characters.")
            if not pan_card[:5].isalpha() or not pan_card[5:9].isdigit() or not pan_card[9].isalpha():
                raise ValidationError("PAN Card number must follow the format: 5 letters, 4 digits, 1 letter.")
        return pan_card
    
    def clean_bond_end(self):
        bond_start = self.cleaned_data.get('bond_start')
        bond_end = self.cleaned_data.get('bond_end')
        if bond_start and bond_end and bond_end < bond_start:
            raise ValidationError("Bond end date cannot be before bond start date.")
        return bond_end

    # def clean_remaining_bond(self):
    #     bond_start = self.cleaned_data.get('bond_start')
    #     bond_end = self.cleaned_data.get('bond_end')
    #     if bond_start and bond_end:
    #         delta = bond_end - bond_start
    #         return delta.days if delta.days >= 0 else 0
    #     return None
 
    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number:
            if not phone_number.isdigit():
                raise ValidationError("Phone number must contain only digits.")
            if len(phone_number) != 10:
                raise ValidationError("Phone number must be exactly 10 digits.")
            if phone_number[0] in ['1', '2', '3', '4']:
                raise ValidationError("Phone number cannot start with 1, 2, 3, or 4")
        return phone_number
 
    def clean_emergency_phone(self):
        emergency_phone = self.cleaned_data.get('emergency_phone')
        phone_number = self.cleaned_data.get('phone_number')
        if emergency_phone:
            if not emergency_phone.isdigit():
                raise ValidationError("Emergency contact phone number must contain only digits.")
            if len(emergency_phone) != 10:
                raise ValidationError("Emergency contact phone number must be exactly 10 digits.")
            if emergency_phone == phone_number:
                raise ValidationError("Emergency contact phone number cannot be the same as the primary phone number.")
            if emergency_phone[0] in ['1', '2', '3', '4']:
                raise ValidationError("Emergency contact phone number cannot start with 1, 2, 3, or 4")
        return emergency_phone
 
    def save(self, commit=True):
        instance = super().save(commit=False)
        if hasattr(instance, 'admin'):
            admin = instance.admin
        else:
            admin = CustomUser(
                email=self.cleaned_data.get('email'),
                first_name=self.cleaned_data.get('first_name'),
                last_name=self.cleaned_data.get('last_name'),
                phone_number=self.cleaned_data.get('phone_number'),
                user_type=2,
            )
            if self.cleaned_data.get('password') and self.cleaned_data.get('password').strip():
                admin.set_password(self.cleaned_data.get('password'))
            admin.save()
            instance.admin = admin

        admin.first_name = self.cleaned_data.get('first_name')
        admin.last_name = self.cleaned_data.get('last_name')
        admin.email = self.cleaned_data.get('email')
        admin.phone_number = self.cleaned_data.get('phone_number')
        if self.cleaned_data.get('password') and self.cleaned_data.get('password').strip():
            admin.set_password(self.cleaned_data.get('password'))
        admin.save()

        instance.emergency_contact = {
            'name': self.cleaned_data.get('emergency_name') or '',
            'relationship': self.cleaned_data.get('emergency_relationship') or '',
            'phone': self.cleaned_data.get('emergency_phone') or '',
            'address': self.cleaned_data.get('emergency_address') or '',
        }
        instance.date_of_joining = self.cleaned_data.get('date_of_joining')
        instance.aadhar_card = self.cleaned_data.get('aadhar_card') or ''
        instance.pan_card = self.cleaned_data.get('pan_card') or ''
        instance.bond_start = self.cleaned_data.get('bond_start')
        instance.bond_end = self.cleaned_data.get('bond_end')
        # instance.remaining_bond = self.cleaned_data.get('remaining_bond')
 
        if commit:
            instance.save()
        return instance

    class Meta(CustomUserForm.Meta):
        model = Manager
        fields = CustomUserForm.Meta.fields + [
            'division', 'department', 'phone_number', 'date_of_joining',
            'aadhar_card', 'pan_card', 'bond_start', 'bond_end'
        ]


class DivisionForm(FormSettings):
    def __init__(self, *args, **kwargs):
        super(DivisionForm, self).__init__(*args, **kwargs)

    class Meta:
        fields = ['name']
        model = Division


class DepartmentForm(FormSettings):

    def __init__(self, *args, **kwargs):
        super(DepartmentForm, self).__init__(*args, **kwargs)

    class Meta:
        model = Department
        fields = ['name', 'division']


class LeaveReportManagerForm(FormSettings):
    def __init__(self, *args, **kwargs):
        super(LeaveReportManagerForm, self).__init__(*args, **kwargs)

    class Meta:
        model = LeaveReportManager
        fields = [ 'message']
        widgets = {
            'date': forms.DateInput(
                attrs={
                    'type': 'date',
                    'class': 'form-control',   # Ensures proper Bootstrap styling
                    'placeholder': 'Select a date',
                }
            ),
            'message': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Enter your message',
                    'rows': 3
                }
            )
        }


class FeedbackManagerForm(FormSettings):

    def __init__(self, *args, **kwargs):
        super(FeedbackManagerForm, self).__init__(*args, **kwargs)

    class Meta:
        model = FeedbackManager
        fields = ['feedback']


class LeaveReportEmployeeForm(FormSettings):
    def __init__(self, *args, **kwargs):
        super(LeaveReportEmployeeForm, self).__init__(*args, **kwargs)
        today = date.today().isoformat()
        self.fields['start_date'].widget.attrs['min'] = today
        self.fields['end_date'].widget.attrs['min'] = today

    class Meta:
        model = LeaveReportEmployee
        fields = [ 'leave_type','start_date', 'end_date', 'message']
        widgets = {
            'start_date': DateInput(attrs={'type': 'date'},),
            'end_date': DateInput(attrs={'type': 'date'}),
        }


class FeedbackEmployeeForm(FormSettings):

    def __init__(self, *args, **kwargs):
        super(FeedbackEmployeeForm, self).__init__(*args, **kwargs)

    class Meta:
        model = FeedbackEmployee
        fields = ['feedback']


class EmployeeEditForm(CustomUserForm):
    def __init__(self, *args, **kwargs):
        super(EmployeeEditForm, self).__init__(*args, **kwargs)

    class Meta(CustomUserForm.Meta):
        model = Employee
        fields = CustomUserForm.Meta.fields 



class ManagerEditForm(CustomUserForm):
    def __init__(self, *args, **kwargs):
        super(ManagerEditForm, self).__init__(*args, **kwargs)
        # Ensure email field is properly initialized from admin user
        if self.instance and self.instance.admin:
            self.fields['email'].initial = self.instance.admin.email
            self.fields['password'].required = False  # Password is optional for updates

    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            # Update the admin user fields
            admin = instance.admin
            admin.first_name = self.cleaned_data.get('first_name')
            admin.last_name = self.cleaned_data.get('last_name')
            admin.email = self.cleaned_data.get('email')
            if self.cleaned_data.get('password') and self.cleaned_data.get('password').strip():
                admin.set_password(self.cleaned_data.get('password'))
            admin.save()
            instance.save()
        return instance

    class Meta(CustomUserForm.Meta):
        model = Manager
        fields = CustomUserForm.Meta.fields


class EditSalaryForm(FormSettings):
    def __init__(self, *args, **kwargs):
        super(EditSalaryForm, self).__init__(*args, **kwargs)

    class Meta:
        model = EmployeeSalary
        fields = ['department', 'employee', 'base', 'ctc']


# class ScheduleForm(forms.ModelForm):
#     class Meta:
#         model = Schedule
#         fields = ['project', 'task_description', 'status', 'employee']
#         widgets = {
#             # 'employee' : forms.TextInput(attrs={'class' : 'form-control'})
#             'project': forms.TextInput(attrs={'class': 'form-control','placeholder': 'Project name (optional)'}),
#             'task_description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control','placeholder': 'Describe your tasks for today...'}),
#             'status': forms.Select(attrs={'class': 'form-control'}),
#         }

# class ScheduleUpdateForm(forms.ModelForm):
#     class Meta:
#         model = ScheduleUpdate
#         fields = ['update_description', 'status']
#         widgets = {
#             'update_description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control','placeholder': 'What progress have you made?'}),
#             'status': forms.Select(attrs={'class': 'form-control'}),
#         }

#     def clean_update_description(self):
#         description = self.cleaned_data['update_description']
#         if not description.strip():
#             raise forms.ValidationError("Update description cannot be empty.")
#         return description