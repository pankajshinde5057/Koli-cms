from django import forms
from django.forms.widgets import DateInput
from datetime import date
from .models import *


class FormSettings(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(FormSettings, self).__init__(*args, **kwargs)
        for field in self.visible_fields():
            field.field.widget.attrs['class'] = 'form-control'


class CustomUserForm(FormSettings):
    email = forms.EmailField(required=True)
    gender = forms.ChoiceField(choices=[('M', 'Male'), ('F', 'Female')])
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    address = forms.CharField(widget=forms.Textarea)
    password = forms.CharField(widget=forms.PasswordInput)
    widget = {
        'password': forms.PasswordInput(),
    }
    profile_pic = forms.ImageField()

    def __init__(self, *args, **kwargs):
        super(CustomUserForm, self).__init__(*args, **kwargs)

        if kwargs.get('instance'):
            instance = kwargs.get('instance').admin.__dict__
            self.fields['password'].required = False
            for field in CustomUserForm.Meta.fields:
                self.fields[field].initial = instance.get(field)
            if self.instance.pk is not None:
                self.fields['password'].widget.attrs['placeholder'] = "Fill this only if you wish to update password"

    def clean_email(self, *args, **kwargs):
        formEmail = self.cleaned_data['email'].lower()
        if self.instance.pk is None:  
            if CustomUser.objects.filter(email=formEmail).exists():
                raise forms.ValidationError(
                    "The given email is already registered")
        else: 
            dbEmail = self.Meta.model.objects.get(
                id=self.instance.pk).admin.email.lower()
            if dbEmail != formEmail:  
                if CustomUser.objects.filter(email=formEmail).exists():
                    raise forms.ValidationError("The given email is already registered")

        return formEmail

    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'gender',  'password','profile_pic', 'address' ]

# class EmployeeForm(CustomUserForm):
#     def __init__(self, *args, **kwargs):
#         super(EmployeeForm, self).__init__(*args, **kwargs)

#     def save(self, commit=True):
#         employee = super().save(commit=False)
#         admin = employee.admin
#         admin.first_name = self.cleaned_data['first_name']
#         admin.last_name = self.cleaned_data['last_name']
#         admin.email = self.cleaned_data['email']
#         admin.gender = self.cleaned_data['gender']
#         admin.address = self.cleaned_data['address']
#         if self.cleaned_data.get('profile_pic'):
#             admin.profile_pic = self.cleaned_data['profile_pic']
#         password = self.cleaned_data.get('password')
#         if password:
#             admin.set_password(password)

#         if commit:
#             admin.save()
#             employee.admin = admin
#             employee.save()

#         return employee

#     class Meta(CustomUserForm.Meta):
#         model = Employee
#         fields = CustomUserForm.Meta.fields + [
#             'division', 'department', 'designation', 'team_lead', 'phone_number', 'emergency_contact'
#         ]
class EmployeeForm(CustomUserForm):
    def __init__(self, *args, **kwargs):
        super(EmployeeForm, self).__init__(*args, **kwargs)

    class Meta(CustomUserForm.Meta):
        model = Employee
        fields = CustomUserForm.Meta.fields + \
            ['division', 'department','designation', 'team_lead', 'phone_number']


class AdminForm(CustomUserForm):
    def __init__(self, *args, **kwargs):
        super(AdminForm, self).__init__(*args, **kwargs)

    class Meta(CustomUserForm.Meta):
        model = Admin
        fields = CustomUserForm.Meta.fields


class ManagerForm(CustomUserForm):
    def __init__(self, *args, **kwargs):
        super(ManagerForm, self).__init__(*args, **kwargs)

    class Meta(CustomUserForm.Meta):
        model = Manager
        fields = CustomUserForm.Meta.fields + \
            ['division' ]

# class ManagerForm(CustomUserForm):
#     def __init__(self, *args, **kwargs):
#         super(ManagerForm, self).__init__(*args, **kwargs)

#         self.fields['first_name'].required = True
#         self.fields['last_name'].required = True
#         self.fields['email'].required = True
#         self.fields['password'].required = True
#         self.fields['division'].required = True
#         self.fields['address'].required = True

#         self.fields['first_name'].error_messages.update({
#             'required': 'First name is required.'
#         })
#         self.fields['last_name'].error_messages.update({
#             'required': 'Last name is required.'
#         })
#         self.fields['email'].error_messages.update({
#             'required': 'Email address is required.',
#             'invalid': 'Enter a valid email address.'
#         })
#         self.fields['password'].error_messages.update({
#             'required': 'Password is required.'
#         })
#         self.fields['division'].error_messages.update({
#             'required': 'Division selection is required.'
#         })
#         self.fields['address'].error_messages.update({
#             'required': 'Address is required.'
#         })

#     class Meta(CustomUserForm.Meta):
#         model = Manager
#         fields = CustomUserForm.Meta.fields + ['division']




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
        fields = ['date', 'message']
        widgets = {
            'date': DateInput(attrs={'type': 'date'}),
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

    class Meta(CustomUserForm.Meta):
        model = Manager
        fields = CustomUserForm.Meta.fields


class EditSalaryForm(FormSettings):
    def __init__(self, *args, **kwargs):
        super(EditSalaryForm, self).__init__(*args, **kwargs)

    class Meta:
        model = EmployeeSalary
        fields = ['department', 'employee', 'base', 'ctc']
