from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from .forms import SignUpForm, SignInForm, UserEditForm
from .models import Profile
from django.db import transaction


def signup_view(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save(commit=False)
                user.save()
                # پروفایل را هم بساز یا آپدیت کن
                Profile.objects.get_or_create(user=user)
            login(request, user)
            return redirect('home')
    else:
        form = SignUpForm()
    return render(request, 'accounts/signup.html', {'form': form})


def signin_view(request):
    if request.method == 'POST':
        form = SignInForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('home')
    else:
        form = SignInForm()
    return render(request, 'accounts/signin.html', {'form': form})


@login_required
def signout_view(request):
    logout(request)
    return redirect('home')



@login_required
def profile_view(request):
    # تلاش برای دریافت پروفایل یا ایجاد آن در صورت عدم وجود
    profile, created = Profile.objects.get_or_create(user=request.user)
    
    context = {
        'profile': profile,
    }
    return render(request, 'accounts/profile.html', context)


@login_required
def edit_profile_view(request):
    user = request.user
    profile = Profile.objects.get(user=user)
    
    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=user)
        if form.is_valid():
            with transaction.atomic():
                form.save()
                # آپدیت پروفایل
                profile.skin_type = form.cleaned_data.get('skin_type', '')
                profile.device_type = form.cleaned_data.get('device_type', '')
                profile.save()
            return redirect('profile')
    else:
        initial = {
            'skin_type': profile.skin_type,
            'device_type': profile.device_type,
        }
        form = UserEditForm(instance=user, initial=initial)
    
    return render(request, 'accounts/edit_profile.html', {'form': form})
