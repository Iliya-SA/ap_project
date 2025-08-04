from rest_framework import serializers
from .models import RoutinePlan, RoutineStep
from products.models import Product  # برای نمایش اطلاعات محصول


class RoutineStepSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    
    class Meta:
        model = RoutineStep
        fields = ['step_name', 'product', 'product_name']


class RoutinePlanSerializer(serializers.ModelSerializer):
    steps = RoutineStepSerializer(many=True)  # وصل کردن مراحل روتین (Nested)
    
    class Meta:
        model = RoutinePlan
        fields = ['id', 'user', 'plan_name', 'created_at', 'steps']

    def create(self, validated_data):
        steps_data = validated_data.pop('steps')
        routine = RoutinePlan.objects.create(**validated_data)
        for step in steps_data:
            RoutineStep.objects.create(routine=routine, **step)
        return routine
