import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'attendance_system.settings')
django.setup()

from fees.models import FeeCategory, FeeItem, AccountCategory, Income, Expense

def tag_data():
    print("Tagging FeeCategories...")
    for cat in FeeCategory.objects.all():
        name_lower = cat.name.lower()
        if 'hostel' in name_lower:
            cat.department = 'hostel'
        elif any(x in name_lower for x in ['admission', 'course', 'grade', 'enrollment', 'bus', 'vehicle']):
            cat.department = 'academic'
        else:
            cat.department = 'academic' # Default to academic for most school fees
        cat.save()
        print(f"  {cat.name} -> {cat.department}")

    print("\nTagging FeeItems...")
    for item in FeeItem.objects.all():
        name_lower = item.name.lower()
        parent_dept = item.category.department
        if 'hostel' in name_lower:
            item.department = 'hostel'
        elif any(x in name_lower for x in ['admission', 'course', 'grade', 'enrollment', 'bus', 'vehicle']):
            item.department = 'academic'
        else:
            item.department = parent_dept
        item.save()
        print(f"  {item.name} -> {item.department}")

    print("\nTagging AccountCategories...")
    for cat in AccountCategory.objects.all():
        name_lower = cat.name.lower()
        if 'hostel' in name_lower:
            cat.department = 'hostel'
        elif any(x in name_lower for x in ['admission', 'course', 'student fees', 'bus', 'vehicle']):
            cat.department = 'academic'
        else:
            cat.department = 'general'
        cat.save()
        print(f"  {cat.name} -> {cat.department}")

    print("\nTagging Income Records...")
    for inc in Income.objects.all():
        inc.department = inc.category.department
        inc.save()
    print(f"  {Income.objects.count()} income records tagged.")

    print("\nTagging Expense Records...")
    for exp in Expense.objects.all():
        exp.department = exp.category.department
        exp.save()
    print(f"  {Expense.objects.count()} expense records tagged.")

if __name__ == '__main__':
    tag_data()
