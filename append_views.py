views_code = """
from django.contrib.auth.models import User
from .forms import UserManageForm

@role_required(['admin'])
def user_list(request):
    users = User.objects.select_related('profile').all().order_by('-date_joined')
    return render(request, 'students/user_list.html', {'users': users})

@role_required(['admin'])
def user_create(request):
    if request.method == 'POST':
        form = UserManageForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            password = form.cleaned_data.get('password')
            if password:
                user.set_password(password)
            user.save()
            
            # The signal might create a default profile, so let's update it or create it
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.role = form.cleaned_data.get('role')
            profile.student_record = form.cleaned_data.get('student_record')
            profile.save()
            
            messages.success(request, f'User {user.username} created successfully.')
            return redirect('students:user_list')
    else:
        form = UserManageForm()
    
    return render(request, 'students/user_form.html', {'form': form, 'title': 'Create User'})

@role_required(['admin'])
def user_update(request, pk):
    user = get_object_or_404(User, pk=pk)
    profile = getattr(user, 'profile', None)
    
    if request.method == 'POST':
        form = UserManageForm(request.POST, instance=user)
        if form.is_valid():
            updated_user = form.save(commit=False)
            password = form.cleaned_data.get('password')
            if password:
                updated_user.set_password(password)
            updated_user.save()
            
            if not profile:
                profile = UserProfile.objects.create(user=updated_user)
                
            profile.role = form.cleaned_data.get('role')
            profile.student_record = form.cleaned_data.get('student_record')
            profile.save()
            
            messages.success(request, f'User {updated_user.username} updated successfully.')
            return redirect('students:user_list')
    else:
        initial = {}
        if profile:
            initial['role'] = profile.role
            initial['student_record'] = profile.student_record
        form = UserManageForm(instance=user, initial=initial)
        
    return render(request, 'students/user_form.html', {'form': form, 'title': 'Edit User'})

@role_required(['admin'])
def user_delete(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    if user_obj.is_superuser and request.user.pk != user_obj.pk:
        messages.error(request, "You cannot delete other superusers.")
        return redirect('students:user_list')
        
    if request.method == 'POST':
        user_obj.delete()
        messages.success(request, 'User deleted successfully.')
        return redirect('students:user_list')
    return render(request, 'students/user_confirm_delete.html', {'user_obj': user_obj})
"""
with open('students/views.py', 'a', encoding='utf-8') as f:
    f.write(views_code)
