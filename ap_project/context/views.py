from django.shortcuts import render
from products.models import Product
from django.db.models import Avg, Count
from django.db.models.functions import Coalesce
import jdatetime

def get_persian_season():
    month = jdatetime.date.today().month
    if month in [1, 2, 3]:
        return 'بهار'
    elif month in [4, 5, 6]:
        return 'تابستان'
    elif month in [7, 8, 9]:
        return 'پاییز'
    else:
        return 'زمستان'

def seasonal_products_view(request):
    season = get_persian_season()
    seasonal_products = Product.objects.filter(tags__contains=[season]).annotate(
        avg_rating=Coalesce(Avg('comments__rating'), 0.0),
        comment_count=Coalesce(Count('comments'), 0)
    ).order_by('-avg_rating')

    return render(request, 'context/seasonal_products.html', {
        'season': season,
        'seasonal_products': seasonal_products,
    })