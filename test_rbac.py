import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'attendance_system.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from students.models import UserProfile, Student

def run_tests():
    print("Setting up test users...")
    
    # Clean up old test users
    User.objects.filter(username__startswith='test_').delete()
    
    admin_user = User.objects.create_user('test_admin', password='testpassword')
    UserProfile.objects.get(user=admin_user).delete() # Remove auto-created
    UserProfile.objects.create(user=admin_user, role='admin')
    
    teacher_user = User.objects.create_user('test_teacher', password='testpassword')
    UserProfile.objects.get(user=teacher_user).delete()
    UserProfile.objects.create(user=teacher_user, role='teacher')
    
    student_user = User.objects.create_user('test_student', password='testpassword')
    UserProfile.objects.get(user=student_user).delete()
    # Create a dummy student record
    dummy_student = Student.objects.create(first_name='Dummy', last_name='Student', student_id='DUMMY123')
    UserProfile.objects.create(user=student_user, role='student', student_record=dummy_student)
    
    c = Client()
    
    print("\n--- Testing Admin Role ---")
    c.login(username='test_admin', password='testpassword')
    print("Admin accessing /fees/dashboard/:", c.get('/fees/dashboard/').status_code) # Should be 200
    print("Admin accessing /students/:", c.get('/students/').status_code) # Should be 200
    c.logout()

    print("\n--- Testing Teacher Role ---")
    c.login(username='test_teacher', password='testpassword')
    print("Teacher accessing /students/:", c.get('/students/').status_code) # Should be 200
    print("Teacher accessing /fees/dashboard/:", c.get('/fees/dashboard/').status_code) # Should be 403
    c.logout()

    print("\n--- Testing Student Role ---")
    c.login(username='test_student', password='testpassword')
    print("Student accessing their own profile:", c.get(f'/students/{dummy_student.id}/edit/').status_code) # Should be 200
    print("Student accessing /students/:", c.get('/students/').status_code) # Should be 200
    print("Student accessing /fees/dashboard/:", c.get('/fees/dashboard/').status_code) # Should be 403
    c.logout()
    
    # Cleanup
    dummy_student.delete()

if __name__ == '__main__':
    run_tests()
