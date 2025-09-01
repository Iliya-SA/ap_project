from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model
from .models import Profile

User = get_user_model()

class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)

    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'password1', 'password2',
        ]

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')

        if commit:
            user.save()

        return user


class SignInForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={'placeholder': 'نام کاربری'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'رمز عبور'}))


class UserEditForm(forms.ModelForm):
    SKIN_TYPE_CHOICES = [
    ('خشک', 'خشک'),
    ('چرب', 'چرب'),
    ('نرمال', 'نرمال'),
    ('ترکیبی', 'ترکیبی'),
    ('حساس', 'حساس'),
]
    skin_type = forms.ChoiceField(choices=SKIN_TYPE_CHOICES, required=False)
    device_type = forms.CharField(required=False)

    class Meta:
        model = User
        fields = [
            'username', 'first_name', 'last_name', 'email',
                'skin_type', 'device_type',
        ]
        widgets = {
            'username': forms.TextInput(attrs={'placeholder': 'نام کاربری'}),
            'first_name': forms.TextInput(attrs={'placeholder': 'نام'}),
            'last_name': forms.TextInput(attrs={'placeholder': 'نام خانوادگی'}),
            'email': forms.EmailInput(attrs={'placeholder': 'ایمیل'}),
            'skin_type': forms.TextInput(attrs={'placeholder': 'نوع پوست'}),

            'device_type': forms.TextInput(attrs={'placeholder': 'نوع دستگاه'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.get('instance')
        super().__init__(*args, **kwargs)
        if user:
            try:
                profile = user.profile
                self.fields['skin_type'].initial = profile.skin_type
                self.fields['device_type'].initial = profile.device_type
            except Profile.DoesNotExist:
                pass

    def save(self, commit=True):
        user = super().save(commit=False)

        if commit:
            user.save()

        profile_data = {
            'skin_type': self.cleaned_data.get('skin_type', ''),
            'device_type': self.cleaned_data.get('device_type', ''),
        }

        Profile.objects.update_or_create(user=user, defaults=profile_data)

        return user
