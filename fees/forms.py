from django import forms
from .models import Income, Expense, AccountCategory, StudentFee, FeeCategory, FeeItem, FeeStructure, BusStop

# ... (rest of imports and forms)

class FeeStructureForm(forms.ModelForm):
    class Meta:
        model = FeeStructure
        fields = ['academic_year', 'grade', 'division', 'fee_item', 'amount']
        widgets = {
            'academic_year': forms.Select(attrs={'class': 'form-select'}),
            'grade': forms.Select(attrs={'class': 'form-select'}),
            'division': forms.Select(attrs={'class': 'form-select'}),
            'fee_item': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Limit division choices based on grade if possible, or just leave as is for now
        # Also ensure academic year is active by default if creating
        from students.models import AcademicYear
        active_year = AcademicYear.objects.filter(is_active=True).first()
        if active_year and not self.instance.pk:
            self.initial['academic_year'] = active_year
from students.models import Student

class IncomeForm(forms.ModelForm):
    # Virtual fields for fee collection from Income form
    is_fee_collection = forms.BooleanField(required=False, widget=forms.HiddenInput())
    student = forms.ModelChoiceField(queryset=Student.objects.all(), required=False, empty_label="Select Student")
    # student_fee field removed, allocation happens automatically on backend
    
    # New category virtual field
    new_category_name = forms.CharField(max_length=100, required=False, label="Or Add New Category", widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter new category name'}))

    # Make received_from not strictly required here so clean can handle it based on category
    received_from = forms.CharField(max_length=200, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))

    class Meta:
        model = Income
        fields = ['category', 'amount', 'received_from', 'payment_method', 'reference_number', 'remarks', 'department']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'reference_number': forms.TextInput(attrs={'class': 'form-control'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'department': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = AccountCategory.objects.filter(type='income')
        self.fields['category'].required = False # We make it false because they might enter a new one
        # Add widget classes to virtual fields
        self.fields['student'].widget.attrs.update({'class': 'form-select'})

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        new_category_name = cleaned_data.get('new_category_name')
        
        if not category and not new_category_name:
            self.add_error('category', 'Please select an existing category or enter a new one.')
            self.add_error('new_category_name', 'Please select an existing category or enter a new one.')
            return cleaned_data
            
        if new_category_name:
            # Create the custom category on the fly
            category, created = AccountCategory.objects.get_or_create(
                name=new_category_name,
                type='income'
            )
            cleaned_data['category'] = category

        is_fee = cleaned_data.get('is_fee_collection')
        
        # If this category is selected as "Student Fees", enforce the virtual fields
        if category and 'fee' in category.name.lower():
            student = cleaned_data.get('student')
            if not student:
                 self.add_error('student', 'Please select a student for fee collection.')
            # Set the flag to true for view processing
            cleaned_data['is_fee_collection'] = True
            
            # Auto-fill received from if blank
            if student:
                # If student model has full_name property use it otherwise just str representation
                cleaned_data['received_from'] = getattr(student, 'full_name', str(student))
        else:
            # Not a fee, so received from is required
            if not cleaned_data.get('received_from'):
                self.add_error('received_from', 'This field is required.')
                
        if category and not cleaned_data.get('department'):
            cleaned_data['department'] = category.department
            
        return cleaned_data


class ExpenseForm(forms.ModelForm):
    # New category virtual field
    new_category_name = forms.CharField(max_length=100, required=False, label="Or Add New Category", widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter new category name'}))

    class Meta:
        model = Expense
        fields = ['category', 'amount', 'paid_to', 'payment_method', 'reference_number', 'remarks', 'department']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'paid_to': forms.TextInput(attrs={'class': 'form-control'}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'reference_number': forms.TextInput(attrs={'class': 'form-control'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'department': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = AccountCategory.objects.filter(type='expense')
        self.fields['category'].required = False # Allow it to be blank if they type a new one

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        new_category_name = cleaned_data.get('new_category_name')
        
        if not category and not new_category_name:
            self.add_error('category', 'Please select an existing category or enter a new one.')
            self.add_error('new_category_name', 'Please select an existing category or enter a new one.')
            return cleaned_data
            
        if new_category_name:
            # Create the custom category on the fly
            category, created = AccountCategory.objects.get_or_create(
                name=new_category_name,
                type='expense'
            )
        if category and not cleaned_data.get('department'):
            cleaned_data['department'] = category.department
            
        return cleaned_data

class FeeCategoryForm(forms.ModelForm):
    class Meta:
        model = FeeCategory
        fields = ['name', 'description', 'department']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Admission, Medical, Course'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional description for this category'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
        }

class FeeItemForm(forms.ModelForm):
    class Meta:
        model = FeeItem
        fields = ['category', 'name', 'default_amount', 'is_monthly', 'is_refundable', 'description', 'target_student_type', 'department', 'applicable_grades', 'applicable_divisions']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Uniform Fee, Monthly Tuition'}),
            'default_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'is_refundable': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_monthly': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'target_student_type': forms.Select(attrs={'class': 'form-select'}),
            'applicable_grades': forms.CheckboxSelectMultiple(),
            'applicable_divisions': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Style the checkboxes a bit within a container usually handled in template
        # But we can add some classes if needed for CSS targeting
        self.fields['applicable_grades'].help_text = "Select one or more grades. Leave blank for all grades."
        self.fields['applicable_divisions'].help_text = "Select one or more divisions. Leave blank for all divisions."

class BusStopForm(forms.ModelForm):
    class Meta:
        model = BusStop
        fields = ['stop_name', 'fee_amount']
        widgets = {
            'stop_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Downtown, North Side'}),
            'fee_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }
