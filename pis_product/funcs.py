from pis_sales.models import SalesHistory
from django.db.models import Sum
from pis_product.models import PaymentClient, Avoir
def totalclientbons(customer):
    return SalesHistory.objects.filter(customer=customer).aggregate(
        total_bon_sum=Sum('grand_total')
    )['total_bon_sum'] or 0  # Return 0 if no bons exist

def totalclientpaid(customer):
    return SalesHistory.objects.filter(customer=customer).aggregate(
        total_paid_sum=Sum('paid_amount')
    )['total_paid_sum'] or 0  # Return 0 if no payments exist

def totalclientavoirs(customer):
    return Avoir.objects.filter(customer=customer).aggregate(
        total_avoirs_sum=Sum('grand_total')
    )['total_avoirs_sum'] or 0  # Return 0 if no avoirs exist

def totalclientpayments(customer):
    return PaymentClient.objects.filter(client=customer).aggregate(
        total_payments_sum=Sum('amount')
    )['total_payments_sum'] or 0  # Return 0 if no payments exist
