from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='alumni_home'),
    path('registration/', views.registration_view, name='alumni_registration'),
    path('list/', views.alumni_list_view, name='alumni_list'),
    path('pdf/', views.render_pdf_view, name='alumni_pdf'),
    path('alumni/delete/<int:pk>/', views.delete_alumni, name='delete_alumni'),

]
