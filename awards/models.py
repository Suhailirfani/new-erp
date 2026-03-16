from django.db import models

class Candidate(models.Model):
    BOARD_CHOICES = [
        ('SK SVB', 'Samastha Kerala Sunni Vidyabhyasa Board'),
        ('SK IMVB', 'Samastha Kerala Islam Matha Vidyabhyasa Board'),
    ]
    
    GRADE_CHOICES = [
        ('TOPPER', 'Topper'),
        ('TOP_PLUS', 'Top Plus'),
        ('DISTINCTION', 'Distinction'),
    ]
    
    name = models.CharField(max_length=255)
    father_name = models.CharField(max_length=255)
    mobile_number = models.CharField(max_length=15)
    madrasa_and_place = models.CharField(max_length=255)
    student_class = models.CharField(max_length=50) # 'class' is a reserved keyword in Python
    board = models.CharField(max_length=10, choices=BOARD_CHOICES)
    grade = models.CharField(max_length=15, choices=GRADE_CHOICES)
    address = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class AwazeGCampCandidate(models.Model):
    name = models.CharField(max_length=255)
    father_name = models.CharField(max_length=255)
    address = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=15)
    student_class = models.CharField(max_length=50)
    age = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
