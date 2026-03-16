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
    grade_filter = request.GET.get('grade')
    candidates = Candidate.objects.all()
    
    if grade_filter:
        candidates = candidates.filter(grade=grade_filter)
        
    candidates = candidates.order_by('-created_at')
    return render(request, 'awards/candidate_list.html', {
        'candidates': candidates,
        'current_grade': grade_filter
    })

@login_required
def madrasa_wise_list(request):
    # Get all candidates
    candidates = Candidate.objects.all()
    
    # Custom sorting for grades: Distinction > Topper > Top Plus
    # We can use Case/When for custom order in database or sort in Python
    from django.db.models import Case, When, Value, IntegerField
    
    candidates = candidates.annotate(
        grade_order=Case(
            When(grade='DISTINCTION', then=Value(1)),
            When(grade='TOPPER', then=Value(2)),
            When(grade='TOP_PLUS', then=Value(3)),
            default=Value(4),
            output_field=IntegerField(),
        )
    ).order_by('madrasa_and_place', 'grade_order', 'name')
    
    # Group by madrasa
    grouped_candidates = {}
    for c in candidates:
        madrasa = c.madrasa_and_place
        if madrasa not in grouped_candidates:
            grouped_candidates[madrasa] = []
        grouped_candidates[madrasa].append(c)
        
    return render(request, 'awards/madrasa_wise_list.html', {
        'grouped_candidates': grouped_candidates
    })

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
