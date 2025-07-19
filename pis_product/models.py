from __future__ import unicode_literals
from django.db import models
from django.db.models import Sum, Q, F
import random
from django.db.models.signals import post_save
import json
from pis_com.models import DatedModel, Customer
from pis_sales.models import Avoir
from django.utils import timezone

class Outcaisse(models.Model):
    date=models.DateTimeField(auto_now_add=True)
    amount=models.FloatField()
    raison=models.CharField(max_length=1500, default=None, null=True, blank=True)
    externe=models.BooleanField(default=False)
    charge=models.BooleanField(default=False)

class Outbank(models.Model):
    date=models.DateTimeField(auto_now_add=True)
    amount=models.FloatField()
    raison=models.CharField(max_length=1500, default=None, null=True, blank=True)
    externe=models.BooleanField(default=False)
    charge=models.BooleanField(default=False)
    intern=models.BooleanField(default=False)


class Outcaisseext(models.Model):
    date=models.DateTimeField(auto_now_add=True)
    amount=models.FloatField()
    raison=models.CharField(max_length=1500, default=None, null=True, blank=True)
    interne=models.BooleanField(default=False)
    charge=models.BooleanField(default=False)
    bank=models.BooleanField(default=False)


class Supplier(models.Model):
    name = models.CharField(max_length=100)
    phone1 = models.CharField(max_length=100, default=None)
    phone2 = models.CharField(max_length=100, default=None, null=True, blank=True)
    address = models.CharField(max_length=100, default=None, null=True, blank=True)
    website = models.CharField(max_length=100, default=None, null=True, blank=True)
    total= models.DecimalField(max_digits=65, decimal_places=2, default=0.00)
    rest= models.DecimalField(max_digits=65, decimal_places=2, default=0.00)
    client=models.ForeignKey(Customer, related_name="clientofsupplier", on_delete=models.CASCADE, default=None, blank=True, null=True)
    def __str__(self) -> str:
        return self.name
    def totalstock(self):
        return Product.objects.filter(
            stock__gt=0, originsupp=self
        ).aggregate(total_value=Sum(F('prnet') * F('stock')))['total_value'] or 0
    def sold(self):
        avoirs=Avoirsupp.objects.filter(supplier=self)
        reglementsbl=PaymentSupplier.objects.filter(supplier=self)
        bons=Itemsbysupplier.objects.filter(supplier=self)
        totalbons=bons.aggregate(total=Sum('total'))['total'] or 0
        totalregl=reglementsbl.aggregate(total=Sum('amount'))['total'] or 0
        totalavoirs=avoirs.aggregate(total=Sum('total'))['total'] or 0
        totalreglandavoirs=round(totalavoirs+totalregl, 2)
        return round(totalbons-totalreglandavoirs, 2)

class Avoirsupp(models.Model):
    supplier=models.ForeignKey(Supplier, on_delete=models.CASCADE, default=None)
    date = models.DateTimeField(default=timezone.now)
    items = models.TextField(blank=True, null=True, help_text='Quantity and Product name would save in JSON format')
    total = models.DecimalField(max_digits=65, decimal_places=2, default=0.00)
    receipt_no = models.CharField(
        max_length=20, unique=True, blank=True, null=True
    )
    def getitems(self):
        return json.loads(self.items)
def create_avoir_no(sender, instance, created, **kwargs):
    if created and not instance.receipt_no:
        year_month = timezone.now().strftime("%y")
        latest_receipt = Avoirsupp.objects.filter(
            receipt_no__startswith=f'FAV{year_month}'
        ).order_by("-id").first()
        if latest_receipt:
            latest_receipt_no = int(latest_receipt.receipt_no[-6:])
            receipt_no = f"FAV{year_month}{latest_receipt_no + 1:06}"
        else:
            receipt_no = f"FAV{year_month}000001"
        instance.receipt_no = receipt_no
        instance.save()
post_save.connect(create_avoir_no, sender=Avoirsupp)



class PaymentSupplier(models.Model):
    supplier=models.ForeignKey(Supplier, on_delete=models.CASCADE, default=None)
    date = models.DateTimeField(default=timezone.now)
    amount = models.DecimalField(max_digits=65, decimal_places=2, default=0.00)
    mode=models.CharField(max_length=10, default=None)
    npiece=models.CharField(max_length=100, default=None, null=True, blank=True)
    echeance=models.DateField(default=None, null=True)
    ispaid=models.BooleanField(default=False)
    # this is for the case of payment in cash
    iscash=models.BooleanField(default=False)
    note=models.CharField(max_length=1000, default=None, null=True, blank=True)



class PaymentClient(models.Model):
    isfacture=models.BooleanField(default=False)
    ispaid=models.BooleanField(default=False)
    iscash=models.BooleanField(default=False)
    facture=models.ForeignKey('Facture', on_delete=models.CASCADE, default=None, null=True, blank=True)
    client=models.ForeignKey(Customer, on_delete=models.CASCADE, default=None)
    created_at = models.DateTimeField(auto_now_add=True)
    date = models.DateTimeField(default=timezone.now)
    amount = models.DecimalField(max_digits=65, decimal_places=2, default=0.00)
    mode=models.CharField(max_length=10, default=None)
    npiece=models.CharField(max_length=50, default=None, null=True, blank=True)
    echeance=models.DateField(default=None, null=True)
    note=models.CharField(max_length=1000, default=None, null=True, blank=True)
    bons=models.ManyToManyField('pis_sales.SalesHistory', default=None, blank=True, related_name="bons_reglements")
    bon=models.ForeignKey('pis_sales.SalesHistory', on_delete=models.CASCADE, blank=True, null=True, default=None, related_name="bonofreglements")
    @classmethod
    def totalclientbl(cls, customer):
        return cls.objects.filter(client=customer, isfacture=False).aggregate(
            total_bon_sum=Sum('amount')
        )['total_bon_sum'] or 0  # Return 0 if no bons exist
    @classmethod
    def totalclientfc(cls, customer):
        return cls.objects.filter(client=customer, isfacture=True).aggregate(
            total_bon_sum=Sum('amount')
        )['total_bon_sum'] or 0  # Return 0 if no bons exist


# this acts as a bon achat
class Itemsbysupplier(models.Model):
    supplier= models.ForeignKey(Supplier, related_name='supplier',on_delete=models.CASCADE, default=None)
    date = models.DateTimeField(auto_now_add=True)
    items = models.TextField(blank=True, null=True, help_text='Quantity and Product name would save in JSON format')
    total = models.DecimalField(max_digits=65, decimal_places=2, default=0.00)
    nbon = models.CharField(max_length=100, blank=True, null=True)
    #date in bon
    bondate = models.DateTimeField(blank=True, null=True, default=None)
    rest= models.DecimalField(max_digits=65, decimal_places=2, default=0.00)
    isfacture=models.BooleanField(default=False)
    def tva(self):
        return float(self.total)-round(float(self.total)/1.2, 2)
    def ht(self):
        return round(float(self.total)/1.2, 2)
# items of bon achat


class Avancesbon(models.Model):
    supplier = models.ForeignKey(Supplier, related_name='supplier_avance',on_delete=models.CASCADE, default=None)
    date = models.DateTimeField(auto_now_add=True)
    avance = models.DecimalField(max_digits=65, decimal_places=2, default=0.00)
    details = models.CharField(max_length=100, blank=True, null=True)
    avoinbr = models.CharField(max_length=100, blank=True, null=True)

class Category(models.Model):
    parent = models.ForeignKey('self', related_name='children', on_delete=models.CASCADE, blank =
    True, null=True)
    name = models.CharField(max_length=100)
    def __str__(self) -> str:
        return self.name

class SubCategory(models.Model):
    category = models.ForeignKey(
        Category, related_name='category_subcategory',on_delete=models.CASCADE, default=None
    )
    name = models.CharField(max_length=100)
    def __str__(self) -> str:
        return self.name

class Mark(models.Model):
    name = models.CharField(max_length=100)
    def __str__(self) -> str:
        return self.name

class Product(models.Model):
    category=models.ForeignKey(Category, on_delete=models.CASCADE, default=None)
    name = models.CharField(max_length=5000)
    ref = models.CharField(max_length=5000, default=None, null=True, blank=True)
    brand_name = models.CharField(max_length=200, blank=True, null=True)
    stockfacture=models.FloatField(default=0.00)
    retailer = models.ForeignKey(
        'pis_retailer.Retailer',
        related_name='retailer_product',on_delete=models.CASCADE, default=None
    )
    pr_achat=models.FloatField(default=0.00, null=True)
    # pr magazin
    price=models.FloatField(default=0.00, null=True)
    # prix vente client
    price1=models.FloatField(default=0.00, null=True)
    # prix vente client 2
    price2=models.FloatField(default=0.00, null=True)
    #prix vente gro
    prvente=models.FloatField(default=0.00, null=True)
    pondire=models.FloatField(default=0.00, null=True)
    remise=models.IntegerField(default=0)
    prnet=models.FloatField(default=0.00, null=True)
    prices = models.TextField(default='[]')
    command=models.BooleanField(default=False)
    rcommand=models.BooleanField(default=False)
    commanded=models.BooleanField(default=False)
    qtycommand=models.FloatField(default=0.00)
    disponibleinother=models.BooleanField(default=False)
    # this is the supplier of the commande
    supplier=models.ForeignKey(Supplier, on_delete=models.CASCADE, default=None, null=True, blank=True, related_name="command_supplier")
    originsupp=models.ForeignKey(Supplier, on_delete=models.CASCADE, default=None, null=True, blank=True, related_name="original_supplier")
    mark=models.ForeignKey(Mark, on_delete=models.CASCADE, default=None, null=True, blank=True, related_name="product_mark")
    stock=models.FloatField(default=0.00)
    minstock=models.FloatField(default=0.00)
    car = models.CharField(max_length=5000, blank=True, null=True, default=None)
    bar_code = models.CharField(max_length=500, unique=True, blank=True, null=True)
    image = models.ImageField(upload_to='product_images/', blank=True, null=True)
    
    def getsimillars(self):
        originref=self.ref.split()[0]
        return Product.objects.exclude(id=self.id).filter(category=self.category).filter(ref__startswith=originref).exclude(stock=0)
    def stockvalue(self):
        return round(self.pondire*self.stock, 2)
    # def getprices(self):
    #     prices=json.loads(self.prices)
    #     filtered_prices = [item for item in prices[1:] if float(item[1]) != 0]
    #     return filtered_prices
    

class Productscommand(models.Model):
    product = models.ForeignKey(
        Product, related_name='productcommande',on_delete=models.CASCADE, default=None
    )
    qty=models.DecimalField(max_digits=10, decimal_places=2, default=0.00)


def int_to_bin(value):
        return bin(value)[2:]


def bin_to_int(value):
        return int(value, base=2)


# Signals Function for bar code
def create_save_bar_code(sender, instance, created, **kwargs):

    if not instance.bar_code:
        import time
        from pis_com import ean13

        code = None

        r = random.Random(time.time())
        m = int_to_bin(instance.pk % 4)
        if len(m) == 1:
            m = '0' + m
        elif not len(m):
            m = '00'

        while not code:
            g = ''.join([str(r.randint(0, 1)) for i in range(32)])
            chk = int_to_bin(bin_to_int(g) % 16)

            if len(chk) < 4:
                chk = '0' * (4 - len(chk)) + chk

            chk = ''.join(['1' if x == '0' else '0' for x in chk])

            if m == '11':
                code = ''.join(['1', m, g[:16], chk, g[16:32]])
            elif m == '10':
                code = ''.join(['1', m, g[:11], chk, g[11:32]])
            elif m == '01':
                code = ''.join(['1', m, g[:19], chk, g[19:32]])
            else:
                code = ''.join(
                    ['1', m, g[:9], chk[:2], g[9:23], chk[2:4], g[23:32]])

            code = '%d' % bin_to_int(code)
            code += '%d' % ean13.get_checksum(code)

        instance.bar_code = code
        instance.save()


# Signal Calls bar code
post_save.connect(create_save_bar_code, sender=Product)


class StockIn(models.Model):
    product = models.ForeignKey(
        Product, related_name='stockin_product',on_delete=models.CASCADE, default=None
    )
    quantity = models.FloatField(default=0)
    price=models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total=models.FloatField(default=0.00)
    remise=models.FloatField(default=0.00)
    dated_order = models.DateTimeField(auto_now_add=True)
    reciept=models.ForeignKey(Itemsbysupplier, related_name='supplier_product',on_delete=models.CASCADE, default=None, null=True, blank=True)
    avoir_reciept=models.ForeignKey(Avoir, related_name='avoir_product',on_delete=models.CASCADE, default=None, null=True, blank=True)
    status=models.IntegerField(default=1)
    def __unicode__(self):
        return self.product.name



class ProductDetail(DatedModel):
    product = models.ForeignKey(
        Product, related_name='product_detail',on_delete=models.CASCADE, default=None
    )
    retail_price = models.DecimalField(
        max_digits=65, decimal_places=2, default=0
    )
    consumer_price = models.DecimalField(
        max_digits=65, decimal_places=2, default=0
    )
    available_item = models.IntegerField(default=1)
    purchased_item = models.IntegerField(default=0)

    def __unicode__(self):
        return self.product.name


class Returned(models.Model):
    product=models.ForeignKey(Product, on_delete=models.CASCADE, default=None)
    qty=models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total=models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    price=models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    avoir=models.ForeignKey(Avoir, related_name='returned_invoice', on_delete=models.CASCADE, default=None, null=True, blank=True)
    def __str__(self) -> str:
        return self.product.ref
class PurchasedProduct(DatedModel):
    product = models.ForeignKey(
        Product, related_name='purchased_product',on_delete=models.CASCADE, default=None
    )
    invoice = models.ForeignKey(
        'pis_sales.SalesHistory', related_name='purchased_invoice',
        blank=True, null=True,on_delete=models.CASCADE
    )
    isavoirsupp=models.BooleanField(default=False)
    avoirsupp=models.ForeignKey(Avoirsupp, related_name='avoirsupp', on_delete=models.CASCADE, default=None, null=True, blank=True)
    quantity = models.FloatField(default=1.00, blank=True, null=True
    )
    price = models.FloatField(default=0.00, blank=True, null=True
    )
    discount_percentage = models.FloatField(default=0.00, blank=True, null=True
    )
    purchase_amount = models.FloatField(default=0.00, blank=True, null=True
    )


class ExtraItems(DatedModel):
    retailer = models.ForeignKey(
        'pis_retailer.Retailer', related_name='retailer_extra_items',on_delete=models.CASCADE, default=None
    )
    item_name = models.CharField(
        max_length=100, blank=True, null=True)
    quantity = models.CharField(
        max_length=100, blank=True, null=True)
    price = models.DecimalField(
        max_digits=65, decimal_places=2, default=0, blank=True, null=True)
    discount_percentage = models.DecimalField(
        max_digits=65, decimal_places=2, default=0, blank=True, null=True)
    total = models.DecimalField(
        max_digits=65, decimal_places=2, default=0, blank=True, null=True)

    def __unicode__(self):
        return self.item_name or ''


class ClaimedProduct(DatedModel):
    product = models.ForeignKey(Product, related_name='claimed_product',on_delete=models.CASCADE, default=None)
    customer = models.ForeignKey(
        'pis_com.Customer', related_name='customer_claimed_items',
        null=True, blank=True,on_delete=models.CASCADE
    )
    claimed_items = models.IntegerField(
        default=1, verbose_name='No. of Claimed Items')
    claimed_amount = models.DecimalField(
        max_digits=65, decimal_places=2, default=0, blank=True, null=True)

    def __unicode__(self):
        return self.product.name


class StockOut(models.Model):
    product = models.ForeignKey(
        Product, related_name='stockout_product',on_delete=models.CASCADE, default=None
    )
    invoice = models.ForeignKey(
        'pis_sales.SalesHistory', related_name='out_invoice',
        blank=True, null=True,on_delete=models.CASCADE
    )
    purchased_item = models.ForeignKey(
        PurchasedProduct, related_name='out_purchased',
        blank=True, null=True,on_delete=models.CASCADE
    )
    stock_out_quantity=models.CharField(max_length=100, blank=True, null=True)
    selling_price = models.DecimalField(
        max_digits=65, decimal_places=2, default=0, blank=True, null=True
    )
    buying_price = models.DecimalField(
        max_digits=65, decimal_places=2, default=0, blank=True, null=True
    )
    dated=models.DateField(blank=True, null=True)

    def __unicode__(self):
        return self.product.name


# Signals
def purchase_product(sender, instance, created, **kwargs):

    product_items = (
        instance.product.product_detail.filter(
            available_item__gt=0).order_by('created_at')
    )

    if product_items:
        item = product_items[0]
        item.available_item - 1
        item.save()
# this class <ill track client prices to use in avoir
class Clientprice(models.Model):
    client=models.ForeignKey('pis_com.Customer', on_delete=models.CASCADE, default=None, null=True, blank=True)
    product=models.ForeignKey(Product, on_delete=models.CASCADE, default=None, blank=True, null=True)
    price=models.FloatField(default=0.00, blank=True, null=True)
    qty=models.FloatField(default=0.00, blank=True, null=True)


class Supplierprice(models.Model):
    supplier=models.ForeignKey(Supplier, on_delete=models.CASCADE, default=None, null=True, blank=True)
    product=models.ForeignKey(Product, on_delete=models.CASCADE, default=None, blank=True, null=True)
    price=models.FloatField(default=0.00, blank=True, null=True)
    qty=models.IntegerField(default=0, blank=True, null=True)
    remise=models.IntegerField(default=0, blank=True, null=True)
class Devis(models.Model):
    client=models.ForeignKey(
        'pis_com.Customer', related_name='clientdevis',
        null=True, blank=True,on_delete=models.SET_NULL
    )
    date=models.DateField()
    total=models.FloatField(default=0.00, null=True)
    devis_no=models.CharField(max_length=100)
    isgenerated=models.BooleanField(default=False)

class Devisitems(models.Model):
    devis=models.ForeignKey(Devis, on_delete=models.SET_NULL, null=True)
    product=models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    qty=models.CharField(max_length=500)
    price=models.CharField(max_length=500)
    total=models.CharField(max_length=500)
    
class Facture(models.Model):
    paid_amount=models.FloatField(default=0.00)
    isvalid=models.BooleanField(default=False)
    date = models.DateTimeField(blank=True, null=True)
    code=models.CharField(max_length=50, null=True, default=None)
    total=models.FloatField(default=0.00)
    tva=models.FloatField(default=0.00)
    rest=models.FloatField(default=0.00)
    ispaid=models.BooleanField(default=False)
    facture_no=models.CharField(max_length=50, null=True, default=None)
    client=models.ForeignKey(Customer, on_delete=models.SET_NULL, default=None, null=True)
    # notes of fc
    # printed indicates that this facture was received by the client
    printed = models.BooleanField(default=False)
    note=models.TextField(default=None, null=True, blank=True)
    # true if facture is accounting
    isaccount=models.BooleanField(default=False)
    statusreg=models.CharField(max_length=50, null=True, default='b1', blank=True)
    # if we have more than one bon for the same facture
    def ht(self):
        return round(self.total/1.2, 2)
    def thistva(self):
        return round((self.total/1.2)*.2, 2)
    def reglements(self):
        return PaymentClient.objects.filter(factures__in=[self])
    @classmethod
    def totalclient(cls, customer):
        return cls.objects.filter(client=customer).aggregate(
            total_bon_sum=Sum('total')
        )['total_bon_sum'] or 0  # Return 0 if no bons exist

class Outfacture(models.Model):
    facture=models.ForeignKey(Facture, on_delete=models.CASCADE, default=None)
    total=models.FloatField(default=0.00)
    product=models.ForeignKey(Product, on_delete=models.CASCADE, default=None, null=True)
    remise=models.CharField(max_length=100, null=True, default=None)
    ref=models.CharField(max_length=100, null=True, default=None)
    name=models.CharField(max_length=100, null=True, default=None)
    qty=models.IntegerField()
    # this total represents the revenue of this product
    price=models.FloatField(default=0.00)
    client=models.ForeignKey(Customer, on_delete=models.CASCADE, default=None, null=True, blank=True)
    date=models.DateField(default=None, blank=True, null=True)
    
class Devise(models.Model):
    client=models.ForeignKey(
        'pis_com.Customer', related_name='clientdevise',
        null=True, blank=True,on_delete=models.SET_NULL
    )
    date=models.DateField()
    total=models.FloatField(default=0.00, null=True)
    Devise_no=models.CharField(max_length=100)

class Deviseitems(models.Model):
    devise=models.ForeignKey(Devise, on_delete=models.SET_NULL, null=True)
    article=models.CharField(max_length=500)
    qty=models.CharField(max_length=500)
    price=models.CharField(max_length=500)
    total=models.CharField(max_length=500)
