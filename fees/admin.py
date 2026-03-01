from django.contrib import admin
from .models import FeeCategory, FeeItem, BusStop, CourseInstallment, StudentFee, FeePayment

@admin.register(FeeCategory)
class FeeCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(FeeItem)
class FeeItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'default_amount', 'is_refundable')
    list_filter = ('category', 'is_refundable')
    search_fields = ('name',)

@admin.register(BusStop)
class BusStopAdmin(admin.ModelAdmin):
    list_display = ('stop_name', 'fee_amount')
    search_fields = ('stop_name',)

@admin.register(CourseInstallment)
class CourseInstallmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'due_date')
    search_fields = ('name',)

class FeePaymentInline(admin.TabularInline):
    model = FeePayment
    extra = 0
    readonly_fields = ('receipt_number', 'payment_date')

@admin.register(StudentFee)
class StudentFeeAdmin(admin.ModelAdmin):
    list_display = ('student', 'fee_item', 'installment', 'total_amount', 'amount_paid', 'status', 'due_date')
    list_filter = ('status', 'fee_item', 'installment')
    search_fields = ('student__first_name', 'student__last_name', 'student__student_id')
    readonly_fields = ('status',)
    inlines = [FeePaymentInline]

    def save_model(self, request, obj, form, change):
        obj.update_status()
        super().save_model(request, obj, form, change)

@admin.register(FeePayment)
class FeePaymentAdmin(admin.ModelAdmin):
    list_display = ('receipt_number', 'student_fee_student', 'amount', 'payment_date', 'payment_method', 'collected_by')
    list_filter = ('payment_method', 'payment_date')
    search_fields = ('receipt_number', 'student_fee__student__first_name', 'student_fee__student__last_name', 'reference_number')
    readonly_fields = ('receipt_number', 'payment_date')

    def student_fee_student(self, obj):
        return obj.student_fee.student
    student_fee_student.short_description = 'Student'

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Update StudentFee amount_paid
        fee = obj.student_fee
        transactions = fee.payments.all()
        total_paid = sum(t.amount for t in transactions)
        # Since this is saved after, we inject this payment amount if it's new
        if obj.pk is None or not transactions.filter(pk=obj.pk).exists():
           total_paid += obj.amount
        fee.amount_paid = total_paid
        fee.update_status()

from .models import AccountCategory, Income, Expense

@admin.register(AccountCategory)
class AccountCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'type')
    list_filter = ('type',)
    search_fields = ('name',)

@admin.register(Income)
class IncomeAdmin(admin.ModelAdmin):
    list_display = ('category', 'amount', 'date', 'received_from', 'payment_method', 'collected_by')
    list_filter = ('category', 'payment_method', 'date')
    search_fields = ('received_from', 'reference_number', 'remarks')

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('category', 'amount', 'date', 'paid_to', 'payment_method', 'recorded_by')
    list_filter = ('category', 'payment_method', 'date')
    search_fields = ('paid_to', 'reference_number', 'remarks')
