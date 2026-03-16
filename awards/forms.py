from django import forms
from .models import Candidate, AwazeGCampCandidate

class CandidateForm(forms.ModelForm):
    class Meta:
        model = Candidate
        fields = ['name', 'father_name', 'mobile_number', 'madrasa_and_place', 'student_class', 'board', 'grade', 'address']
        widgets = {
            'board': forms.Select(attrs={'class': 'form-select'}),
            'grade': forms.Select(attrs={'class': 'form-select'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'father_name': forms.TextInput(attrs={'class': 'form-control'}),
            'mobile_number': forms.TextInput(attrs={'class': 'form-control'}),
            'madrasa_and_place': forms.TextInput(attrs={'class': 'form-control'}),
            'student_class': forms.TextInput(attrs={'class': 'form-control'}),
        }

class AwazeGCampForm(forms.ModelForm):
    class Meta:
        model = AwazeGCampCandidate
        fields = ['name', 'father_name', 'address', 'phone', 'student_class', 'age']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'father_name': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'student_class': forms.TextInput(attrs={'class': 'form-control'}),
            'age': forms.NumberInput(attrs={'class': 'form-control'}),
        }
