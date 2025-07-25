from django.db import models

class Product(models.Model):
    name = models.CharField(max_length = 100)
    brand = models.CharField(max_length = 100)
    category = models.CharField(max_length = 50)
    description = models.TextField()
    skin_types = models.CharField(max_length=100)
    concerns_targeted = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    rating = models.FloatField(default=0)
    image_url = models.URLField(max_length=300)
    created_at = models.DateTimeField()

    def __str__(self):
        return f"{self.name} ({self.brand})"