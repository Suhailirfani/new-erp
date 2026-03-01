from django.db import models

class AlumniRegistration(models.Model):
    name = models.CharField(max_length=100)
    course = models.ForeignKey('students.Division', on_delete=models.SET_NULL, null=True, blank=True)
    batch = models.CharField(max_length=50)
    mobile_no = models.CharField(max_length=15)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.batch}"
