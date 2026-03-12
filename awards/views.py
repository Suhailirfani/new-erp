from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import CandidateForm, AwazeGCampForm
from .models import Candidate, AwazeGCampCandidate

def candidate_register(request):
    if request.method == 'POST':
        form = CandidateForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('registration_success')
    else:
        form = CandidateForm()
    return render(request, 'awards/candidate_form.html', {'form': form})

def registration_success(request):
    return render(request, 'awards/registration_success.html')

@login_required
def candidate_list(request):
    candidates = Candidate.objects.all().order_by('-created_at')
    return render(request, 'awards/candidate_list.html', {'candidates': candidates})

@login_required
def candidate_print(request):
    candidates = Candidate.objects.all().order_by('name')
    return render(request, 'awards/candidate_print.html', {'candidates': candidates})

# AWAZE G-CAMP Views
def awaze_register(request):
    if request.method == 'POST':
        form = AwazeGCampForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('awaze_success')
    else:
        form = AwazeGCampForm()
    return render(request, 'awards/awaze_candidate_form.html', {'form': form})

def awaze_success(request):
    return render(request, 'awards/awaze_registration_success.html')

@login_required
def awaze_list(request):
    candidates = AwazeGCampCandidate.objects.all().order_by('-created_at')
    return render(request, 'awards/awaze_candidate_list.html', {'candidates': candidates})

@login_required
def awaze_print(request):
    candidates = AwazeGCampCandidate.objects.all().order_by('name')
    return render(request, 'awards/awaze_candidate_print.html', {'candidates': candidates})
