from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import CandidateForm, AwazeGCampForm
from .models import Candidate, AwazeGCampCandidate, CampMessage

@login_required
def candidate_edit(request, pk):
    candidate = get_object_or_404(Candidate, pk=pk)
    if request.method == 'POST':
        form = CandidateForm(request.POST, instance=candidate)
        if form.is_valid():
            form.save()
            return redirect('candidate_list')
    else:
        form = CandidateForm(instance=candidate)
    return render(request, 'awards/candidate_form.html', {'form': form, 'is_edit': True})

@login_required
def candidate_delete(request, pk):
    candidate = get_object_or_404(Candidate, pk=pk)
    if request.method == 'POST':
        candidate.delete()
        return redirect('candidate_list')
    return render(request, 'awards/candidate_confirm_delete.html', {'candidate': candidate})

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
    all_candidates = Candidate.objects.all().order_by('created_at')
    
    # Calculate counts
    total_count = all_candidates.count()
    distinction_count = all_candidates.filter(grade='DISTINCTION').count()
    topper_count = all_candidates.filter(grade='TOPPER').count()
    top_plus_count = all_candidates.filter(grade='TOP_PLUS').count()
    
    # Filter if needed
    candidates = all_candidates
    if grade_filter:
        candidates = candidates.filter(grade=grade_filter)
        
    # Group by grade for separate tables
    # Define the order of grades
    grade_order = ['DISTINCTION', 'TOPPER', 'TOP_PLUS']
    grouped_candidates = []
    
    for g_code in grade_order:
        grade_display = next((display for code, display in Candidate.GRADE_CHOICES if code == g_code), g_code)
        grade_candidates = candidates.filter(grade=g_code)
        if grade_candidates.exists():
            grouped_candidates.append({
                'grade_code': g_code,
                'grade_display': grade_display,
                'candidates': grade_candidates,
                'count': grade_candidates.count()
            })

    return render(request, 'awards/candidate_list.html', {
        'candidates': candidates,
        'current_grade': grade_filter,
        'total_count': total_count,
        'distinction_count': distinction_count,
        'topper_count': topper_count,
        'top_plus_count': top_plus_count,
        'grouped_candidates': grouped_candidates
    })

import difflib

@login_required
def madrasa_wise_list(request):
    # Get all candidates
    candidates = Candidate.objects.all()
    
    # Custom sorting for grades: Distinction > Topper > Top Plus
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
    
    # Group by madrasa with fuzzy matching
    unique_names = sorted(list(set(candidates.values_list('madrasa_and_place', flat=True))), key=len, reverse=True)
    canonical_map = {}
    processed = set()

    for name in unique_names:
        if name in processed:
            continue
        # Find close matches for this name among all unique names
        # We use a cutoff of 0.7 for reasonable similarity
        matches = difflib.get_close_matches(name, unique_names, n=len(unique_names), cutoff=0.7)
        
        # Pick a canonical representative (the first one among matches that wasn't processed)
        representative = name
        for m in matches:
            if m not in processed:
                canonical_map[m] = representative
                processed.add(m)
    
    # Group by canonical representative
    grouped_candidates = {}
    for c in candidates:
        original_name = c.madrasa_and_place
        canonical = canonical_map.get(original_name, original_name)
        
        if canonical not in grouped_candidates:
            grouped_candidates[canonical] = {
                'candidates': [],
                'aliases': set()
            }
        grouped_candidates[canonical]['candidates'].append(c)
        if original_name != canonical:
            grouped_candidates[canonical]['aliases'].add(original_name)
        
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
    candidates = AwazeGCampCandidate.objects.all().order_by('created_at')
    camp_msg_obj, created = CampMessage.objects.get_or_create(id=1)
    
    if request.method == 'POST' and 'update_message' in request.POST:
        camp_msg_obj.message_text = request.POST.get('message_text', '')
        camp_msg_obj.save()
        messages.success(request, "Camp message updated successfully.")
        return redirect('awaze_list')
        
    return render(request, 'awards/awaze_candidate_list.html', {
        'candidates': candidates,
        'camp_message': camp_msg_obj.message_text
    })

@login_required
def awaze_print(request):
    candidates = AwazeGCampCandidate.objects.all().order_by('name')
    return render(request, 'awards/awaze_candidate_print.html', {'candidates': candidates})

@login_required
def awaze_edit(request, pk):
    candidate = get_object_or_404(AwazeGCampCandidate, pk=pk)
    if request.method == 'POST':
        form = AwazeGCampForm(request.POST, instance=candidate)
        if form.is_valid():
            form.save()
            return redirect('awaze_list')
    else:
        form = AwazeGCampForm(instance=candidate)
    return render(request, 'awards/awaze_candidate_form.html', {'form': form, 'is_edit': True})

@login_required
def awaze_delete(request, pk):
    candidate = get_object_or_404(AwazeGCampCandidate, pk=pk)
    if request.method == 'POST':
        candidate.delete()
        return redirect('awaze_list')
    return render(request, 'awards/awaze_candidate_confirm_delete.html', {'candidate': candidate})
