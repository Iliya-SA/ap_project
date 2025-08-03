from django.db import models
from django.contrib.auth.models import User

class ContextData(models.Model):
    DEVICE_CHOICES = [
        ('mobile', 'Mobile'),
        ('desktop', 'Desktop'),
    ]

    SEASON_CHOICES = [
        ('spring', 'Spring'),
        ('summer', 'Summer'),
        ('autumn', 'Autumn'),
        ('winter', 'Winter'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    device_type = models.CharField(max_length=10, choices=DEVICE_CHOICES)
    season = models.CharField(max_length=10, choices=SEASON_CHOICES)

    def __str__(self):
        return f"{self.user.username} - {self.device_type} - {self.season} - {self.timestamp}"
