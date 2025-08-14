# routine/serializers.py
from rest_framework import serializers
from .models import RoutinePlan, RoutineStep

class RoutineStepSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_brand = serializers.CharField(source="product.brand", read_only=True)
    product_price = serializers.IntegerField(source="product.price", read_only=True)
    product_image = serializers.ImageField(source="product.image", read_only=True)

    class Meta:
        model = RoutineStep
        fields = ["step_name", "product", "product_name", "product_brand", "product_price", "product_image"]

class RoutinePlanSerializer(serializers.ModelSerializer):
    user = serializers.IntegerField(source="user.id", read_only=True)
    steps = RoutineStepSerializer(many=True, read_only=True)

    class Meta:
        model = RoutinePlan
        fields = ["id", "user", "plan_name", "created_at", "steps"]
