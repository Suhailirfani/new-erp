from django import forms
from .models import AlumniRegistration

class AlumniRegistrationForm(forms.ModelForm):
    class Meta:
        model = AlumniRegistration
        fields = ['name', 'course', 'batch', 'mobile_no']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'Enter your full name',
                'autocomplete': 'name'
            }),
            'course': forms.Select(attrs={
                'autocomplete': 'off'
            }),
            'batch': forms.TextInput(attrs={
                'placeholder': 'e.g., 2020-2022',
                'autocomplete': 'off'
            }),
            'mobile_no': forms.TextInput(attrs={
                'placeholder': 'Enter your mobile number',
                'autocomplete': 'tel'
            }),
        }

