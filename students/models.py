from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError

class Section(models.Model):
    """Section/Level of the institution, e.g., KG, LP, UP, HS, HSS, Degree, Diploma"""
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0, help_text="Order for display sorting")

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

class Grade(models.Model):
    """Grade/Class, e.g., 11, 12, 1st Year, KG"""
    name = models.CharField(max_length=50, unique=True)
    section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True, related_name='grades')
    order = models.PositiveIntegerField(default=0, help_text="Order for display sorting")

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

class AcademicYear(models.Model):
    """Academic session year, e.g., '2024-2025'"""
    name = models.CharField(max_length=50, help_text="e.g., '2024-2025'")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True, related_name='academic_years')
    is_active = models.BooleanField(default=False, help_text="Is this the active academic year for its section?")

    class Meta:
        ordering = ['-name']
        unique_together = [['name', 'section']]

    def __str__(self):
        if self.section:
            return f"{self.name} ({self.section.name})"
        return self.name

    def save(self, *args, **kwargs):
        if self.is_active:
            # ensure no other academic year in the SAME section is active
            # (If section is None, ensure no other section=None is active)
            qs = AcademicYear.objects.filter(is_active=True, section=self.section).exclude(pk=self.pk)
            qs.update(is_active=False)
        super().save(*args, **kwargs)

class Division(models.Model):
    """Division like Commerce, Science, Arts, etc."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True, related_name='divisions')

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Room(models.Model):
    """Room/Classroom"""
    room_number = models.CharField(max_length=50, unique=True)
    capacity = models.PositiveIntegerField(default=40)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['room_number']

    def __str__(self):
        return f"Room {self.room_number}"


class Student(models.Model):
    """Student model with all categorization fields"""
    STUDENT_TYPE_CHOICES = [
        ('hostel', 'Hostel'),
        ('day_scholar', 'Day Scholar'),
    ]

    student_id = models.CharField(max_length=50, unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    student_type = models.CharField(max_length=20, choices=STUDENT_TYPE_CHOICES, default='day_scholar')
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    siblings = models.ManyToManyField('self', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f"{self.student_id} - {self.first_name} {self.last_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def current_enrollment(self):
        """Returns the enrollment for the currently active academic year."""
        return self.enrollments.filter(academic_year__is_active=True).first()

    @property
    def grade(self):
        """Returns the grade from the current active enrollment."""
        enrollment = self.current_enrollment
        return enrollment.grade if enrollment else ""

    @property
    def division(self):
        """Returns the division from the current active enrollment."""
        enrollment = self.current_enrollment
        return enrollment.division if enrollment else None


class Enrollment(models.Model):
    """Enrollment mapping a student to an AcademicYear, grade, division, and room"""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='enrollments')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='enrollments')
    section = models.ForeignKey('Section', on_delete=models.SET_NULL, null=True, blank=True)
    grade = models.ForeignKey(Grade, on_delete=models.SET_NULL, null=True, blank=True, related_name='enrollments')
    division = models.ForeignKey(Division, on_delete=models.SET_NULL, null=True, blank=True)
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-academic_year__name', 'grade', 'division', 'student__last_name']
        unique_together = [['student', 'academic_year']]
        
    def __str__(self):
        return f"{self.student.full_name} - {self.academic_year.name} ({self.grade})"

    @property
    def class_name(self):
        if self.grade and self.division:
            return f"{self.grade.name} - {self.division.name}"
        elif self.grade:
            return f"{self.grade.name} - No Division"
        return "Unassigned"


class Period(models.Model):
    """Period/Subject for period-wise attendance"""
    name = models.CharField(max_length=100)
    start_time = models.TimeField()
    end_time = models.TimeField()
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['start_time']

    def __str__(self):
        return f"{self.name} ({self.start_time} - {self.end_time})"


class Activity(models.Model):
    """Other activities for activity-based attendance"""
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)

    class Meta:
        ordering = ['-date', 'name']
        verbose_name_plural = 'Activities'

    def __str__(self):
        return f"{self.name} - {self.date}"


class Attendance(models.Model):
    """Attendance model supporting multiple attendance types per day"""
    ATTENDANCE_TYPE_CHOICES = [
        ('daily', 'Daily Attendance'),
        ('period', 'Period Attendance'),
        ('activity', 'Activity Attendance'),
    ]

    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('excused', 'Excused'),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendances')
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField(default=timezone.now)
    attendance_type = models.CharField(max_length=20, choices=ATTENDANCE_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='present')

    # For period attendance
    period = models.ForeignKey(Period, on_delete=models.SET_NULL, null=True, blank=True)

    # For activity attendance
    activity = models.ForeignKey(Activity, on_delete=models.SET_NULL, null=True, blank=True)

    # Additional fields
    remarks = models.TextField(blank=True)
    marked_by = models.CharField(max_length=100, blank=True)  # Name of person who marked attendance
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', 'enrollment', 'student']
        # Note: Unique constraints are handled in the view logic
        # Multiple attendance types can exist for same student on same day
        indexes = [
            models.Index(fields=['student', 'date']),
            models.Index(fields=['enrollment', 'date']),
            models.Index(fields=['date', 'attendance_type']),
            models.Index(fields=['student', 'date', 'attendance_type']),
            models.Index(fields=['enrollment', 'date', 'attendance_type']),
        ]

    def __str__(self):
        type_display = self.get_attendance_type_display()
        if self.period:
            return f"{self.student} - {type_display} - {self.period} - {self.date}"
        elif self.activity:
            return f"{self.student} - {type_display} - {self.activity} - {self.date}"
        return f"{self.student} - {type_display} - {self.date}"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.attendance_type == 'period' and not self.period:
            raise ValidationError({'period': 'Period is required for period attendance.'})
        if self.attendance_type == 'activity' and not self.activity:
            raise ValidationError({'activity': 'Activity is required for activity attendance.'})
        if self.attendance_type == 'daily' and (self.period or self.activity):
            raise ValidationError('Daily attendance should not have period or activity.')


class HostelMovement(models.Model):
    """Hostel student movement record (departure and arrival)"""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='hostel_movements',
                                limit_choices_to={'student_type': 'hostel'})

    # Departure Part
    departure_date = models.DateField()
    departure_time = models.TimeField()
    escorting_person = models.CharField(max_length=200)
    reason = models.TextField()

    # Arrival Part
    expected_return_date = models.DateField(null=True, blank=True)
    arrival_date = models.DateField(null=True, blank=True)
    arrival_time = models.TimeField(null=True, blank=True)
    sign = models.CharField(max_length=200, blank=True)  # Student signature or name

    # Status
    is_returned = models.BooleanField(default=False)

    # Additional fields
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-departure_date', '-departure_time']
        indexes = [
            models.Index(fields=['student', 'departure_date']),
            models.Index(fields=['is_returned']),
        ]

    def __str__(self):
        status = "Returned" if self.is_returned else "Not Returned"
        return f"{self.student} - {self.departure_date} ({status})"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.is_returned:
            if not self.arrival_date:
                raise ValidationError({'arrival_date': 'Arrival date is required when student has returned.'})
            if self.arrival_date < self.departure_date:
                raise ValidationError({'arrival_date': 'Arrival date cannot be before departure date.'})


class ExamType(models.Model):
    """Exam types like Quarterly, Half Yearly, Annual, etc."""
    SUBJECT_TYPE_CHOICES = [
        ('all', 'All Subjects'),
        ('hadiya', 'Hadiya (Islamic)'),
        ('division', 'Division Specific'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    subject_type = models.CharField(max_length=20, choices=SUBJECT_TYPE_CHOICES, default='all', help_text="Filter subjects shown during mark entry for this exam")
    section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True, related_name='exam_types')
    order = models.PositiveIntegerField(default=0, help_text="Order for display")

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class Subject(models.Model):
    """Subjects for different grades and divisions"""
    SUBJECT_TYPE_CHOICES = [
        ('hadiya', 'Hadiya (Islamic)'),
        ('division', 'Division Specific'),
    ]

    name = models.CharField(max_length=200)
    subject_type = models.CharField(max_length=20, choices=SUBJECT_TYPE_CHOICES)
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE, related_name='subjects', null=True)
    division = models.ForeignKey(Division, on_delete=models.CASCADE, null=True, blank=True,
                                 help_text="Required for division-specific subjects, leave blank for Hadiya")
    section = models.ForeignKey(Section, on_delete=models.SET_NULL, null=True, blank=True, related_name='subjects')
    code = models.CharField(max_length=20, blank=True, help_text="Subject code")
    max_marks = models.PositiveIntegerField(default=100, help_text="Maximum marks for this subject")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['grade', 'subject_type', 'name']
        unique_together = [['name', 'grade', 'division', 'subject_type']]

    def __str__(self):
        if self.division:
            return f"{self.name} - {self.grade} ({self.division.name})"
        return f"{self.name} - {self.grade} ({self.get_subject_type_display()})"


class MarkEntry(models.Model):
    """Mark entry for students in exams"""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='mark_entries')
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='mark_entries')
    exam_type = models.ForeignKey(ExamType, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    marks_obtained = models.DecimalField(max_digits=5, decimal_places=2)
    max_marks = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    exam_date = models.DateField(null=True, blank=True)
    remarks = models.TextField(blank=True)
    entered_by = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-exam_date', 'enrollment', 'student', 'subject']
        unique_together = [['student', 'exam_type', 'subject']]  # Will be updated to enrollment later
        indexes = [
            models.Index(fields=['student', 'exam_type']),
            models.Index(fields=['enrollment', 'exam_type']),
            models.Index(fields=['exam_type', 'subject']),
        ]

    def __str__(self):
        return f"{self.student} - {self.exam_type} - {self.subject} - {self.marks_obtained}/{self.max_marks}"

    @property
    def percentage(self):
        """Calculate percentage"""
        if self.max_marks > 0:
            return (self.marks_obtained / self.max_marks) * 100
        return 0

    @property
    def grade_letter(self):
        """Calculate grade letter"""
        percentage = self.percentage
        if percentage >= 87.5:
            return 'A+'
        elif percentage >= 75:
            return 'A'
        elif percentage >= 62.5:
            return 'B+'
        elif percentage >= 50:
            return 'B'
        elif percentage >= 37.5:
            return 'C+'
        elif percentage >= 30:
            return 'C'
        else:
            return 'F'


class ProgressReport(models.Model):
    """Progress report for a student in a specific exam"""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='progress_reports')
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='progress_reports')
    exam_type = models.ForeignKey(ExamType, on_delete=models.CASCADE)
    academic_year = models.CharField(max_length=20, blank=True)  # Legacy string
    total_marks_obtained = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    total_max_marks = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    overall_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    overall_grade = models.CharField(max_length=5, blank=True)
    rank = models.PositiveIntegerField(null=True, blank=True)
    remarks = models.TextField(blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['-generated_at', 'student']
        unique_together = [['student', 'exam_type', 'academic_year']]

    def __str__(self):
        return f"{self.student} - {self.exam_type} - {self.academic_year}"

    def calculate_totals(self):
        """Calculate total marks and percentage from mark entries"""
        mark_entries = MarkEntry.objects.filter(
            student=self.student,
            exam_type=self.exam_type
        )
        self.total_marks_obtained = sum(entry.marks_obtained for entry in mark_entries)
        self.total_max_marks = sum(entry.max_marks for entry in mark_entries)
        if self.total_max_marks > 0:
            self.overall_percentage = (self.total_marks_obtained / self.total_max_marks) * 100
        else:
            self.overall_percentage = 0

        # Calculate overall grade
        percentage = float(self.overall_percentage)
        if percentage >= 90:
            self.overall_grade = 'A+'
        elif percentage >= 80:
            self.overall_grade = 'A'
        elif percentage >= 70:
            self.overall_grade = 'B+'
        elif percentage >= 60:
            self.overall_grade = 'B'
        elif percentage >= 50:
            self.overall_grade = 'C+'
        elif percentage >= 40:
            self.overall_grade = 'C'
        else:
            self.overall_grade = 'F'

# students/models.py  (or attendance app)

class Holiday(models.Model):
    date = models.DateField(unique=True)
    title = models.CharField(max_length=100)
    is_optional = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.date} - {self.title}"


class GlobalSettings(models.Model):
    """Singleton model for system-wide settings"""
    common_interview_date = models.DateTimeField(null=True, blank=True, help_text="Common date and time for all interviews")
    whatsapp_message_template = models.TextField(
        default="We have received your application. Your application number is {app_no}. You can check your application status directly by clicking this link: {status_link}",
        help_text="Available placeholders: {name}, {app_no}, {status_link}"
    )

    def save(self, *args, **kwargs):
        self.pk = 1 # Ensure only one instance exists
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

class Enquiry(models.Model):
    """Model to store prospective student enquiries and interview tokens"""
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Received', 'Application Received'),
        ('Token Generated', 'Token Generated'),
        ('Enrolled', 'Enrolled'),
        ('Rejected', 'Rejected'),
    ]

    name = models.CharField(max_length=100)
    application_number = models.CharField(max_length=50, unique=True, blank=True, null=True, help_text="Auto-generated application number")
    phone = models.CharField(max_length=15)
    course = models.ForeignKey('Division', on_delete=models.SET_NULL, null=True, blank=True)
    district = models.CharField(max_length=100)
    academic_year = models.ForeignKey('AcademicYear', on_delete=models.SET_NULL, null=True, blank=True)
    section = models.ForeignKey('Section', on_delete=models.SET_NULL, null=True, blank=True) # Assuming it can still be None initially but we mandate it in forms
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    token_number = models.IntegerField(null=True, blank=True)
    interview_date = models.DateTimeField(null=True, blank=True, help_text="Scheduled date and time for the interview")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Enquiries'

    def __str__(self):
        return f"{self.application_number or 'Pending'} - {self.name} - {self.phone} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.application_number:
            # Need to create it: Section First Letter + YY + MM + Count
            today = timezone.now().date()
            year_str = today.strftime('%y') # e.g. '26'
            month_str = today.strftime('%m') # e.g. '03'
            
            section_letter = 'X' # Default if no section
            if self.section and self.section.name:
                section_letter = self.section.name.strip()[0].upper()
                
            # Find the count for this month and year and section letter
            # We can count how many enquiries exist for this month/year/section
            prefix = f"{section_letter}{year_str}{month_str}"
            
            # Count enquiries starting with this prefix
            count = Enquiry.objects.filter(application_number__startswith=prefix).count()
            
            # Format count as 2 digits minimally (01, 02, etc.)
            count_str = f"{count + 1:02d}"
            self.application_number = f"{prefix}{count_str}"
            
        super().save(*args, **kwargs)

from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('teacher', 'Teacher'),
        ('accountant', 'Accountant'),
        ('ntstaff', 'Non-Teaching Staff'),
        ('student', 'Student/Parent'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='ntstaff')
    
    # Only populated if role == 'student'
    student_record = models.OneToOneField('Student', on_delete=models.SET_NULL, null=True, blank=True, related_name='user_profile')

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()
