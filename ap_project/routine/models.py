from django.db import models
from django.conf import settings

class RoutinePlan(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    plan_name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.plan_name}"


class RoutineStep(models.Model):
    routine = models.ForeignKey(RoutinePlan, related_name='steps', on_delete=models.CASCADE)
    step_name = models.CharField(max_length=200)
    # allow product to be nullable so tests won't fail if no products present
    product = models.ForeignKey('products.Product', null=True, blank=True, on_delete=models.SET_NULL)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.routine} - {self.step_name}"
