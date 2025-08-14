from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from rest_framework.response import Response
from .models import RoutinePlan, RoutineStep
from .serializers import RoutinePlanSerializer
from accounts.models import Profile
from .utils import select_products_from_quiz  # ✅ add

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def quiz_view(request):
    user = request.user
    data = request.data

    skin_type = data.get('skin_type')
    concerns = data.get('concerns', [])
    preferences = data.get('preferences', [])

    profile, _ = Profile.objects.get_or_create(user=user)
    profile.preferences = preferences
    profile.save()

    # If user retakes the quiz, drop old plan (simple, predictable)
    RoutinePlan.objects.filter(user=profile).delete()

    steps, plan_name = select_products_from_quiz(skin_type, concerns, preferences)

    # Create plan
    plan = RoutinePlan.objects.create(user=profile, plan_name=plan_name)

    # Create steps
    for idx, (step_name, product) in enumerate(steps, start=1):
        RoutineStep.objects.create(
            routine=plan,
            step_name=step_name,
            product=product
        )

    serializer = RoutinePlanSerializer(plan)
    return Response(serializer.data, status=201)

@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def my_routine(request):
    profile = request.user.profile
    plan = RoutinePlan.objects.filter(user=profile).order_by("-created_at").first()
    if not plan:
        return Response({"detail": "No routine found"}, status=404)
    return Response(RoutinePlanSerializer(plan).data)
