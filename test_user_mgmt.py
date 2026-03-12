import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'attendance_system.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from students.models import UserProfile

def run_user_tests():
    print("Setting up test admin...")
    
    # Clean up old test users
    User.objects.filter(username__startswith='test_').delete()
    
    admin_user = User.objects.create_user('test_admin', password='testpassword')
    UserProfile.objects.get(user=admin_user).delete()
    UserProfile.objects.create(user=admin_user, role='admin')
    
    c = Client()
    cc = c.login(username='test_admin', password='testpassword')
    print("Admin logged in:", cc)
    
    print("\n--- Testing User Creation ---")
    response = c.post('/users/create/', {
        'username': 'test_teacher2',
        'password': 'teacherpassword',
        'role': 'teacher',
        'first_name': 'Test',
        'last_name': 'Teacher',
        'email': 'teacher@example.com'
    })
    print("User creation status (should be 302):", response.status_code)
    
    teacher = User.objects.filter(username='test_teacher2').first()
    print("Teacher created:", teacher is not None)
    if teacher:
        print("Teacher role:", teacher.profile.role)
        print("Teacher password checks out:", teacher.check_password('teacherpassword'))

if __name__ == '__main__':
    run_user_tests()
