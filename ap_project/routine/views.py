from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods

# Minimal API placeholders so importing routine.urls won't fail.
# These can be replaced with full implementations later.

def quiz_view(request):
    if request.method != 'POST':
        return JsonResponse({'detail': 'Use POST for quiz API.'}, status=405)
    # minimal placeholder: echo received data
    data = getattr(request, 'data', None) or request.POST.dict()
    return JsonResponse({'received': data}, status=201)


def my_routine(request):
    return JsonResponse({'detail': 'No routine implemented yet.'}, status=200)


# Web views

def routine_home(request):
    """Render a simple page asking user to choose a plan."""
    return render(request, 'routine/home.html')


@require_http_methods(["POST"])
def routine_start(request):
    """Handle plan selection from the HTML form and show a confirmation."""
    plan = request.POST.get('plan')
    return render(request, 'routine/started.html', {'plan': plan})
