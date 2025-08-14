from django.db import models
from accounts.models import Profile
from products.models import Product


class RoutinePlan(models.Model):
    PLAN_CHOICES = [
        ('Full Plan', 'Full Plan'),
        ('Hydration Plan', 'Hydration Plan'),
        ('Minimalist Plan', 'Minimalist Plan'),
    ]

    user = models.ForeignKey(Profile, on_delete=models.CASCADE)  # از Profile استفاده می‌کنیم
    plan_name = models.CharField(max_length=20, choices=PLAN_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.user.username} - {self.plan_name}"


class RoutineStep(models.Model):
    routine = models.ForeignKey(RoutinePlan, on_delete=models.CASCADE, related_name='steps')
    step_name = models.CharField(max_length=50)  # مثلاً Cleanser, Toner, ...
    product = models.ForeignKey(Product, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.routine.plan_name} - {self.step_name}"
