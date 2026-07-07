from django.urls import path
from . import views

app_name = 'invitaciones'

urlpatterns = [
    path('complete-registration', views.complete_registration, name='complete_registration'),
]
