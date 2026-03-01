from django.contrib import admin

from .models import AlumniRegistration

@admin.register(AlumniRegistration)
class AlumniRegistrationAdmin(admin.ModelAdmin):
    list_display = ('name', 'batch', 'course', 'mobile_no', 'created_at')
    list_filter = ('batch', 'course')
    search_fields = ('name', 'mobile_no')
