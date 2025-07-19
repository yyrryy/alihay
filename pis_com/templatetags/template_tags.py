from django import template
from pis_product.models import Product, Category, PaymentSupplier, Mark, PaymentClient
from django.db.models import Count
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q
from django.template.defaultfilters import stringfilter

register = template.Library()

@register.filter(name='intspace')
@stringfilter
def intspace(value):
    # Split the value into integer and decimal parts

    if len(value)>1:
        parts = str(value).split('.')
    # Format the integer part with spaces as thousands separators
        try:
            integer_part = "{:,}".format(int(parts[0])).replace(',', ' ')

            # If there's a decimal part, join it back
            formatted_number = integer_part + ('.' + parts[1] if len(parts) > 1 else '')
        
            return formatted_number
        except:
            return value
    else:
        return value


@register.simple_tag
def product_notifications(retailer_id):
    p=Product.objects.filter(retailer__id=retailer_id)
    return len([i for i in p if i.stock<=i.minstock])

@register.simple_tag
def lenproducts():
    return Product.objects.all().count

@register.simple_tag
def products():
    return Product.objects.all()

@register.filter(name='intspace')
def intspace(value):
    # Split the value into integer and decimal parts

    if len(value)>1:
        parts = str(value).split('.')
    # Format the integer part with spaces as thousands separators
        integer_part = "{:,}".format(int(parts[0])).replace(',', ' ')

        # If there's a decimal part, join it back
        formatted_number = integer_part + ('.' + parts[1] if len(parts) > 1 else '')

        return formatted_number
    else:
        return value


@register.simple_tag
def command():
    return Product.objects.filter(command=True).count

@register.simple_tag
def ensemble():
    ids=[]
    #ids=[5, 17]
    categories=[Category.objects.get(pk=i) for i in ids]
    products = Product.objects.filter(stock=1, category__in=categories).annotate(num_products=Count('id'))
    return products.count()



@register.simple_tag
def alertechsupp():
    tomorrow=timezone.now()+timedelta(days=3)
    return PaymentSupplier.objects.filter(Q(mode="echeanceEspece")| Q(mode="effet")| Q(mode="cheque"), echeance__lte=tomorrow, ispaid=False, iscash=False).count()

@register.simple_tag
def alertechclient():
    tomorrow=timezone.now()+timedelta(days=1)
    return PaymentClient.objects.filter(Q(mode="effet")| Q(mode="cheque"), echeance__lte=tomorrow, ispaid=False).count()


@register.simple_tag
def allcategories():
    return Category.objects.filter(children__isnull=True).order_by('name')


@register.simple_tag
def allmarks():
    return Mark.objects.order_by('name')
