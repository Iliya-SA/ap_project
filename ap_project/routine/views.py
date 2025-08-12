from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import RoutinePlan, RoutineStep
from .serializers import RoutinePlanSerializer
from products.models import Product
from accounts.models import Profile

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def quiz_view(request):
    """
    Accepts quiz answers, generates RoutinePlan, and returns it.
    """
    user = request.user
    data = request.data  # answers from quiz

    skin_type = data.get('skin_type')
    concerns = data.get('concerns', [])
    preferences = data.get('preferences', [])

    # Get user profile or create
    profile, _ = Profile.objects.get_or_create(user=user)
    profile.preferences = preferences
    profile.save()

    # Create routine plan
    plan = RoutinePlan.objects.create(user_profile=profile, name="My Skincare Routine")

    # Example product selection logic (very simple)
    products = Product.objects.all()[:3]  # TODO: filter based on answers
    step_names = ["Cleanser", "Moisturizer", "Sunscreen"]

    for i, product in enumerate(products):
        RoutineStep.objects.create(
            plan=plan,
            step_number=i + 1,
            product=product,
            instructions=f"Use {product.name} as your {step_names[i]}"
        )

    serializer = RoutinePlanSerializer(plan)
    return Response(serializer.data)
