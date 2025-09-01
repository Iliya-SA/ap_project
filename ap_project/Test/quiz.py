import json
from hazm import Normalizer, word_tokenize, Stemmer

# --- سؤالات و گزینه‌ها ---
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
    "forbidden_ingredients": None,  # متن آزاد
    "current_products": None,       # متن آزاد
    "wishlist_feature": None,       # متن آزاد
    "other_notes": None             # متن آزاد
}

# --- جواب کاربر (مثال نمونه) ---
USER_ANSWERS = {
    "skin_type": 2,  # "خشک"
    "main_concern": [2, 5],  # "آکنه و جوش", "پف و حلقه دور چشم"
    "product_type": 1,  # "مرطوب‌کننده"
    "features": [1, 4, 6],  # "مات‌کننده", "حاوی ویتامین C", "بدون عطری"
    "budget": 2,  # "200 تا 400 هزار تومان"
    "brand_preference": 11,  # "برند مهم نیست"
    "texture": 3,  # "کرم"
    "paraben_free": 1,
    "alcohol_free": 2,
    "fragrance_free": 1,
    "absorption": 1,
    "active_ingredients": [1, 2, 4],
    "forbidden_ingredients": "پارابن و سولفات و الکل نباشد",
    "current_products": "مرطوب‌کننده آردن و ژل شست‌وشوی نوتروژینا",
    "wishlist_feature": "محصول سبک با جذب سریع و بوی ملایم",
    "other_notes": "ترجیح می‌دهم محصول گیاهی باشد"
}

# --- پردازش متن با Hazm ---
normalizer = Normalizer()
stemmer = Stemmer()

def extract_keywords(text):
    if not text:
        return []
    text = normalizer.normalize(text)
    tokens = word_tokenize(text)
    stems = [stemmer.stem(t) for t in tokens if len(t) > 2]  # حذف کلمات کوتاه
    return list(set(stems))

# --- ساخت خروجی ---
preferences_output = {}
keywords_output = {}

# تعریف بازه‌های قیمت بر اساس اندیس
BUDGET_RANGES = [
    (0, 200000),
    (200000, 400000),
    (400000, 700000),
    (700000, 1000000),
    (1000000, None)  # None یعنی سقف ندارد
]

for q, opts in QUESTIONS.items():
    ans = USER_ANSWERS.get(q)

    # پردازش بودجه به صورت مستقیم
    if q == "budget" and isinstance(ans, int):
        min_val, max_val = BUDGET_RANGES[ans - 1]  # -1 چون اندیس‌ها از 0 هستند
        preferences_output[q] = {
            "min": min_val,
            "max": max_val
        }
        continue  # از اینجا به بعد ادامه نده چون بودجه کامل پردازش شد

    # چندگزینه‌ای یا تک‌گزینه‌ای
    if isinstance(ans, list):
        if opts:
            preferences_output[q] = [opts[i-1] for i in ans]
        else:
            preferences_output[q] = ans
    elif isinstance(ans, int):
        if opts:
            preferences_output[q] = opts[ans-1]
        else:
            preferences_output[q] = ans
    elif isinstance(ans, str):
        preferences_output[q] = ans
        keywords_output[q] = extract_keywords(ans)

# --- ذخیره در فایل‌ها ---
with open("user_preferences.json", "w", encoding="utf-8") as f:
    json.dump(preferences_output, f, ensure_ascii=False, indent=4)

with open("keywords.json", "w", encoding="utf-8") as f:
    json.dump(keywords_output, f, ensure_ascii=False, indent=4)

print("✅ فایل‌ها ساخته شد: user_preferences.json و keywords.json")
