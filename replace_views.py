import re

file_path = r'd:\work\erp_new\myproject_backup\fees\views.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

pattern = re.compile(r"@role_required\(\['admin', 'accountant'\]\)\ndef fee_item_create\(request\):.*?return render\(request, 'fees/setup_form\.html', context\)", re.DOTALL)

replacement = """@role_required(['admin', 'accountant'])
def fee_item_create(request):
    from students.models import AcademicYear, Grade, Division, Enrollment
    from .models import FeeStructure, StudentFee
    from datetime import date
    
    active_year = AcademicYear.objects.filter(is_active=True).first()
    
    grades = Grade.objects.all().order_by('order', 'name')
    divisions = Division.objects.all().order_by('name')
    
    classrooms = []
    for g in grades:
        if g.section:
            grade_divisions = divisions.filter(section=g.section)
            if grade_divisions.exists():
                for d in grade_divisions:
                    classrooms.append({'grade': g, 'division': d})
            else:
                classrooms.append({'grade': g, 'division': None})
        else:
            classrooms.append({'grade': g, 'division': None})

    if request.method == 'POST':
        form = FeeItemForm(request.POST)
        if form.is_valid():
            fee_item = form.save()
            
            if active_year:
                for classroom in classrooms:
                    g_id = classroom['grade'].id
                    d_id = classroom['division'].id if classroom['division'] else 'none'
                    input_key = f"fee_{g_id}_{d_id}"
                    amount = request.POST.get(input_key)
                    
                    if amount is not None and amount.strip() != '':
                        try:
                            amount = float(amount)
                            FeeStructure.objects.update_or_create(
                                academic_year=active_year,
                                grade=classroom['grade'],
                                division=classroom['division'],
                                fee_item=fee_item,
                                defaults={'amount': amount}
                            )
                            
                            if not fee_item.installment_templates.exists() and not fee_item.is_monthly:
                                if classroom['division']:
                                    enrollments = Enrollment.objects.filter(academic_year=active_year, grade=classroom['grade'], division=classroom['division'])
                                else:
                                    enrollments = Enrollment.objects.filter(academic_year=active_year, grade=classroom['grade'], division__isnull=True)
                                
                                for enrollment in enrollments:
                                    fee, created = StudentFee.objects.get_or_create(
                                        student=enrollment.student,
                                        fee_item=fee_item,
                                        defaults={'total_amount': amount, 'due_date': date.today(), 'remarks': 'Automatically allocated from fee setup'}
                                    )
                                    if not created and fee.total_amount != amount and fee.amount_paid == 0:
                                        fee.total_amount = amount
                                        fee.update_status()
                                        fee.save()
                        except (ValueError, TypeError):
                            pass

            messages.success(request, 'Fee Item and structures created successfully.')
            return redirect('fees:fee_setup_dashboard')
    else:
        initial = {}
        category_id = request.GET.get('category')
        if category_id:
            initial['category'] = category_id
        form = FeeItemForm(initial=initial)
        
    from collections import defaultdict
    sections = defaultdict(list)
    for c in classrooms:
        section_name = c['grade'].section.name if c['grade'].section else "General"
        c['current_amount'] = ''
        sections[section_name].append(c)

    context = {
        'form': form, 
        'page_title': 'Add Fee Item',
        'sections': dict(sections),
        'active_year': active_year
    }
    return render(request, 'fees/fee_item_form.html', context)

@role_required(['admin', 'accountant'])
def fee_item_update(request, pk):
    item = get_object_or_404(FeeItem, pk=pk)
    from students.models import AcademicYear, Grade, Division, Enrollment
    from .models import FeeStructure, StudentFee
    from datetime import date
    
    active_year = AcademicYear.objects.filter(is_active=True).first()
    
    grades = Grade.objects.all().order_by('order', 'name')
    divisions = Division.objects.all().order_by('name')
    
    classrooms = []
    for g in grades:
        if g.section:
            grade_divisions = divisions.filter(section=g.section)
            if grade_divisions.exists():
                for d in grade_divisions:
                    classrooms.append({'grade': g, 'division': d})
            else:
                classrooms.append({'grade': g, 'division': None})
        else:
            classrooms.append({'grade': g, 'division': None})

    if request.method == 'POST':
        form = FeeItemForm(request.POST, instance=item)
        if form.is_valid():
            fee_item = form.save()
            
            if active_year:
                for classroom in classrooms:
                    g_id = classroom['grade'].id
                    d_id = classroom['division'].id if classroom['division'] else 'none'
                    input_key = f"fee_{g_id}_{d_id}"
                    amount = request.POST.get(input_key)
                    
                    if amount is not None and amount.strip() != '':
                        try:
                            amount = float(amount)
                            FeeStructure.objects.update_or_create(
                                academic_year=active_year,
                                grade=classroom['grade'],
                                division=classroom['division'],
                                fee_item=fee_item,
                                defaults={'amount': amount}
                            )
                            
                            if not fee_item.installment_templates.exists() and not fee_item.is_monthly:
                                if classroom['division']:
                                    enrollments = Enrollment.objects.filter(academic_year=active_year, grade=classroom['grade'], division=classroom['division'])
                                else:
                                    enrollments = Enrollment.objects.filter(academic_year=active_year, grade=classroom['grade'], division__isnull=True)
                                
                                for enrollment in enrollments:
                                    fee, created = StudentFee.objects.get_or_create(
                                        student=enrollment.student,
                                        fee_item=fee_item,
                                        defaults={'total_amount': amount, 'due_date': date.today(), 'remarks': 'Automatically allocated from fee setup update'}
                                    )
                                    if not created and fee.total_amount != amount and fee.amount_paid == 0:
                                        fee.total_amount = amount
                                        fee.update_status()
                                        fee.save()
                        except (ValueError, TypeError):
                            pass

            messages.success(request, 'Fee Item and structures updated successfully.')
            return redirect('fees:fee_setup_dashboard')
    else:
        form = FeeItemForm(instance=item)
        
    existing_structures = FeeStructure.objects.filter(academic_year=active_year, fee_item=item) if active_year else []
    fee_map = {(fs.grade_id, fs.division_id): fs.amount for fs in existing_structures}

    from collections import defaultdict
    sections = defaultdict(list)
    for c in classrooms:
        section_name = c['grade'].section.name if c['grade'].section else "General"
        c['current_amount'] = fee_map.get((c['grade'].id, c['division'].id if c['division'] else None), '')
        sections[section_name].append(c)
        
    context = {
        'form': form, 
        'page_title': 'Edit Fee Item', 
        'is_edit': True,
        'sections': dict(sections),
        'active_year': active_year
    }
    return render(request, 'fees/fee_item_form.html', context)"""

new_content = pattern.sub(replacement, content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Replacement successful!")
