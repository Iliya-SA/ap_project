# recommendation/utils.py
def score_product(user_profile, product):
    """
    یک محصول رو نسبت به پروفایل کاربر امتیاز می‌ده.
    """
    score = 0
    reasons = []

    # ✅ نوع پوست
    if hasattr(product, "skin_type") and product.skin_type:
        if user_profile["skin_type"] and user_profile["skin_type"].lower() in product.skin_type.lower():
            score += 2
            reasons.append(f"مناسب برای پوست {user_profile['skin_type']}")

    # ✅ نگرانی‌ها
    if hasattr(product, "concerns_targeted") and product.concerns_targeted:
        if isinstance(product.concerns_targeted, str):
            product_concerns = [c.strip() for c in product.concerns_targeted.split(",")]
        else:
            product_concerns = product.concerns_targeted

        matched = [c for c in user_profile["concerns"] if c in product_concerns]
        if matched:
            score += len(matched)
            reasons.append(f"هسته آکنه: {', '.join(matched)}")

    # ✅ ترجیحات (tags)
    if hasattr(product, "tags") and product.tags:
        if isinstance(product.tags, str):
            product_tags = [t.strip() for t in product.tags.split(",")]
        else:
            product_tags = product.tags

        matched_prefs = [p for p in user_profile["preferences"] if p in product_tags]
        if matched_prefs:
            score += len(matched_prefs)
            reasons.append(f"ترجیحات رعایت شده: {', '.join(matched_prefs)}")

    return score, " و ".join(reasons) if reasons else "محصول پرطرفدار"