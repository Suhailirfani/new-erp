from django import forms
from .models import AcademicYear, Subject, Section, Grade, Division

class SectionForm(forms.ModelForm):
    class Meta:
        model = Section
        fields = ['name', 'description', 'order']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class AcademicYearForm(forms.ModelForm):
    class Meta:
        model = AcademicYear
        fields = ['name', 'start_date', 'end_date', 'section', 'is_active']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'section': forms.Select(attrs={'class': 'form-control'}),
        }


class GradeForm(forms.ModelForm):
    class Meta:
        model = Grade
        fields = ['name', 'section', 'order']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'section': forms.Select(attrs={'class': 'form-control'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class DivisionForm(forms.ModelForm):
    class Meta:
        model = Division
        fields = ['name', 'description', 'section']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'section': forms.Select(attrs={'class': 'form-control'}),
        }


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name', 'code', 'subject_type', 'section', 'grade', 'division', 'max_marks', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'subject_type': forms.Select(attrs={'class': 'form-control'}),
            'section': forms.Select(attrs={'class': 'form-control'}),
            'grade': forms.Select(attrs={'class': 'form-control'}),
            'division': forms.Select(attrs={'class': 'form-control'}),
            'max_marks': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class EnquiryForm(forms.ModelForm):
    class Meta:
        from .models import Enquiry
        model = Enquiry
        fields = ['name', 'phone', 'course', 'district', 'section']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number'}),
            'course': forms.Select(attrs={'class': 'form-control'}),
            'district': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'District'}),
            'section': forms.Select(attrs={'class': 'form-control', 'required': 'required'}),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['section'].required = True

from django.contrib.auth.models import User
from .models import UserProfile, Student

class UserManageForm(forms.ModelForm):
    role = forms.ChoiceField(choices=UserProfile.ROLE_CHOICES, required=True, widget=forms.Select(attrs={'class': 'form-control'}))
    student_record = forms.ModelChoiceField(queryset=Student.objects.all(), required=False, widget=forms.Select(attrs={'class': 'form-control'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), required=False, help_text="Leave blank to keep existing password (only when editing).")

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

from .models import Alumni

class AlumniTransferForm(forms.ModelForm):
    class Meta:
        model = Alumni
        fields = ['graduation_year', 'current_status']
        widgets = {
            'graduation_year': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 2026'}),
            'current_status': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Higher Studies, Employed'}),
        }

class AlumniForm(forms.ModelForm):
    class Meta:
        model = Alumni
        fields = ['graduation_year', 'current_status', 'company_or_institution', 'remarks']
        widgets = {
            'graduation_year': forms.TextInput(attrs={'class': 'form-control'}),
            'current_status': forms.TextInput(attrs={'class': 'form-control'}),
            'company_or_institution': forms.TextInput(attrs={'class': 'form-control'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

# --- Job Vacancy Forms ---
from .models import JobOpening, JobApplication

class JobOpeningForm(forms.ModelForm):
    class Meta:
        model = JobOpening
        fields = ['title', 'role', 'eligibility', 'description', 'announced_date', 'validity', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Job Title'}),
            'role': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Arabic Teacher'}),
            'announced_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'validity': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'eligibility': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Qualifications...'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Full Job Description...'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class JobApplicationForm(forms.ModelForm):
    class Meta:
        model = JobApplication
        fields = ['full_name', 'email', 'phone', 'qualification', 'experience', 'resume', 'cover_letter']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your Full Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number'}),
            'qualification': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. B.Ed, M.Sc'}),
            'experience': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 3 Years'}),
            'resume': forms.FileInput(attrs={'class': 'form-control'}),
            'cover_letter': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Why are you a good fit?'}),
        }
