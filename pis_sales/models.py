from __future__ import unicode_literals
import random
from django.db.models import Sum
from django.db import models
from django.db.models.signals import post_save

from pis_com.models import DatedModel


class SalesHistory(DatedModel):
    isdevis=models.BooleanField(default=False)
    # isfacture will be used if bon is generated to Facture
    isfacture=models.BooleanField(default=False)
    # ismanual will be used to get facture created manually
    ismanual=models.BooleanField(default=False)
    retailer = models.ForeignKey(
        'pis_retailer.Retailer', related_name='retailer_sales',on_delete=models.CASCADE
    )
    receipt_no = models.CharField(
        max_length=20, unique=True, blank=True, null=True
    )
    datebon= models.DateTimeField(default=None, blank=True, null=True)
    customer = models.ForeignKey(
        'pis_com.Customer',
        related_name='customer_sales',
        blank=True, null=True,on_delete=models.CASCADE,
        default=None
    )

    product_details = models.TextField(
        max_length=512, blank=True, null=True,
        help_text='Quantity and Product name would save in JSON format')

    purchased_items = models.ManyToManyField(
        'pis_product.PurchasedProduct',
        max_length=100, blank=True
    )

    extra_items = models.ManyToManyField(
        'pis_product.ExtraItems',
        max_length=200, blank=True,
    )

    total_quantity = models.CharField(
        max_length=10, blank=True, null=True, default=1)

    sub_total = models.DecimalField(
        max_digits=65, decimal_places=2, default=0, blank=True, null=True
    )

    paid_amount = models.DecimalField(
        max_digits=65, decimal_places=2, default=0, blank=True, null=True
    )

    remaining_payment = models.DecimalField(
        max_digits=65, decimal_places=2, default=0, blank=True, null=True
    )

    discount = models.DecimalField(
        max_digits=65, decimal_places=2, default=0, blank=True, null=True
    )

    shipping = models.DecimalField(
        max_digits=65, decimal_places=2, default=0, blank=True, null=True
    )

    grand_total = models.DecimalField(
        max_digits=65, decimal_places=2, default=0, blank=True, null=True
    )

    cash_payment = models.DecimalField(
        max_digits=65, decimal_places=2, default=0, blank=True, null=True
    )

    returned_payment = models.DecimalField(
        max_digits=65, decimal_places=2, default=0, blank=True, null=True
    )

    def __unicode__(self):
        return self.retailer.name
    @classmethod
    def totalclient(cls, customer):
        """
        Returns the total number of bons (sales records) for a given client.
        :param customer_id: ID of the customer
        :return: Total bons as an integer
        """
        return cls.objects.filter(customer=customer).aggregate(
            total_bon_sum=Sum('grand_total')
        )['total_bon_sum'] or 0  # Return 0 if no bons exist
    @classmethod
    def totalclientavance(cls, customer):
        return cls.objects.filter(customer=customer).aggregate(
            total_bon_sum=Sum('paid_amount')
        )['total_bon_sum'] or 0

# Signals Function
from django.utils import timezone

# Signals Function
def create_save_receipt_no(sender, instance, created, **kwargs):
    if created and not instance.receipt_no:
        year_month = timezone.now().strftime("%y")
        latest_receipt = SalesHistory.objects.filter(
            receipt_no__startswith=year_month
        ).last()
        if latest_receipt:
            latest_receipt_no = int(latest_receipt.receipt_no[-6:])
            receipt_no = f"{year_month}{latest_receipt_no + 1:06}"
        else:
            receipt_no = f"{year_month}000001"
        instance.receipt_no = receipt_no
        instance.save()


# Signal Calls
post_save.connect(create_save_receipt_no, sender=SalesHistory)



class Avoir(DatedModel):
    bon = models.ForeignKey(
        SalesHistory, related_name='bon_sortie_of_avoir',on_delete=models.CASCADE, default=None, blank=True, null=True
    )
    dateavoir= models.DateTimeField(default=None, blank=True, null=True)
    retailer = models.ForeignKey(
        'pis_retailer.Retailer', related_name='retailer_avoir',on_delete=models.CASCADE
    )
    receipt_no = models.CharField(
        max_length=20, unique=True, blank=True, null=True
    )

    customer = models.ForeignKey(
        'pis_com.Customer',
        related_name='customer_avoir',
        blank=True, null=True,on_delete=models.CASCADE
    )

    returneditems = models.ManyToManyField(
        'pis_product.Returned',
        related_name='returned',
        max_length=100, blank=True, default=None
    )
    grand_total = models.DecimalField(
        max_digits=65, decimal_places=2, default=0, blank=True, null=True
    )
    isfacture = models.BooleanField(default=False)
    @classmethod
    def totalclient(cls, customer):
        return cls.objects.filter(customer=customer, isfacture=True).aggregate(
            total_bon_sum=Sum('grand_total')
        )['total_bon_sum'] or 0  # Return 0 if no bons exist
    @classmethod
    def totalclientfc(cls, customer):
        return cls.objects.filter(customer=customer, isfacture=True).aggregate(
            total_bon_sum=Sum('grand_total')
        )['total_bon_sum'] or 0  # Return 0 if no bons exist
    

# Signals Function

# Signals Function
def create_avoir_no(sender, instance, created, **kwargs):
    if created and not instance.receipt_no:
        year_month = timezone.now().strftime("%y")
        latest_receipt = Avoir.objects.filter(
            receipt_no__startswith=f'AV{year_month}'
        ).order_by("-id").first()
        if latest_receipt:
            latest_receipt_no = int(latest_receipt.receipt_no[-6:])
            receipt_no = f"AV{year_month}{latest_receipt_no + 1:06}"
        else:
            receipt_no = f"AV{year_month}000001"
        instance.receipt_no = receipt_no
        instance.save()

# Signal Calls
post_save.connect(create_avoir_no, sender=Avoir)
