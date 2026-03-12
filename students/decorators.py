from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from functools import wraps

def role_required(allowed_roles):
    """
    Decorator for views that checks whether a user has a specific role.
    If the user has a UserProfile.role in `allowed_roles` or is a superuser, access is granted.
    Otherwise, raises PermissionDenied (403).
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.conf import settings
                return redirect(f"{settings.LOGIN_URL}?next={request.path}")
                
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
                
            if hasattr(request.user, 'profile'):
                if request.user.profile.role in allowed_roles:
                    return view_func(request, *args, **kwargs)
            else:
                # If no profile exists, create one with default role if necessary or block
                pass
                
            raise PermissionDenied("You do not have permission to view this page.")
        return _wrapped_view
    return decorator

def student_own_data_required(view_func):
    """
    Decorator for student detail/edit views.
    Grants access if:
    1. The user is an admin/accountant/teacher.
    2. The user is a student, and the PK in the URL matches their UserProfile.student_record.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.conf import settings
            return redirect(f"{settings.LOGIN_URL}?next={request.path}")

        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
            
        if hasattr(request.user, 'profile'):
            role = request.user.profile.role
            if role in ['admin', 'accountant', 'teacher']:
                return view_func(request, *args, **kwargs)
            
            if role == 'student':
                # Assuming the view takes `pk` as an argument representing the student ID
                requested_pk = kwargs.get('pk')
                student_record = request.user.profile.student_record
                
                if student_record and str(student_record.pk) == str(requested_pk):
                    return view_func(request, *args, **kwargs)
        
        raise PermissionDenied("You do not have permission to view this student's data.")
    return _wrapped_view
