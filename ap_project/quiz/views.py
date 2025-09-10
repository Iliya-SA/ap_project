from django.shortcuts import render
from django.views import View
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from hazm import Normalizer, word_tokenize, Stemmer
from accounts.models import Profile
import json

normalizer = Normalizer()
stemmer = Stemmer()

# --- سوال‌ها و گزینه‌ها ---
QUESTIONS = {
    "skin_type": ["نرمال", "خشک", "چرب", "ترکیبی", "حساس"],
    "main_concern": [
        "چروک و خطوط ریز", "آکنه و جوش", "منافذ باز", "قرمزی و التهاب",
        "خشکی", "پف و حلقه دور چشم", "پوست کدر",
        "چربی بیش از حد", "عدم یکنواختی رنگ", "لکه‌های قهوه‌ای"
    ],
    "product_type": ["مرطوب‌کننده", "ضد آفتاب", "ضد چروک", "روشن‌کننده", "ضد جوش", "تونر", "پاک‌کننده"],
    "features": [
        "مات‌کننده", "جذب سریع", "تغذیه‌کننده", "حاوی ویتامین C",
        "حاوی اسید هیالورونیک", "بدون عطری", "بدون الکل",
        "فاقد پارابن", "مناسب پوست حساس", "لایه‌بردار ملایم"
    ],
    "budget": [
        "زیر 200 هزار تومان", "200 تا 400 هزار تومان",
        "400 تا 700 هزار تومان", "700 هزار تا 1 میلیون تومان",
        "بالاتر از 1 میلیون تومان"
    ],
    "brand_preference": [
        "ناتورال", "بیولب", "آکوا بیوتی", "اُرگانیکا",
        "ریوِرا", "کلینیکا", "درمالاین", "پِلِنا",
        "سِرِنا", "سِنسِرا", "برند مهم نیست"
    ],
    "texture": ["سرم", "ژل", "کرم", "بالم", "موس", "امولسیون", "اسپری", "فوم"],
    "paraben_free": ["مهم", "فعلاً مهم نیست"],
    "alcohol_free": ["مهم", "فعلاً مهم نیست"],
    "fragrance_free": ["مهم", "فعلاً مهم نیست"],
    "absorption": ["جذب سریع", "ماندگاری بالا", "هر دو مهم نیست"],
    "active_ingredients": [
        "هیالورونیک اسید", "ویتامین C", "اسید سالیسیلیک",
        "نیکوتین‌آمید", "پپتیدها", "رتینول", "هیچکدام"
    ],
    "forbidden_ingredients": None,
    "current_products": None,
    "wishlist_feature": None,
    "other_notes": None
}

# --- سوال‌های چندگزینه‌ای ---
MULTI_KEYS = {"main_concern", "features", "active_ingredients"}

# --- متن فارسی سوال‌ها ---
READABLE_NAMES = {
    "skin_type": "نوع پوست خود را مشخص کنید",
    "main_concern": "اصلی‌ترین مشکل یا نگرانی پوستی شما چیست؟",
    "product_type": "نوع محصولی که به دنبال آن هستید چیست؟",
    "features": "چه ویژگی‌هایی در محصول برای شما اهمیت دارد؟",
    "budget": "بودجه تقریبی خود برای خرید محصول را انتخاب کنید",
    "brand_preference": "آیا ترجیح خاصی برای برند محصول دارید؟",
    "texture": "بافت محصول مورد نظر شما چگونه باشد؟",
    "paraben_free": "آیا محصول فاقد پارابن برای شما مهم است؟",
    "alcohol_free": "آیا محصول فاقد الکل برای شما مهم است؟",
    "fragrance_free": "آیا محصول بدون عطر برای شما مهم است؟",
    "absorption": "ترجیح شما برای جذب محصول چیست؟",
    "active_ingredients": "چه مواد فعالی برای شما اهمیت دارد؟",
    "forbidden_ingredients": "چه مواد یا ترکیباتی برای شما ممنوع است؟",
    "current_products": "محصولات فعلی خود را که استفاده می‌کنید نام ببرید",
    "wishlist_feature": "ویژگی‌های دلخواهی که از محصول انتظار دارید چیست؟",
    "other_notes": "سایر نکات یا توضیحات خود را وارد کنید"
}

# --- بازه‌های قیمت ---
BUDGET_RANGES = [
    (0, 200000), (200000, 400000), (400000, 700000),
    (700000, 1000000), (1000000, None)
]

# --- پردازش متن با Hazm ---
def extract_keywords(text):
    if not text: return []
    t = normalizer.normalize(text)
    tokens = word_tokenize(t)
    stems = [stemmer.stem(tok) for tok in tokens if tok.isalpha() and len(tok) > 2]
    return list(set(stems))

# --- نرمال کردن اندیس بودجه ---
def normalize_budget_index(idx_value):
    try:
        i = int(idx_value)
        if 1 <= i <= len(BUDGET_RANGES):
            return BUDGET_RANGES[i-1]
    except: pass
    return (None, None)

# --- ذخیره در پروفایل ---
@transaction.atomic
def save_preferences_to_profile(user, preferences_output, keywords_output):
    profile, _ = Profile.objects.get_or_create(user=user)
    profile.user_preferences = preferences_output
    profile.keywords = keywords_output
    if 'skin_type' in preferences_output:
        profile.skin_type = preferences_output['skin_type']
    profile.save()
    return profile

# --- View ---
class QuizView(View):
    template_name = 'store/quiz.html'

    def get(self, request):
        readable_questions = [(key, READABLE_NAMES[key], QUESTIONS[key]) for key in QUESTIONS.keys()]
        # build initial form data from user's saved preferences (if any)
        initial = {}
        if request.user.is_authenticated and hasattr(request.user, 'profile') and request.user.profile.user_preferences:
            prefs = request.user.profile.user_preferences
            for key in QUESTIONS.keys():
                if key in prefs:
                    val = prefs[key]
                    if key == 'budget' and isinstance(val, dict):
                        # map budget dict back to index (1-based)
                        for i, (mn, mx) in enumerate(BUDGET_RANGES, start=1):
                            if val.get('min') == mn and val.get('max') == mx:
                                initial['budget'] = i
                                break
                    else:
                        initial[key] = val

        next_url = request.GET.get('next', '')

        return render(request, self.template_name, {
            'readable_questions': readable_questions,
            'multi_keys': json.dumps(list(MULTI_KEYS)),
            'initial_json': json.dumps(initial, ensure_ascii=False),
            'next': next_url,
        })

    def post(self, request):
        preferences_output = {}
        keywords_output = {}

        readable_questions = [(key, READABLE_NAMES[key], QUESTIONS[key]) for key in QUESTIONS.keys()]

        for key, _, options in readable_questions:
            if options:
                if key in MULTI_KEYS:
                    values = request.POST.getlist(f"{key}[]")
                    mapped = []
                    for v in values:
                        if not v: continue
                        try:
                            idx = int(v)
                            if 1 <= idx <= len(options):
                                mapped.append(options[idx-1])
                        except:
                            mapped.append(v)
                    preferences_output[key] = mapped
                else:
                    v = request.POST.get(key, '').strip()
                    try:
                        idx = int(v)
                        if 1 <= idx <= len(options):
                            if key != 'budget':
                                preferences_output[key] = options[idx-1]
                            else:
                                preferences_output[key] = idx
                        else:
                            preferences_output[key] = v
                    except:
                        preferences_output[key] = v
            else:
                txt = request.POST.get(key, '').strip()
                preferences_output[key] = txt
                kws = extract_keywords(txt)
                if kws: keywords_output[key] = kws

        # --- پردازش بودجه ---
        if 'budget' in preferences_output and preferences_output['budget']:
            raw = preferences_output['budget']
            min_b, max_b = normalize_budget_index(raw)
            preferences_output['budget'] = {"min": min_b, "max": max_b}

        # --- کاربر ---
        User = get_user_model()
        if request.user.is_authenticated:
            user = request.user
        else:
            user, _ = User.objects.get_or_create(username='u1', defaults={'email': 'u1@example.com'})
            if not user.has_usable_password():
                user.set_password('testpass')
                user.save()

        profile = save_preferences_to_profile(user, preferences_output, keywords_output)

        # --- آماده‌سازی JSONها (فقط در حافظه، نه روی دیسک) ---
        prefs_json = json.dumps(preferences_output, ensure_ascii=False, indent=4)
        kws_json = json.dumps(keywords_output, ensure_ascii=False, indent=4)

        # بعد از ذخیره، برگرد به آدرس 'next' در صورت وجود و ایمن بودن، وگرنه به روتین
        next_url = request.POST.get('next') or request.GET.get('next') or request.META.get('HTTP_REFERER')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
            return redirect(next_url)
        return redirect('routine')