import os
import django
from django.test import Client
from django.urls import reverse

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'attendance_system.settings')
django.setup()

def verify_auth_changes():
    c = Client()
    
    print("--- Verifying Homepage Access (Anonymous) ---")
    response = c.get('/')
    print(f"Homepage status code: {response.status_code}")
    if response.status_code == 200:
        print("PASS: Homepage is accessible without login.")
    else:
        print("FAIL: Homepage returned non-200 status.")

    print("\n--- Verifying Redirect to Custom Login ---")
    # Access a protected page
    response = c.get('/students/')
    print(f"Protected page redirect URL: {response.url}")
    if '/login/' in response.url:
        print("PASS: Redirects to custom /login/ path.")
    elif '/admin/login/' in response.url:
        print("FAIL: Still redirects to /admin/login/.")
    else:
        print(f"FAIL: Unexpected redirect to {response.url}")

    print("\n--- Verifying Custom Login Page Content ---")
    response = c.get('/login/')
    if response.status_code == 200:
        print("PASS: Custom login page is accessible.")
        if b"System Login" in response.content:
            print("PASS: Found custom title 'System Login' in page content.")
        else:
            print("FAIL: Custom title not found.")
    else:
        print(f"FAIL: Login page returned {response.status_code}")

if __name__ == '__main__':
    verify_auth_changes()
