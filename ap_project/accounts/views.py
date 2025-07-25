from django.shortcuts import render, redirect # هدایت به صفحه و پشتیبانی قالب html
from django.contrib.auth import login, logout # ورود و خروج
from .forms import SignUpForm, SignInForm # استقاده ت از فرم های ساخته شده 

def signup_view(request):
    if request.method == 'POST': # در صورت استفاده از دکمه ثبت 
        form = SignUpForm(request.POST)
        if form.is_valid(): # فرم کامل پرشده
            user = form.save()
            login(request, user)  # ورود خودکار بعد از ثبت‌نام
            return redirect('home')  # ارجاع به صفحه اصلی سایت
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

def signout_view(request):
    logout(request)
    return redirect('home')

