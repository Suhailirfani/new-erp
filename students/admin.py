from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Student, Division, Room, Period, Activity,
    Attendance, HostelMovement, ExamType, Subject,
    MarkEntry, ProgressReport, AcademicYear, Enrollment
)


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ['name', 'section', 'start_date', 'end_date', 'is_active']
    search_fields = ['name']
    list_filter = ['section', 'is_active']


@admin.register(Division)
class DivisionAdmin(admin.ModelAdmin):
    list_display = ['name', 'section', 'description']
    search_fields = ['name']
    list_filter = ['section', 'name']


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ['room_number', 'capacity', 'description']
    search_fields = ['room_number']
    list_filter = ['capacity']


@admin.register(Period)
class PeriodAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_time', 'end_time', 'description']
    search_fields = ['name']
    list_filter = ['start_time']


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ['name', 'date', 'start_time', 'end_time']
    search_fields = ['name']
    list_filter = ['date']
    date_hierarchy = 'date'


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['student_id', 'full_name', 'student_type', 'is_active']
    list_filter = ['student_type', 'is_active']
    search_fields = ['student_id', 'first_name', 'last_name', 'email']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('student_id', 'first_name', 'last_name', 'email', 'phone', 'address')
        }),
        ('Student Type', {
            'fields': ('student_type',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def full_name(self, obj):
        return obj.full_name
    full_name.short_description = 'Full Name'


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ['student', 'academic_year', 'section', 'grade', 'division', 'room']
    list_filter = ['academic_year', 'section', 'grade', 'division']
    search_fields = ['student__student_id', 'student__first_name', 'student__last_name']
    readonly_fields = ['created_at', 'updated_at']

    def full_name(self, obj):
        return obj.full_name
    full_name.short_description = 'Full Name'


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['student', 'enrollment', 'date', 'attendance_type', 'status', 'period', 'activity', 'marked_by']
    list_filter = ['attendance_type', 'status', 'date', 'period', 'activity']
    search_fields = ['student__student_id', 'student__first_name', 'student__last_name', 'marked_by']
    date_hierarchy = 'date'
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Student Information', {
            'fields': ('student', 'enrollment', 'date')
        }),
        ('Attendance Details', {
            'fields': ('attendance_type', 'status', 'period', 'activity')
        }),
        ('Additional Information', {
            'fields': ('remarks', 'marked_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('student', 'period', 'activity')

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Make period and activity fields optional in the form
        return form


@admin.register(HostelMovement)
class HostelMovementAdmin(admin.ModelAdmin):
    list_display = ['student', 'departure_date', 'departure_time', 'escorting_person',
                    'expected_return_date', 'arrival_date', 'is_returned', 'status_display']
    list_filter = ['is_returned', 'departure_date', 'arrival_date']
    search_fields = ['student__student_id', 'student__first_name', 'student__last_name',
                     'escorting_person', 'reason']
    date_hierarchy = 'departure_date'
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Student Information', {
            'fields': ('student',)
        }),
        ('Departure Information', {
            'fields': ('departure_date', 'departure_time', 'escorting_person', 'reason')
        }),
        ('Arrival Information', {
            'fields': ('expected_return_date', 'arrival_date', 'arrival_time', 'sign', 'is_returned')
        }),
        ('Additional Information', {
            'fields': ('remarks',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def status_display(self, obj):
        if obj.is_returned:
            color = 'green'
            text = 'Returned'
        else:
            color = 'orange'
            text = 'Not Returned'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, text
        )
    status_display.short_description = 'Status'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('student')

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "student":
            kwargs["queryset"] = Student.objects.filter(student_type='hostel', is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(ExamType)
class ExamTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'section', 'order', 'description']
    search_fields = ['name']
    list_filter = ['section', 'order']


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'section', 'subject_type', 'grade', 'division', 'max_marks', 'is_active']
    list_filter = ['section', 'subject_type', 'grade', 'division', 'is_active']
    search_fields = ['name', 'code', 'grade']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'code', 'subject_type', 'section', 'grade', 'division')
        }),
        ('Marks', {
            'fields': ('max_marks',)
        }),
        ('Additional', {
            'fields': ('description', 'is_active')
        }),
    )


@admin.register(MarkEntry)
class MarkEntryAdmin(admin.ModelAdmin):
    list_display = ['student', 'enrollment', 'exam_type', 'subject', 'marks_obtained', 'max_marks', 'percentage', 'grade_letter', 'exam_date']
    list_filter = ['exam_type', 'subject', 'exam_date']
    search_fields = ['student__student_id', 'student__first_name', 'student__last_name', 'subject__name']
    date_hierarchy = 'exam_date'
    readonly_fields = ['created_at', 'updated_at', 'percentage', 'grade_letter']

    fieldsets = (
        ('Student & Exam Information', {
            'fields': ('student', 'enrollment', 'exam_type', 'subject', 'exam_date')
        }),
        ('Marks', {
            'fields': ('marks_obtained', 'max_marks', 'percentage', 'grade_letter')
        }),
        ('Additional', {
            'fields': ('remarks', 'entered_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ProgressReport)
class ProgressReportAdmin(admin.ModelAdmin):
    list_display = ['student', 'enrollment', 'exam_type', 'academic_year', 'overall_percentage', 'overall_grade', 'rank', 'generated_at']
    list_filter = ['exam_type', 'academic_year', 'overall_grade']
    search_fields = ['student__student_id', 'student__first_name', 'student__last_name']
    readonly_fields = ['generated_at', 'overall_percentage', 'overall_grade']
    date_hierarchy = 'generated_at'

# admin.py
from .models import Holiday

@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ('date', 'title')
    ordering = ('date',)
