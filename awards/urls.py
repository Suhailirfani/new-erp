from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.candidate_register, name='candidate_register'),
    path('success/', views.registration_success, name='registration_success'),
    path('list/', views.candidate_list, name='candidate_list'),
    path('edit/<int:pk>/', views.candidate_edit, name='candidate_edit'),
    path('delete/<int:pk>/', views.candidate_delete, name='candidate_delete'),
    path('madrasa-wise/', views.madrasa_wise_list, name='madrasa_wise_list'),
    path('print/', views.candidate_print, name='candidate_print'),
    
    # AWAZE G-CAMP
    path('awaze/register/', views.awaze_register, name='awaze_register'),
    path('awaze/success/', views.awaze_success, name='awaze_success'),
    path('awaze/list/', views.awaze_list, name='awaze_list'),
    path('awaze/print/', views.awaze_print, name='awaze_print'),
    path('awaze/edit/<int:pk>/', views.awaze_edit, name='awaze_edit'),
    path('awaze/delete/<int:pk>/', views.awaze_delete, name='awaze_delete'),
]
