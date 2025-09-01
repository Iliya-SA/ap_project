# routine/views.py

from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from rest_framework.response import Response
from .models import RoutinePlan, RoutineStep
from .serializers import RoutinePlanSerializer
from accounts.models import Profile
from .utils import select_products_from_quiz

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def quiz_view(request):
    user = request.user
    data = request.data

    skin_type = data.get('skin_type')
    concerns = data.get('concerns', [])

    profile, _ = Profile.objects.get_or_create(user=user)
    profile.skin_type = skin_type  # ✅ ذخیره skin_type
    profile.concerns = concerns
    profile.save()

    # حذف روتین‌های قبلی
    RoutinePlan.objects.filter(user=profile).delete()

    # لیست پلن‌ها
    plans_config = [
        {"name": "Full Plan", "steps_count": 5},
        {"name": "Hydration Plan", "steps_count": 3},
        {"name": "Minimalist Plan", "steps_count": 3}
    ]

    created_routines = []

    for plan_config in plans_config:
        steps, _ = select_products_from_quiz(
            skin_type=skin_type,
            concerns=concerns,
            plan_type=plan_config["name"]  # می‌تونیم بر اساس نوع پلن رفتار کنیم
        )

        # محدود کردن مراحل بر اساس نوع پلن
        if plan_config["name"] == "Minimalist Plan":
            steps = steps[:3]
        elif plan_config["name"] == "Hydration Plan":
            steps = [s for s in steps if "Moisturizer" in s[0] or "Serum" in s[0]] or steps[:3]
        # Full Plan همه مراحل رو نگه می‌داره

        # ساخت پلن
        plan = RoutinePlan.objects.create(user=profile, plan_name=plan_config["name"])

        # اضافه کردن مراحل
        for step_name, product in steps:
            if product:
                RoutineStep.objects.create(
                    routine=plan,
                    step_name=step_name,
                    product=product
                )
        created_routines.append(plan)

    # سریالایز همه روتین‌ها
    serializer = RoutinePlanSerializer(created_routines, many=True)
    return Response(serializer.data, status=201)


@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def my_routine(request):
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        return Response({"error": "پروفایل یافت نشد."}, status=404)

    plan = RoutinePlan.objects.filter(user=profile).order_by("-created_at").first()
    if not plan:
        return Response({"detail": "روتینی یافت نشد."}, status=404)

    return Response(RoutinePlanSerializer(plan).data)