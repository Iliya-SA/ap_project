from django.db import models

class SeasonalKeyword(models.Model):
    season = models.CharField(max_length=50)
    keyword = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.season}: {self.keyword}"
