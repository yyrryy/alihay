from __future__ import unicode_literals
from django.db import models
from django.contrib.auth.models import User

from pis_com.models import DatedModel


class Retailer(DatedModel):
    name = models.CharField(max_length=100)
    slug = models.CharField(max_length=100)
    package = models.CharField(max_length=200, null=True, blank=True)
    ice = models.CharField(max_length=200, null=True, blank=True)
    address = models.CharField(max_length=200, null=True, blank=True)
    #if identification fiscal
    id_fiscal = models.CharField(max_length=200, null=True, blank=True)
    cnss = models.CharField(max_length=200, null=True, blank=True)
    phone = models.CharField(max_length=200, null=True, blank=True)
    #patent
    pt = models.CharField(max_length=200, null=True, blank=True)
    package_price = models.CharField(max_length=200, null=True, blank=True)
    package_expiry = models.DateField(blank=True, null=True)
    caisse=models.FloatField(default=0.00)
    bank=models.FloatField(default=0.00)
    # we need initial bank account
    initialbank=models.FloatField(default=0.00)
    caisseexterieur=models.FloatField(default=0.00)
    working=models.BooleanField(default=True)
    logo = models.ImageField(
        upload_to='images/retailer/logo/', max_length=1024,
        blank=True, null=True
    )

    def __unicode__(self):
        return self.name


class RetailerUser(models.Model):
    # ROLE_TYPE_OWNER = 'owner'
    # ROLE_TYPE_DATA_ENTRY_USER = 'data_entry_user'
    # ROLE_TYPE_SALESMAN = 'salesman'
    # ROLE_TYPE_VIEW_ACCOUNT = 'account_viewer'
    # ROLE_TYPE_LEDGER_VIEW = 'ledger_viewer'

    # ROLE_TYPES = (
    #     (ROLE_TYPE_OWNER, 'Owner'),
    #     (ROLE_TYPE_DATA_ENTRY_USER, 'Data Entry User'),
    #     (ROLE_TYPE_SALESMAN, 'Salesman'),
    #     (ROLE_TYPE_VIEW_ACCOUNT, 'Account Viewer'),
    #     (ROLE_TYPE_LEDGER_VIEW, 'Ledger Viewer'),
    # )

    user = models.OneToOneField(User, related_name='retailer_user',on_delete=models.CASCADE)
    retailer = models.ForeignKey(Retailer, related_name='u_retailer',on_delete=models.CASCADE)
    role_type = models.CharField(
        max_length=100, default="owner"
    )

    def __unicode__(self):
        return self.user.username

