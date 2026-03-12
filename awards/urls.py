from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.candidate_register, name='candidate_register'),
    path('success/', views.registration_success, name='registration_success'),
    path('list/', views.candidate_list, name='candidate_list'),
    path('print/', views.candidate_print, name='candidate_print'),
    
    # AWAZE G-CAMP
    path('awaze/register/', views.awaze_register, name='awaze_register'),
    path('awaze/success/', views.awaze_success, name='awaze_success'),
    path('awaze/list/', views.awaze_list, name='awaze_list'),
    path('awaze/print/', views.awaze_print, name='awaze_print'),
]
