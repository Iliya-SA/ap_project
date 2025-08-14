from django.contrib import admin
from .models import ContextData

@admin.register(ContextData)
class ContextDataAdmin(admin.ModelAdmin):
    list_display = ['user', 'device_type', 'season', 'timestamp']
    list_filter = ['device_type', 'season', 'timestamp']