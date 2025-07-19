from __future__ import unicode_literals
from django.shortcuts import render, redirect
import json
from django.views.generic import TemplateView, UpdateView
from django.views.generic import FormView, ListView
from django.http import HttpResponseRedirect, JsonResponse, HttpResponse
from django.urls import reverse, reverse_lazy
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from django.db.models import Sum, F, DecimalField, ExpressionWrapper, Q, BooleanField, Case, When, Value
from django.db.models.functions import Coalesce
from pis_product.models import Outcaisse, PurchasedProduct, ExtraItems,StockOut, StockIn, Product, Category, Supplier, Itemsbysupplier, Avancesbon, Mark, PaymentSupplier, Avoirsupp, PaymentClient, Supplierprice, Clientprice, Returned, Outcaisseext, Outbank
from pis_product.forms import (
    ProductForm, ProductDetailsForm, ClaimedProductForm,StockDetailsForm,StockOutForm, PurchasedProductForm)
import pandas as pd
from django.views.decorators.csrf import csrf_exempt
from pis_retailer.models import Retailer, RetailerUser
from django.db.models import Count
from django.db import transaction
from datetime import datetime, date, timedelta
from pis_sales.models import SalesHistory, Avoir
from pis_com.models import Customer, UserProfile
from itertools import chain
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.serializers import serialize
from pis_sales.forms import BillingForm
import barcode
from barcode.writer import ImageWriter
from io import BytesIO
import base64
this_year = datetime.now().year
this_month = datetime.now().month

def number_to_letters(num):
    result = ''
    alphabet = 'uqslfarch'  # Mapping for digits 1 to 9

    # Convert each digit to a letter, ignore decimals and handle 0s
    for digit in str(num):
        if digit == '.':
            result += '.'  # Preserve the decimal point
        elif digit == '0':
            result += 'x'  # Use 'x' to represent '0'; you can change this if needed
        else:
            index = int(digit) - 1  # Convert to 0-based index
            if 0 <= index < len(alphabet):
                result += alphabet[index]  # Append the corresponding letter

    return result


def letters_to_number(letters):
    result = ''
    alphabet = 'uqslfarch'  # Mapping for digits 1 to 9

    # Convert each letter back to a digit
    for char in letters:
        if char == '.':
            result += '.'  # Preserve the decimal point
        elif char == 'x':
            result += '0'  # Convert 'x' back to '0'
        else:
            index = alphabet.index(char)  # Get index of the letter
            if index != -1:
                result += str(index + 1)  # Convert back to number (1-based)

    return result

def createavoirclient(request, id):
    print('>>', id)
    bon=SalesHistory.objects.get(pk=id)
    print('>>',bon.purchased_items)
    return render(request, 'sales/avoirclient.html', {
        'title':'Avoir client',
        'categories':Category.objects.filter(children__isnull=True).order_by('name'),
        'customers':Customer.objects.all()
        }
    )
def createavoirsupp(request, id):
    userprofile=UserProfile.objects.get(user=request.user)
    if not userprofile.cancreateavoirsupp:
        return render(request, 'products/nopermission.html')
    print('>>', id)
    bon=Itemsbysupplier.objects.get(pk=id)
    return render(request, 'products/avoirsupp.html', {
        'title':'Avoir Fournisseur',
        'bon':bon,
        'items':json.loads(bon.items)
        }
    )

def avoirsupdata(request):
    id=request.POST.get('id')
    avoir=Avoirsupp.objects.get(pk=id)
    items=json.loads(avoir.items)
    return JsonResponse({
        'data':render(request, 'products/avoirsupdata.html', {'bon':avoir, 'items':items}).content.decode('utf-8')
    })

def outcaisse(request):
    retailer=Retailer.objects.get(pk=1)
    amount=request.POST.get('amount')
    externe=request.POST.get('externe')=="on"
    charge=request.POST.get('charge')=="on"
    print('>>>>', externe)
    raison=request.POST.get('raison')
    # allow if amount is less than caisse
    # if float(amount)>float(retailer.caisse):
    #     return redirect('product:caisse')
    # else:
    outc=Outcaisse.objects.create(
        amount=amount,
        raison=raison,
        externe=externe,
        charge=charge
    )
    if externe:
        retailer.caisseexterieur=float(retailer.caisseexterieur)+float(amount)
    retailer.caisse=float(retailer.caisse)-float(amount)
    retailer.save()


    return redirect('product:caisse')
# not finiched yet
def outext(request):
    retailer=Retailer.objects.get(pk=1)
    amount=request.POST.get('amount')
    raison=request.POST.get('raison')
    interne=request.POST.get('interne')=="on"
    charge=request.POST.get('charge')=="on"
    bank=request.POST.get('bank')=="on"
    print(">>>>>>>>>>>>>>>>", amount, interne, charge, bank)
    print(float(amount)>float(retailer.caisseexterieur), 'amount more than caisse exterieur')
    if float(amount)>float(retailer.caisseexterieur):
        return redirect('product:exterieur')
    else:
        retailer.caisseexterieur=float(retailer.caisseexterieur)-float(amount)
        if interne:
            retailer.caisse=float(retailer.caisse)+float(amount)
        if bank:
            retailer.bank=float(retailer.bank)+float(amount)
        retailer.save()
        Outcaisseext.objects.create(
            amount=amount,
            raison=raison,
            interne=interne,
            charge=charge,
            bank=bank
        )

        print(amount, raison)
        return redirect('product:exterieur')

def outbank(request):
    retailer=Retailer.objects.get(pk=1)
    amount=request.POST.get('amount')
    raison=request.POST.get('raison')
    interne=request.POST.get('interne')=="on"
    charge=request.POST.get('charge')=="on"
    externe=request.POST.get('externe')=="on"

    if float(amount)>float(retailer.bank):
        return redirect('product:caisse')
    else:
        retailer.bank=float(retailer.bank)-float(amount)
        if interne:
            retailer.caisse=float(retailer.caisse)+float(amount)
        if externe:
            retailer.caisseexterieur=float(retailer.caisseexterieur)+float(amount)
        retailer.save()
        Outbank.objects.create(
            amount=amount,
            raison=raison,
            intern=interne,
            charge=charge,
            externe=externe
        )

        return redirect('product:bank')

def addcaisse(request):
    retailer=Retailer.objects.get(pk=1)
    caisse=request.POST.get('caisse')
    retailer.caisse=caisse
    retailer.save()
    return redirect('product:caisse')

def addbank(request):
    retailer=Retailer.objects.get(pk=1)
    bank=request.POST.get('bank')
    retailer.bank=bank
    retailer.initialbank=bank
    retailer.save()
    return redirect('product:bank')

def addcaisseextern(request):
    retailer=Retailer.objects.get(pk=1)
    caisse=request.POST.get('caisse')
    retailer.caisseexterieur=caisse
    retailer.save()
    return redirect('product:exterieur')
def caisse(request):
    userprofile=UserProfile.objects.get(user=request.user)
    if not userprofile.canseecaisse:
        return render(request, 'products/nopermission.html')
    # get payments of 10 last days
    retailer=Retailer.objects.get(pk=1)
    outs=Outcaisse.objects.all().order_by('-date')[:10]
    payments=PaymentClient.objects.filter(mode="espece")[:10]
    comptoir=SalesHistory.objects.filter(customer=None)[:10]
    print('>>> p', payments)
    infromcaisseexterne=Outcaisseext.objects.filter(interne=True)[:50]
    releve = [
        (pay, 'pay') for pay in payments
    ] + [
       (cont, 'cont') for cont in comptoir
    ] + [
        (inext, 'inext') for inext in infromcaisseexterne
    ]
    # releve = chain(*[
    # ((pay, 'pay') for pay in payments),
    # ((cont, 'cont') for cont in comptoir),
    # ((inext, 'inext') for inext in infromcaisseexterne),
    # ])
    def get_date(item):
        obj, type_ = item
        if type_ == 'cont':
            
            return obj.datebon if obj.datebon else obj.created_at
        else:
            return obj.date
        
    # Sort the items by date
    ins = sorted(releve, key=get_date, reverse=True)
    #supplierspayments=PaymentSupplier.objects.filter(mode='espece').order_by('-date')[:10]
    avoirclietns=Avoir.objects.filter(customer=None).order_by('-created_at')[:10]
    print('>>>>>>>><', ins)
    ctx={
        'ins':ins,
        'avoirclietns':avoirclietns,
        'title':'Gestion de Caisse',
        'caisse':retailer.caisse,
        'outs':outs,
        'comptoir':comptoir,
        'payments':payments,
        #'supplierspayments':supplierspayments,
    }
    return render(request, 'products/caisse.html', ctx)

def avoircomptoirpage(request):
    return render(request, 'products/avoircomptoir.html', {
        'title':'Avoir Comptoir',

        }
    )

def exterieur(request):
    userprofile=UserProfile.objects.get(user=request.user)
    if not userprofile.canseecaisseextern:
        return render(request, 'products/nopermission.html')
    # get pay  ments of 10 last days
    retailer=Retailer.objects.get(pk=1)
    insfromcaisse=Outcaisse.objects.filter(externe=True)[:31]
    insfrombank=Outbank.objects.filter(externe=True)[:31]
    releve = [
        (caisse, 'caisse') for caisse in insfromcaisse
    ] + [
       (bank, 'bank') for bank in insfrombank
    ]
    # releve = chain(*[
    # ((pay, 'pay') for pay in payments),
    # ((cont, 'cont') for cont in comptoir),
    # ((inext, 'inext') for inext in infromcaisseexterne),
    # ])
    # Sort the items by date
    ins = sorted(releve, key=lambda item: item[0].date, reverse=True)
    outs=Outcaisseext.objects.all().order_by('-date')[:31]
    #supplierspayments=PaymentSupplier.objects.filter(mode='espece').order_by('-date')[:31]
    ctx={
        'title':'Gestion de caisse externe',
        'caisse':retailer.caisseexterieur,
        'ins':ins,
        'outs':outs,
        #'supplierspayments':supplierspayments,
    }
    return render(request, 'products/caisseexterieur.html', ctx)

def addpaymentsclient(request):
    retailer=Retailer.objects.get(pk=1)
    client=Customer.objects.get(pk=request.POST.get('client'))
    date=request.POST.get('date')
    mantant=request.POST.get('mantant')
    mode=request.POST.get('mode')
    echeance=request.POST.get('echeance') or None
    note=request.POST.get('note') or None
    print('>>>>>>', echeance)
    if echeance != '' and echeance != None:
        echeance=datetime.strptime(echeance, '%Y-%m-%d')
    print(client.customer_name, mantant, mode, echeance)
    PaymentClient.objects.create(
        date=date,
        client=client,
        amount=mantant,
        mode=mode,
        echeance=echeance,
        note=note
    )
    client.rest=float(client.rest)-float(mantant)
    client.save()
    print('>>> mode check', not mode=='remise', not mode=='verment')
    # if not mode=='remise':
    #     retailer.caisse+=float(mantant)
    #     retailer.save()
    # if not mode=='verment':
    #     retailer.caisse+=float(mantant)
    #     retailer.save()
    print(mode not in ['remise', 'verment'])
    if mode not in ['remise', 'verment']:
        retailer.caisse += float(mantant)
        retailer.save()
    # when adding ^yment supp, if mode is verement, we dont need to do nothing
    # finish this effe or cheque
    return redirect('ledger:customer_ledger_detail', customer_id=request.POST.get('client'))

def diffuse(request):
    id=request.POST.get('id')
    originid=request.POST.get('originid')
    originproduct=Product.objects.get(pk=originid)
    product=Product.objects.get(pk=id)
    purchaes=PurchasedProduct.objects.filter(product_id=id)
    outs=StockOut.objects.filter(product_id=id)
    stock=product.stock
    purchaes.update(product_id=originid)
    outs.update(product_id=originid)
    StockIn.objects.create(
        product=originproduct,
        quantity=stock
    )

    originproduct.stock=float(originproduct.stock)+float(stock)
    originproduct.save()
    product.delete()
    return JsonResponse({
        'valid':True
    })



def getdeffusionpdct(request):
    ref=request.POST.get('ref').lower()
    id=request.POST.get('id')
    product=Product.objects.get(pk=id)
    categoryid=request.POST.get('categoryid')
    products=Product.objects.filter(category_id=categoryid, ref__icontains=ref).exclude(id=id)
    res=''
    for i in products:
        res+=f'<div class="p-2 mb-2"><input class="form-check-input" type="radio" originid="{id}" originproduct="{product.ref} - {product.car} - {product.mark}" product="{i.ref} - {i.car} - {i.mark}" value="{i.id}" name="deffusionproduct" id="check{i.id}"> <strong class="form-check-label" for="check{i.id}"> {i.ref} {i.car} {i.mark} </strong></div>'
    return JsonResponse({
        'data':res
    })

def inventaire(request):
    # check if its a post request
    if request.method == 'POST':
        id=request.POST.get('id')
        typestock=request.POST.get('typestock')
        if id=='0':
            if typestock=='0':
                products=Product.objects.filter(stock__lte=0).order_by('ref')
            elif typestock=='1':
                products=Product.objects.filter(stock__gt=0).order_by('ref')
            else:
                products=Product.objects.filter().order_by('ref')
        else:
            if typestock=='0':
                products=Product.objects.filter(category_id=id, stock__lte=0).order_by('ref')
            elif typestock=='1':
                products=Product.objects.filter(category_id=id, stock__gt=0).order_by('ref')
            else:
                products=Product.objects.filter(category_id=id).order_by('ref')
        trs=''
        for i in products:
            trs+=f'<tr><td>{i.ref}</td><td>{i.car}</td><td>{int(i.stock)}</td></tr>'
        return JsonResponse({
            'data':trs
        })

    ctx={
        'title':'Inventaire des Produuits',
        #'products':Product.objects.all(),
        'categories':Category.objects.filter(children__isnull=True).order_by('name')
    }
    return render(request, 'products/inventaire.html', ctx)


def pondire(request):
    product=Product.objects.get(pk=request.POST.get('id'))
    stockin=StockIn.objects.filter(product=product)

    qts=0
    prcs=0
    for b in stockin:
        qts+=b['quantity']
        prcs+=b['total']
    pondire=round(prcs/qts, 2)
    prnet=round(pondire-(pondire*product.remise/100), 2)
    product.prnet=prnet
    product.pr_achat=pondire
    product.save()
    return JsonResponse({
        'pondire':True
    })

def printavoirclient(request, id):
    avoir=Avoir.objects.get(pk=id)
    return render(request, 'sales/bon.html', {'inv':avoir, 'title':f'Bon avoir #{avoir.receipt_no}', 'avoir':True})
def avoirsupp(request):
    userprofile=UserProfile.objects.get(user=request.user)
    if not userprofile.cancreateavoirsupp:
        return render(request, 'products/nopermission.html')
    cts={
        'title': 'Avoir Fournisseur',
        'suppliers':Supplier.objects.all(),
    }
    return render(request, 'products/avoirsupp.html', cts)

def generateavoirsupp(request):
    userprofile=UserProfile.objects.get(user=request.user)
    if not userprofile.cancreateavoirsupp:
        return render(request, 'products/nopermission.html')
    supplierid=request.POST.get('supplierid')
    date=request.POST.get('date')
    date=datetime.strptime(f'{date}', '%Y-%m-%d')
    total=request.POST.get('total')
    items = json.loads(request.POST.get('items'))
    supplier=Supplier.objects.get(pk=supplierid)
    supplier.rest=float(supplier.rest)-float(total)
    supplier.save()
    avoir=Avoirsupp.objects.create(
        supplier_id=supplierid, date=date, total=total, items=json.dumps(items)
        )
    with transaction.atomic():
        for i in items:
            item=i.get('item_id')
            product = Product.objects.get(pk=item)
            # append product.prices

            print(float(supplier.rest)-float(total))
            PurchasedProduct.objects.create(
                avoirsupp=avoir,
                product=product,
                quantity=float(i['qty']),
                isavoirsupp=True,
            )

            product.stock=float(product.stock)-float(i['qty'])
            product.save()
            originref=product.ref.split(' ')[0]
            simillar = Product.objects.filter(category=product.category.id).filter(Q(ref__startswith=originref+' ') | Q(ref=originref))
            simillar.update(disponibleinother=True)
            simillar.update(rcommand=False)
            simillar.update(command=False)
            simillar.update(supplier=None)
            simillar.update(commanded=False)
    return JsonResponse({'status':'ok'})


@csrf_exempt
def getsupplierdata(request):
    id=request.POST.get('id')
    supplier=Supplier.objects.get(pk=id)
    return JsonResponse({
        'name':supplier.name,
        'phone1':supplier.phone1,
        'phone2':supplier.phone2,
        'address':supplier.address,
        'website':supplier.website,
    })
@csrf_exempt
def getclientdata(request):
    id=request.POST.get('id')
    supplier=Customer.objects.get(pk=id)
    return JsonResponse({
        'name':supplier.customer_name,
        'phone1':supplier.customer_phone,
        'address':supplier.address,
        'ice':supplier.ice,
    })


@csrf_exempt
def relveclient(request):
    start_date_str = request.GET.get('start')
    end_date_str = request.GET.get('end')
    customer = request.GET.get('customer')
    start_date = datetime.strptime(start_date_str[:10], '%d/%m/%Y')
    end_date = datetime.strptime(end_date_str[:10], '%d/%m/%Y') + timedelta(days=1)
    print(start_date, end_date)
    bons = SalesHistory.objects.filter(customer_id=customer, datebon__range=[start_date, end_date]).order_by('datebon')
    avoirs = Avoir.objects.filter(customer_id=customer, created_at__range=[start_date, end_date])
    payments=PaymentClient.objects.filter(client_id=customer, created_at__range=[start_date, end_date])
    sales_and_returns = chain(bons, avoirs, payments)
    customer=Customer.objects.get(pk=customer)
    totalbons=bons.aggregate(Sum('grand_total')).get('grand_total__sum') or 0
    totalcredit=(avoirs.aggregate(Sum('grand_total')).get('grand_total__sum') or 0)+(payments.aggregate(Sum('amount')).get('amount__sum') or 0)

    def get_date(item):
        obj, type_ = item
        if type_ == 'bon':
            return obj.datebon
        elif type_ == 'avoir':
            return obj.dateavoir if obj.dateavoir else obj.created_at
        elif type_ == 'reglement':
            return obj.date
        elif type_ == 'relementsupp' or type_ == 'avoirsupp':
            return obj.date
        elif type_ == 'bonachat':
            return obj.bondate
        else:
            raise ValueError("Unknown type: {}".format(type_))
    # Combine all items
    releve = [
        (bon, 'bon') for bon in bons
    ] + [
        (avoir, 'avoir') for avoir in avoirs
    ] + [
        (reglementbl, 'reglement') for reglementbl in payments
    ]
    if customer.supplier:
        supplierbons=Itemsbysupplier.objects.filter(supplier=customer.supplier, bondate__range=[start_date, end_date])
        releve.extend((bonachat, 'bonachat') for bonachat in supplierbons)
        if supplierbons:
            totalcredit+=supplierbons.aggregate(Sum('total')).get('total__sum') or 0
        # get reglement given to this suppplier
        suppregl=PaymentSupplier.objects.filter(supplier=customer.supplier, date__range=[start_date, end_date])
        print('>>> suppregl', suppregl)
        releve.extend((relementsupp, 'relementsupp') for relementsupp in suppregl)
        if suppregl:
            totalbons+=suppregl.aggregate(Sum('amount')).get('amount__sum') or 0
        avoirsupp_=Avoirsupp.objects.filter(supplier=customer.supplier, date__range=[start_date, end_date])
        releve.extend((avoirsupp, 'avoirsupp') for avoirsupp in avoirsupp_)
        if avoirsupp_:
            totalbons+=avoirsupp_.aggregate(Sum('total')).get('total__sum') or 0
    sold=float(totalbons)-float(totalcredit)
    #sorted_releve = sorted(releve, key=get_date)

    #print(sorted_releve)
    #totaldebit=round(bons.a)
    # Sort the items by date
    sorted_releve = sorted(releve, key=get_date)
    #print('>> ', [i for i in sorted_releve])
    return render(request, 'products/relveclient.html', {'releve':sorted_releve, 'sales_and_returns': sales_and_returns, 'bons': bons, 'avoirs':avoirs, 'payments':payments, 'title':f'Relevé client {customer} du {start_date_str} au {end_date_str}', 'customer':customer, 'start_date':start_date_str, 'end_date':end_date_str,
    'totaldebit':totalbons,
    'totalcredit':totalcredit,
    'sold':sold
    })


@csrf_exempt
def relvesupp(request):
    # start_date_str = request.GET.get('start')
    # end_date_str = request.GET.get('end')
    # supplier = request.GET.get('supplier')
    # supplier=Supplier.objects.get(pk=supplier)
    # start_date = datetime.strptime(start_date_str[:10], '%d/%m/%Y')
    # end_date = datetime.strptime(end_date_str[:10], '%d/%m/%Y') + timedelta(days=1)

    # bons = Itemsbysupplier.objects.filter(supplier_id=supplier, date__range=[start_date, end_date]).order_by('date')
    # payments = PaymentSupplier.objects.filter(supplier_id=supplier, date__range=[start_date, end_date]).order_by('date')
    # avoirs=Avoirsupp.objects.filter(supplier_id=supplier, date__range=[start_date, end_date]).order_by('date')
    # totalavoirs=avoirs.aggregate(total=Sum('total'))['total'] or 0
    # totalpayments=payments.aggregate(total=Sum('amount'))['total'] or 0
    # sales_and_returns = sorted(chain(bons, payments, avoirs), key=lambda item: item.date)
    supplierid=request.GET.get('supplier')
    print('>>>', supplierid)
    supplier=Supplier.objects.get(pk=supplierid)
    startdate=request.GET.get('start')
    enddate=request.GET.get('end')
    startdate = datetime.strptime(startdate, '%d/%m/%Y')
    enddate = datetime.strptime(enddate, '%d/%m/%Y')+ timedelta(days=1)
    avoirs=Avoirsupp.objects.filter(supplier_id=supplierid, date__range=[startdate, enddate])
    reglementsbl=PaymentSupplier.objects.filter(supplier_id=supplierid, date__range=[startdate, enddate])

    bons=Itemsbysupplier.objects.filter(supplier_id=supplierid, bondate__range=[startdate, enddate])
    totalbons=bons.aggregate(total=Sum('total'))['total'] or 0
    totalregl=reglementsbl.aggregate(total=Sum('amount'))['total'] or 0
    totalavoirs=avoirs.aggregate(total=Sum('total'))['total'] or 0
    totalreglandavoirs=round(totalavoirs+totalregl, 2)
    def get_date(item):
        obj, type_ = item
        if type_ == 'bon':
            return obj.bondate
        elif type_ == 'avoir':
            return obj.date
        elif type_ == 'reglement' or type_ == 'reglclient':
            return obj.date
        elif type_ == 'bonclient':
            return obj.datebon
        elif type_ == 'avoirclient':
            return obj.created_at
        else:
            raise ValueError("Unknown type: {}".format(type_))
    # Combine all items
    releve = [
        (bon, 'bon') for bon in bons
    ] + [
        (avoir, 'avoir') for avoir in avoirs
    ] + [
        (reglementbl, 'reglement') for reglementbl in reglementsbl
    ]
    print('>>> ',totalbons)
    if supplier.client:
        clientavoirs=Avoir.objects.filter(customer=supplier.client, created_at__range=[startdate, enddate])
        clientbons=SalesHistory.objects.filter(customer=supplier.client, datebon__range=[startdate, enddate])
        clientregls=PaymentClient.objects.filter(client=supplier.client, date__range=[startdate, enddate])
        releve.extend((bonclient, 'bonclient') for bonclient in clientbons)
        releve.extend((reglclient, 'reglclient') for reglclient in clientregls)
        # this is debit
        if clientbons:
            totalreglandavoirs=totalreglandavoirs+clientbons.aggregate(Sum('grand_total')).get('grand_total__sum') or 0

        releve.extend((avoirclient, 'avoirclient') for avoirclient in clientavoirs)
        if clientavoirs:
            totalbons+=clientavoirs.aggregate(Sum('grand_total')).get('grand_total__sum') or 0
        if clientregls:
            totalbons+=clientregls.aggregate(Sum('amount')).get('amount__sum') or 0
    #sorted_releve = sorted(releve, key=lambda item: item[0].bondate if item[1]=='bon' else item[0].date)
    sorted_releve = sorted(releve, key=get_date)
    return render(request, 'products/relvesupp.html', {
        # 'bonandpayments': sales_and_returns,
        # 'bons': bons,
        # 'avoirs': avoirs,
        # 'title':f'Relevé Fournisseur {supplier} du {start_date_str} au {end_date_str}',
        # 'supplier':supplier,
        'start_date':request.GET.get('start'),
        'end_date':request.GET.get('end'),
        # 'totalpayments':totalpayments,
        # 'totalavoirs':totalavoirs,
        'title':f'Relevé Fournisseur {supplier} du {startdate} au {enddate}',
        'totaldebit':totalbons,
        'totalcredit':totalreglandavoirs,
        'sold':round(float(totalbons)-float(totalreglandavoirs), 2),
        'supplier':supplier,
        'releve':sorted_releve
        })


@csrf_exempt
def bondata(request):
    id=request.POST.get('id')
    bon=SalesHistory.objects.get(pk=id)
    #here
    items=PurchasedProduct.objects.filter(invoice=bon)

    avoirs=Avoir.objects.filter(bon=bon)
    print(avoirs)
    return JsonResponse({
        'data':render(request, 'products/bondata.html', {'bon':bon,
        'avoir':False, 'avoirs':avoirs, 'items':items
        }).content.decode('utf-8')
    })

@csrf_exempt
def avoirdata(request):
    id=request.POST.get('id')
    bon=Avoir.objects.get(pk=id)
    return JsonResponse({
        'data':render(request, 'products/bondata.html', {'bon':bon, 'avoir':True}).content.decode('utf-8')
    })

def duplicate(request):
    pp=Product.objects.get(id=request.POST.get('id'))
    rr=request.POST.get('ref')
    categoryid=request.POST.get('categoryid')
    mark=request.POST.get('mark')
    if int(mark)==int(pp.mark.id):
        return JsonResponse({
            'valid':False,
            'error':'Vous avez choisi la même marque'
        })
    product=Product.objects.create(
        retailer_id=1,
        price=0,
        pr_achat=0,
        category=Category.objects.get(pk=categoryid),
        stock=0,
        car=pp.car,
        ref=f'{pp.ref} {rr}',
        originsupp=pp.supplier,
        mark_id=mark,
        image=pp.image,
    )
    StockIn.objects.create(
        product=product,
        quantity=0,
    )
    originref=product.ref.split(' ')[0]
    simillar = Product.objects.filter(category=product.category).filter(Q(ref__startswith=originref+' ') | Q(ref=originref))
    sim=any([int(i.stock) for i in simillar])
    if sim:
        simillar.update(disponibleinother=True)
        simillar.update(rcommand=False)
    else:
        simillar.update(disponibleinother=False)
        simillar.update(rcommand=True)
    return JsonResponse({
        'valid':True
    })

def refreshitemssupplier(request):
    supplier=request.POST.get('supplier')
    products=Product.objects.filter(supplier_id=supplier)
    return JsonResponse({
        'data':render(request, 'products/refreshsupplierproducts.html', {'products':products}).content.decode('utf-8'),
        'len':len(products)
    })


def searchrefinstock(request):
    ref=request.POST.get('ref')
    # Split the term into individual words separated by '*'
    search_terms = ref.split('*')

    # Create a list of Q objects for each search term and combine them with &
    q_objects = Q()
    for term in search_terms:
        if term:
            q_objects &= (Q(ref__iregex=term) | Q(car__iregex=term)| Q(category__name__iregex=term))

    products = Product.objects.filter(q_objects).order_by('-stock')

    ctx={
        'products':products,
        'home':False,
        'marks':Mark.objects.all()
    }
    return JsonResponse({
        'data':render(request, 'products/product_search.html', ctx).content.decode('utf-8')
    })

def refreshmark(request):
    marks=Mark.objects.all()
    options=''
    for mark in marks:
        options+=f'<option value="{mark.id}">{mark.name.upper()}</option>'
    return JsonResponse({
        'data':options
    })

def refexeption(request):
    ref=request.POST.get('ref')
    categoryid=request.POST.get('categoryid')
    products=Product.objects.filter(category_id=categoryid, ref__icontains=ref)
    if request.POST.get('type')=='inv':
        # products=products.filter(stock__gt=0)
        return JsonResponse({
        'data':render(request, 'products/invoicepdcts.html', {'products':products}).content.decode('utf-8'),
    })
    return JsonResponse({
        'data':render(request, 'products/refexeption.html', {'products':products}).content.decode('utf-8'),
    })


def filtercommandesupp(request):
    products=Product.objects.filter(supplier_id=request.POST.get('supplierid'))
    print(products)
    suppliers_data = Supplier.objects.all()
    return JsonResponse({
        'data':render(request, 'products/commandefilter.html', {'products':products, 'suppliers':suppliers_data}).content.decode('utf-8'),
        'len':len(products)
    })

# add new ledger from modal
@csrf_exempt
def addclient(request):
    name=request.POST.get('name')
    phone=request.POST.get('phone')
    address=request.POST.get('address')
    ice=request.POST.get('ice')
    sold=request.POST.get('sold') or 0
    client=Customer.objects.create(rest=sold, customer_name=name,customer_phone=phone, address=address, ice=ice, retailer=Retailer.objects.get(id=request.user.retailer_user.retailer.id))
    return JsonResponse({'status':True, 'id':client.id})

def checkclient(request):
    phone=request.POST.get('phone')
    customer=Customer.objects.filter(customer_phone=phone)
    if customer:
        return JsonResponse({
            'exist':True
        })
    return JsonResponse({
        'exist':False
    })

def productslistbycategory(request):
    userprofile=UserProfile.objects.get(user=request.user)
    if not userprofile.canseeproduits:
        return render(request, 'products/nopermission.html')
    categories = Category.objects.filter(parent=None).order_by('name')
    cc = Category.objects.filter(children__isnull=True).order_by('name')
    parents = Category.objects.all()
    first=0
    if cc:
        first=cc[0].id

    ctx={
        'parents':parents,
        'categories':categories,
        'title':'Liste Articles par categorie',
        'children':cc,
        #first id to put it in the form of adding bulk
        'firstid':first,
        'suppliers':Supplier.objects.all(),
        'marks':Mark.objects.all()
    }
    return render(request, 'products/productslistbycategory.html', ctx)




def retour(request):
    purchase=PurchasedProduct.objects.get(pk=request.POST.get('purchaseid'))
    qty=request.POST.get('qtyinp')
    productid=request.POST.get('productid')
    if float(qty)==float(purchase.quantity):
        purchase.delete()
        # purchase.save()
    else:
        purchase.quantity=float(purchase.quantity)-float(qty)
        purchase.save()
    product=Product.objects.get(pk=productid)
    product.stock=float(product.stock)+float(qty)
    product.save()
    originref=product.ref.split(' ')[0]
    simillar = Product.objects.filter(category=product.category.id).filter(Q(ref__startswith=originref+' ') | Q(ref=originref))
    simillar.update(disponibleinother=True)
    simillar.update(rcommand=False)
    return redirect('product:producthistory', productid)

def lowstock(request):
    userprofile=UserProfile.objects.get(user=request.user)
    if not userprofile.canseealerts:
        return render(request, 'products/nopermission.html')
    supplierid=request.POST.get('supplierid')
    products=Product.objects.filter(stock__lte=F('minstock')).annotate(
    is_preferred_supplier=Case(
        When(originsupp_id=supplierid, then=Value(True)),
        default=Value(False),
        output_field=BooleanField(),
    )).order_by('-is_preferred_supplier')
    cc = Category.objects.filter(
    product__in=products
    ).distinct()
    targets = Category.objects.filter(parent__isnull=False, product__stock__lte=F('product__minstock')).annotate(
    total_products=Count('product')
    )
    return render(request, 'products/lowstock.html', {'title':'Rupture Stock', 'categories':targets, 'ids':cc.values_list('id', flat=True),
    'suppliers':Supplier.objects.all()})


def lowintwins(request):
    ids=[54, 70, 58, 86, 90, 75, 51, 76]
    #ids=[5, 17]
    categories=Category.objects.filter(pk__in=ids, product__stock=1).annotate(total_products=Count('product'))
    ctx={
        'title':'Stock alert twins',
        'categories':categories,
        'suppliers':Supplier.objects.all()
    }
    return render(request, 'products/twinstock.html', ctx)



def lowinarr(request):
    categories=Category.objects.filter(pk=77, product__stock__lt=4).annotate(total_products=Count('product'))
    ctx={
        'title':'Stock alert twins',
        'categories':categories,
        'suppliers':Supplier.objects.all()
    }
    print(categories)
    return render(request, 'products/lowarr.html', ctx)


def getlowintwins(request):
    category=request.POST.get('category')
    # get rpoducts by catgoory and having stock not devided by 2
    products = Product.objects.filter(category=Category.objects.get(pk=category), stock=1)

    ctx={
        'products':products,
        'suppliers':Supplier.objects.all()
    }
    return JsonResponse({
        'data':render(request, 'products/low_stock.html', ctx).content.decode('utf-8')
    })

def getlowinarr(request):
    category=request.POST.get('category')
    # get rpoducts by catgoory and having stock not devided by 2
    products = Product.objects.filter(category=Category.objects.get(pk=category), stock__lt=4)

    ctx={
        'products':products,
        'suppliers':Supplier.objects.all()
    }
    return JsonResponse({
        'data':render(request, 'products/low_stock.html', ctx).content.decode('utf-8')
    })


def searchrefinlow(request):
    ref=request.POST.get('ref').lower()
    search_terms=ref.split('+')
    # get products that starts with ref and stock = 0
    #products=Product.objects.filter(ref__istarts=ref, stock=0)
    q_objects = Q()
    for term in search_terms:
        if term:
            q_objects &= (Q(ref__iregex=term) | Q(car__iregex=term)| Q(category__name__iregex=term))

    products = Product.objects.filter(stock__lte=F('minstock')).filter(q_objects)

    ctx={
        'products':products,
        #'suppliers':Supplier.objects.all()
    }
    return JsonResponse({
        'data':render(request, 'products/low_stock.html', ctx).content.decode('utf-8')
    })

def categories(request):
    categories = Category.objects.all()
    ctx={
        'cc':categories,
        'title':'Liste Categories'
    }
    return render(request, 'products/categories.html', ctx)

def getproductsbycategory(request):
    # category = Category.objects.get(pk=request.POST.get('category'))
    # products = category.product.filter(category=category)[:10]
    # get ten products from the category
    products = Product.objects.filter(category__pk=request.POST.get('category')).order_by('-id')[:50]
    ctx={
        'products':products,
        'home':False,
        'marks':Mark.objects.all()
    }
    return JsonResponse({
        'data':render(request, 'products/product_search.html', ctx).content.decode('utf-8')
    })

def loadpdctsinstock(request):
    page=int(request.GET.get('page', 1))
    categoryid=request.GET.get('categoryid')
    perpage=50
    start=perpage*(page-1)
    end=perpage*page
    print('>>>>>>>>',page, start, end)
    products=Product.objects.filter(category_id=categoryid).order_by('-id')[start:end]
    ctx={
        'products':products,
        'home':False,
        'marks':Mark.objects.all()
    }
    return JsonResponse({
        'trs':render(request, 'products/product_search.html', ctx).content.decode('utf-8'),
        'has_more':len(products)==perpage
    })


def productscommande(request):
    userprofile=UserProfile.objects.get(user=request.user)
    if not userprofile.canseecommandes:
        return render(request, 'products/nopermission.html')
    #products=Product.objects.filter(command=True)
    suppliers=Supplier.objects.filter(
                command_supplier__in=Product.objects.all()
            ).distinct()
    return render(request, 'products/productscommande.html', {
        'title': 'commande',
        #'products':products,
        'suppliers':suppliers
        })

#low stok by category
def getlowbycategory(request):
    # category = Category.objects.get(pk=request.POST.get('category'))
    # products = category.product.filter(category=category)[:10]
    # get ten products from the category
    category_id = request.POST.get('category')
    supplierid = request.POST.get('supplierid')
    print('supplierid >>>>>>>>>><', supplierid)
    #products = Product.objects.filter(category_id=category_id, stock__lte=F('minstock'), originsupp_id=supplierid)
    products = Product.objects.filter(category_id=category_id, stock__lte=F('minstock')).annotate(
    is_preferred_supplier=Case(
        When(originsupp_id=supplierid, then=Value(True)),
        default=Value(False),
        output_field=BooleanField(),
    )).order_by('-is_preferred_supplier')

    suppliers=Supplier.objects.all()
    marks=set([i.mark for i in products])
    marks=[{"name":i.name if i else '', 'id':i.id if i else ''} for i in marks]
    ctx={
        'products':products,
        'suppliers':suppliers,
        'marks':marks
    }
    return JsonResponse({
        'data':render(request, 'products/low_stock.html', ctx).content.decode('utf-8')
})

# not in use
def searchproductsincategory(request):
    # Category=Category.objects.get(pk=request.POST.get('category'))
    # products = Category.product.filter(name__icontains=request.POST.get('item'))
    # earch products in category given
    products = Product.objects.filter(category__pk=request.POST.get('category'), name__icontains=request.POST.get('name'))
    ctx={
        'products':products,
        'home':False
    }
    return JsonResponse({
        'data':render(request, 'products/product_search.html', ctx).content.decode('utf-8')
    })


@csrf_exempt
def addbulkcategory(request, id):
    userprofile=UserProfile.objects.get(user=request.user)
    if not userprofile.canaddbulkcategory:
        return render(request, 'products/nopermission.html')
    myfile=request.FILES["excel_file"]
    retailer=request.user.retailer_user.retailer
    df = pd.read_excel(myfile)
    #df = df.fillna('-')
    for d in df.itertuples():
        ref=str(d.ref).lower().strip()
        prnet=round(float(d.prachat)-(float(d.prachat)*float(d.remise)/100), 2) if d.prachat != 0 else 0
        prachat=d.prachat
        remise=d.remise
        try:
            product=Product.objects.get(ref=ref)
            product.pr_achat=prachat
            product.remise=remise
            product.prnet=prnet
            product.stock=d.qty
            product.save()
        except Exception as e:
            with open('refferrors.txt', 'a') as ff:
                print(f'{ref} => {e}', file=ff)

    #return a json response
    return redirect('product:productslistbycategory')


@csrf_exempt
def addcategory(request):
    userprofile=UserProfile.objects.get(user=request.user)
    if not userprofile.canaddcategory:
        return render(request, 'products/nopermission.html')
    category=request.POST.get('category')
    parent=None if request.POST.get('parent')=='0' else Category.objects.get(pk=request.POST.get('parent'))
    Category.objects.create(name=category, parent=parent)
    return redirect('product:productslistbycategory')

def deletecategory(request, id):
    userprofile=UserProfile.objects.get(user=request.user)
    if not userprofile.candeletecategory:
        return render(request, 'products/nopermission.html')
    category=Category.objects.get(pk=id)
    category.delete()
    return redirect('product:categories')


def updatebonline(request, id):
    itemid=request.POST.get('itemid')
    qty=request.POST.get('qty')
    product=Product.objects.get(pk=itemid)
    bon=Itemsbysupplier.objects.get(pk=id)
    stockin=StockIn.objects.get(reciept_id=id, product_id=itemid)
    avance = Avancesbon.objects.filter(bon_id=id)
    items=json.loads(bon.items)
    sumavances=sum([i.avance for i in avance])
    itemtoupdate = next((item for item in items if item['item_id'] == itemid), None)
    items = [item for item in items if item['item_id'] != itemid]


    if float(qty)==0:
        stockin.delete()
        product.stock=float(product.stock)-float(qty)
        product.save()
        newstock=product.stock
        if newstock==0:
            originref=product.ref.split(' ')[0]
            simillar = Product.objects.filter(category=product.category).filter(Q(ref__startswith=originref+' ') | Q(ref=originref))
            sim=any([int(i.stock) for i in simillar])
            if sim:
                simillar.update(disponibleinother=True)
                simillar.update(rcommand=False)
            else:
                simillar.update(disponibleinother=False)
                simillar.update(rcommand=True)
        total = itemtoupdate['total']
        if items:
            # items not empty
            newtotal=float(bon.total)-float(total)
            newrest=float(newtotal)-float(sumavances)
            bon.total=newtotal
            bon.rest=newrest
            bon.items=json.dumps(items)
            bon.save()
            return redirect('product:bonentree', id)
        else:
            # items empty
            bon.delete()
            avance.delete()
            return redirect('product:bonsentrees')

    else:
        price=request.POST.get('price')
        remise=request.POST.get('remise')
        total=request.POST.get('total')
        # update stockin
        stockin.quantity=qty
        stockin.save()
        #update item in bon
        # old total to compare
        oldtotal=itemtoupdate['total']
        itemtoupdate['total']=total
        itemtoupdate['remise']=remise
        itemtoupdate['qty']=qty
        itemtoupdate['price']=price
        newtotal=float(bon.total)-float(oldtotal)+float(total)
        newrest=float(newtotal)-float(sumavances)
        items.insert(0, itemtoupdate)
        bon.items=json.dumps(items)
        bon.total=newtotal
        bon.rest=newrest
        bon.save()
        # uppdate stock
        product.stock=float(product.stock)-float(qty)
        product.save()
        originref=product.ref.split(' ')[0]
        simillar = Product.objects.filter(category=product.category).filter(Q(ref__startswith=originref+' ') | Q(ref=originref))
        sim=any([int(i.stock) for i in simillar])
        if sim:
            simillar.update(disponibleinother=True)
            simillar.update(rcommand=False)
        else:
            simillar.update(disponibleinother=False)
            simillar.update(rcommand=True)
    return redirect('product:bonentree', id)

@csrf_exempt
def product_search(request):
    ref=request.POST.get('ref')
    car=request.POST.get('car')
    category=request.POST.get('category')
    query = Q()
    if ref:
        query &= Q(ref__icontains=ref)
    if car:
        query &= Q(car__icontains=car)
    if category:
        query &= Q(category= category)
    products = request.user.retailer_user.retailer.retailer_product.filter(query).order_by('-stock')
    return JsonResponse({
        'data': render(request, 'products/product_search.html', {'products': products, 'home':True}).content.decode('utf-8')
    })

@csrf_exempt
def searchglobal(request):
    term = request.POST.get('global')

    # Split the term into individual words separated by '*'
    search_terms = term.split('*')

    # Create a list of Q objects for each search term and combine them with &
    q_objects = Q()
    for term in search_terms:
        if term:
            q_objects &= (Q(ref__iregex=term) | Q(car__iregex=term)| Q(category__name__iregex=term))

    products = Product.objects.filter(q_objects).order_by('-stock')

    return JsonResponse({
        'data': render(request, 'products/product_search.html', {'products': products, 'home': True}).content.decode('utf-8')
    })

@csrf_exempt
def getproducts(request):
    products = Product.objects.filter(name__icontains=request.POST.get('item'))
    return JsonResponse({
        'data':render(request, 'products.html', {'products': products}).content.decode('utf-8')
    })


@csrf_exempt
def addbulk(request):
    # get the uploaded file

    myfile=request.FILES[next(iter(request.FILES))]
    retailer=Retailer.objects.get(id=request.user.retailer_user.retailer.id)

    df = pd.read_excel(myfile)
    df = df.fillna('-')
    for d in df.itertuples():
        product = Product.objects.create(
            retailer=retailer,
            name=d.article,
            brand_name=d.marque,
            price=d.prix,
            pr_achat=d.prachat
        )
        StockIn.objects.create(
            product=product,
            quantity=d.qty,
        )
    #return a json response
    return redirect('index')



def updatestock(request):
    qty=float(request.POST.get('sortieqty'))
    id=request.POST.get('id')
    product=Product.objects.get(pk=id)
    prices=json.loads(product.prices)
    # price=product.pr_achat
    price=float(request.POST.get('price'))
    refinput=request.POST.get('ref')
    carinput=request.POST.get('car')
    categoryinput=request.POST.get('category')
    # from here
    amount=float(qty)*float(price)
    for b, p in enumerate(prices[:1]):
        if float(p[0])==price:
            news=float(prices[b][1])-float(qty)
            # if news==0:
            #     prices.pop(b)
            #     product.prices=json.dumps(prices)
            # else:
            #     prices[b][1] =float(prices[b][1])-float(qty)
            #     product.prices=json.dumps(prices)
            #     break
            prices[b][1] =float(prices[b][1])-float(qty)
            product.prices=json.dumps(prices)
            break
    category=Category.objects.get(pk=request.POST.get('categoryid'))
    t=PurchasedProduct.objects.create(product_id=product.id, quantity=qty, purchase_amount=amount)
    StockOut.objects.create(purchased_item_id=t.id, stock_out_quantity=qty, product_id=product.id)
    product.stock=float(product.stock)-float(qty)
    product.save()
    newstock=product.stock
    if newstock==0:
        originref=product.ref.split(' ')[0]
        simillar = Product.objects.filter(category=category).filter(Q(ref__startswith=originref+' ') | Q(ref=originref))
        sim=any([int(i.stock) for i in simillar])
        if sim:
            simillar.update(disponibleinother=True)
            simillar.update(rcommand=False)
        else:
            simillar.update(disponibleinother=False)
            simillar.update(rcommand=True)
    query = Q()
    if refinput:
        query &= Q(ref__icontains=refinput)
    if carinput:
        query &= Q(car__icontains=carinput)
    if categoryinput:
        query &= Q(category= categoryinput)
    products = request.user.retailer_user.retailer.retailer_product.filter(query)

    return JsonResponse({
        'data': render(request, 'products/product_search.html', {'products': products, 'home':True}).content.decode('utf-8'),
        'zerostock':newstock==0,
    })

#cancel commande
def cancelcommande(request):
    product=Product.objects.get(pk=request.GET.get('id'))
    # originref=product.ref.split(' ')[0]
    # simillar = Product.objects..filter(Q(ref__startswith=originref+' ') | Q(ref=originref))
    product.command=False
    product.supplier=None
    product.commanded=False
    product.save()
    # simillar.update(rcommand=True)
    return JsonResponse({
        'valid':True
    })

def deletemark(request):
    markid=request.POST.get('markid')
    mark = Mark.objects.get(pk=markid)
    if mark.product_mark.exists():
        return JsonResponse({
            'valid':False
        })
    else:
        mark.delete()
        return JsonResponse({
            'valid':True
        })


# marks view
def marks(request):
    userprofile=UserProfile.objects.get(user=request.user)
    if not userprofile.canseelistmarks:
        return render(request, 'products/nopermission.html')
    return render(request, 'products/marks.html', {'title':'les marques', 'marks':Mark.objects.all()})

@csrf_exempt
def addmark(request):
    Mark.objects.create(name=request.POST.get('name'))
    return redirect('product:marks')

# @csrf_exempt
# def addoneproduct(request):
#     userprofile=UserProfile.objects.get(user=request.user)
#     if not userprofile.canaddproduct:
#         return render(request, 'products/nopermission.html')
#     # get data from formData sent from the ajax request
#     # name = request.POST.get('name').strip()
#     mark = request.POST.get('mark')
#     supplier =request.POST.get('originsupp') or None
#     #price = request.POST.get('price')
#     stock=request.POST.get('stock') or 0
#     minstock=request.POST.get('minstock') or 0
#     prachat = request.POST.get('prachat') or 0
#     remise = request.POST.get('remise') or 0
#     priceslist=[]
#     if not supplier == None and not stock == 0:
#         suppliername=Supplier.objects.get(pk=supplier)
#         priceslist=[[f'{suppliername} - stockinitial', date.today().strftime('%d/%m/%Y'), float(prachat), float(stock)]] if prachat != 0 else []
#     car=request.POST.get('car').strip()
#     ref=request.POST.get('ref').strip().lower()
#     category=request.POST.get('pcategory')
#     image = request.FILES.get('image')
#     prnet=round(float(prachat)-(float(prachat)*float(remise)/100), 2) if prachat != 0 else 0
#     product=Product.objects.create(
#         retailer=request.user.retailer_user.retailer,
#         # name=name.strip(),
#         price=0,
#         pr_achat=prachat,
#         category_id=category,
#         stock=stock,
#         remise=remise,
#         minstock=minstock,
#         prnet=prnet,
#         car=car,
#         ref=ref,
#         originsupp_id=supplier,
#         mark_id=mark,
#         image=image,
#         prices=json.dumps(priceslist)
#     )
#     StockIn.objects.create(
#         product=product,
#         quantity=stock,
#         price=prachat
#     )
#     originref=product.ref.split(' ')[0]
#     simillar = Product.objects.filter(category=category).filter(Q(ref__startswith=originref+' ') | Q(ref=originref))
#     sim=any([i.stock for i in simillar])
#     if sim:
#         simillar.update(disponibleinother=True)
#         simillar.update(rcommand=False)
#     else:
#         simillar.update(disponibleinother=False)
#         simillar.update(rcommand=True)
#
#     #return a json response without serialaize error data as product is not json serializable
#     # return JsonResponse({
#     #     'data':{
#     #         'name':product.name,
#     #         'price':product.price,
#     #         'prachat':product.pr_achat,
#     #         'brand':product.brand_name,
#     #         'stock':product.stock,
#     #         'id':product.id
#     #     }
#     # })
#     if request.POST.get('dest')=='receive':
#         return JsonResponse({
#             'success':True
#         })
#     return redirect('product:productslistbycategory')

def addoneproduct(request):
    userprofile=UserProfile.objects.get(user=request.user)
    if not userprofile.canaddproduct:
        return render(request, 'products/nopermission.html')
    # get data from formData sent from the ajax request
    # name = request.POST.get('name').strip()
    mark = request.POST.get('mark')
    supplier =request.POST.get('originsupp') or None
    #price = request.POST.get('price')
    stock=request.POST.get('stock') or 0
    minstock=request.POST.get('minstock') or 0
    prachat = request.POST.get('prachat') or 0
    remise = request.POST.get('remise') or 0
    priceslist=[]
    if not supplier == None and not stock == 0:
        suppliername=Supplier.objects.get(pk=supplier)
        priceslist=[[f'{suppliername} - stockinitial', date.today().strftime('%d/%m/%Y'), float(prachat), float(stock)]] if prachat != 0 else []
    car=request.POST.get('car').strip() or ""
    ref=request.POST.get('ref').strip().lower() or ""
    category=request.POST.get('category')
    image = request.FILES.get('image')
    prnet=round(float(prachat)-(float(prachat)*float(remise)/100), 2) if prachat != 0 else 0
    print(ref, car, supplier, mark, stock, minstock, prachat, remise, category, image)
    product=Product.objects.create(
        retailer=request.user.retailer_user.retailer,
        # name=name.strip(),
        price=0,
        pr_achat=prachat,
        category_id=category,
        stock=stock,
        remise=remise,
        minstock=minstock,
        prnet=prnet,
        car=car,
        ref=ref,
        originsupp_id=supplier,
        mark_id=mark,
        image=image,
        prices=json.dumps(priceslist)
    )
    StockIn.objects.create(
        product=product,
        quantity=stock,
        price=prachat
    )
    originref=product.ref.split(' ')[0]
    simillar = Product.objects.filter(category=category).filter(Q(ref__startswith=originref+' ') | Q(ref=originref))
    sim=any([i.stock for i in simillar])
    if sim:
        simillar.update(disponibleinother=True)
        simillar.update(rcommand=False)
    else:
        simillar.update(disponibleinother=False)
        simillar.update(rcommand=True)

    #return a json response without serialaize error data as product is not json serializable
    # return JsonResponse({
    #     'data':{
    #         'name':product.name,
    #         'price':product.price,
    #         'prachat':product.pr_achat,
    #         'brand':product.brand_name,
    #         'stock':product.stock,
    #         'id':product.id
    #     }
    # })
    return JsonResponse({
    'success':True
    })
    # if request.POST.get('dest')=='receive':
    # return redirect('product:productslistbycategory')


def checkref(request):
    ref=request.GET.get('ref').lower().split()[0]
    categoryid=request.GET.get('categoryid')
    product=Product.objects.filter(category=categoryid).filter(Q(ref__startswith=ref+' ') | Q(ref=ref)).exists()
    print(ref)
    if product:
        return JsonResponse({
            'exist':True,
        })
    else:
        return JsonResponse({
            'exist':False,
        })

@csrf_exempt
def updatecategory(request, id):
    name=request.POST.get('categoryname')
    category=Category.objects.get(pk=id)
    category.name=name
    category.save()
    return redirect('product:productslistbycategory')


def validcommande(request):
    product=Product.objects.get(pk=request.POST.get('itemid'))
    product.commanded=True
    product.save()
    return JsonResponse({
        'valid':True
    })


# new view to update product from the modals
def updateproduct(request, id):
    userprofile=UserProfile.objects.get(user=request.user)
    if not userprofile.caneditproducts:
        return JsonResponse({
            'status': False,
            'error': 'No Permission'
        })
    # get data from formData sent from the ajax request
    try:
        image = request.FILES.get('updateimage')
        ref = request.POST.get('updateref').lower()
        # name = request.POST.get('name')
        car = request.POST.get('updatecar')
        minstock = request.POST.get('updateminstock')
        #price = request.POST.get('updateprice')
        #prachat = request.POST.get('updatepr_achat')
        #remise=request.POST.get('updateremise')
        product=Product.objects.get(pk=id)
        category=Category.objects.get(pk=request.POST.get('updatecategory'))
        exist=Product.objects.filter(category=category, ref=ref).exclude(pk=id).exists()
        if exist:
            return JsonResponse({
                'status':False,
                'error': 'Ref already exist in this Category'
            })
        else:
            mark = Mark.objects.get(pk=request.POST.get('updatemark'))
            print('ref', ref, 'car', car, 'minstock', minstock, 'category', category, 'mark', mark)
            #originsupp =Supplier.objects.get(pk=request.POST.get('updateoriginsupp'))
            #prnet=round(float(prachat)-(float(prachat)*float(remise)/100), 2) if prachat != 0 else 0

            #print('rrr',prnet)
            #product.name=name
            product.ref=ref
            # product.price=price
            product.car=car
            product.minstock=minstock
            product.mark=mark
            product.category=category
            #product.remise=remise
            #product.prnet=prnet
            #product.originsupp=originsupp
            #product.pr_achat=prachat
            if image:
                product.image=image
            product.save()
            # originref=product.ref.split(' ')[0]
            # simillar = Product.objects.filter(category=product.category).filter(Q(ref__startswith=originref+' ') | Q(ref=originref))
            # sim=any([int(i.stock) for i in simillar])
            # if sim:
            #     simillar.update(disponibleinother=True)
            #     simillar.update(rcommand=False)
            # else:
            #     simillar.update(disponibleinother=False)
            #     simillar.update(rcommand=True)
            # #return a json response without serialaize error data as product is not json serializable
            return JsonResponse({
                'status': True,
                'pdctid':id,
                'ref':product.ref,
                'catergory':product.category.name,
                'mark':product.mark.name,
                'car':product.car,
                #'supp':product.originsupp.name,
                'prachat':product.pr_achat,
                'remise':product.remise,
            })
    except:
        return JsonResponse({
            'status': False,
            'error': 'Eror'
        })

# get products based on supplier in commande
def getsupplierproducts(request):
    supplier=Supplier.objects.get(pk=request.POST.get('supplier'))
    products=Product.objects.filter(supplier=supplier)
    return JsonResponse({
        'data':render(request, 'products/setecttagsupply.html',{'products':products, 'len':len(products), 'categories':Category.objects.filter(children__isnull=True)}).content.decode('utf-8'),
        'enteredpdcts':render(request, 'products/enteredpdcts.html', {'products':products}).content.decode('utf-8')
    })
# new view to add stock from modal
def addstock(request, id):
    try:
        stock = float(request.POST.get('stock'))
        product=Product.objects.get(pk=id)
        StockIn.objects.create(
            product=product,
            quantity=stock,
        )
        #return a json response without serialaize error data as product is not json serializable
        return JsonResponse({
            'status': True,
        })
    except Exception as e:
        return JsonResponse({
            'status': False,
            'error': e
        })

def updatecommande(request):
    product=Product.objects.get(pk=request.GET.get('itemid'))
    supplier=Supplier.objects.get(pk=request.GET.get('supplier'))
    product.supplier=supplier
    product.save()
    #return redirect('product:productscommande')
    return JsonResponse({
        'success':True
    })


# this to command a product
def commandproduct(request):
    supplier=Supplier.objects.get(pk=request.POST.get('supplier'))
    qty=float(request.POST.get('qty'))
    product=Product.objects.get(pk=request.POST.get('itemid'))
    #category=Category.objects.get(pk=request.POST.get('categoryid'))
    product.command=True
    product.supplier=supplier
    product.qtycommand=qty
    product.save()
    #originref=product.ref.split(' ')[0]
    #simillar = Product.objects.filter(category=category).filter(Q(ref__startswith=originref+' ') | Q(ref=originref))
    #simillar.update(rcommand=False)
    return JsonResponse({
        'valid':True
    })


# new view for product history
def producthistory(request, id):
    userprofile=UserProfile.objects.get(user=request.user)
    if not userprofile.canviewproduct:
        return render(request, 'products/nopermission.html')
    product=Product.objects.get(pk=id)
    pr=StockIn.objects.filter(product=product).order_by('-dated_order')
    stockout=PurchasedProduct.objects.filter(product=product, invoice__ismanual=False).order_by('-created_at')
    totalin=pr.aggregate(Sum('quantity')).get('quantity__sum')
    totalcost=round(float(totalin)*float(product.pr_achat), 2)
    prices=json.loads(product.prices)
    # print('>>>>>>>>>>', prices)
    ctx={ 'title':'Historique Article', 'stockin':pr, 'product':product,  'totalin':totalin, 'totalcost':totalcost, 'netprofit':0
        # 'prices':json.loads(product.prices)[1:],
        # 'ziped':zip(pr, prices)
    }

    if stockout:
        totalamountout=stockout.aggregate(Sum('purchase_amount')).get('purchase_amount__sum')
        ctx.update({
            'stockout':stockout,
            'totalamountout':round(totalamountout, 2),
            'totalout':stockout.aggregate(Sum('quantity')).get('quantity__sum'),
            'netprofit':round(float(totalamountout)-float(totalcost), 2),
            'rest':float(totalin)-float(stockout.aggregate(Sum('quantity')).get('quantity__sum')),
            # 'percentage':round(float(stockout.aggregate(Sum('quantity')).get('quantity__sum'))*100/float(totalin)),
        })
    else:
        ctx.update({
            'netprofit':-float(totalcost)
        })

    return render(request, 'products/producthistory.html', ctx)

def priceevolution(request):
    id=request.POST.get('id')
    product=Product.objects.get(pk=id)
    invoice_data = [i for i in json.loads(product.prices)]
    labels = [invoice[1] for invoice in invoice_data]
    prices = [float(invoice[2]) for invoice in invoice_data]
    suppliers = [invoice[0] for invoice in invoice_data]

    chart_data = {
        'labels': labels,
        'prices': prices,
        'suppliers': suppliers
    }

    return render(request, 'products/priceevolution.html', {'chart_data': json.dumps(chart_data)})

def reports(request):
    return render(request, 'products/reports.html', {'title':'Rapports'})


def reportnetprofit(request):
    year=this_year if request.POST.get('year')=='0' else request.POST.get('year')
    month=False if request.POST.get('month')=='0' else request.POST.get('month')
    if month:
        totalprofit=round(SalesHistory.objects.filter(
            created_at__year=year, created_at__month=month
            ).aggregate(
            total_revenue=Sum('paid_amount')
        )['total_revenue'] or 0, 2)

        totalcost=round(Product.objects.filter(
            stockin_product__dated_order__year=year, stockin_product__dated_order__month=month
            ).annotate(
                total_items=Sum('stockin_product__quantity')
            ).aggregate(
                total_cost=ExpressionWrapper(Sum(F('pr_achat') * F('total_items'), output_field=DecimalField()), output_field=DecimalField())
            )['total_cost'] or 0, 2)
    else:
        totalprofit=round(SalesHistory.objects.filter(
            created_at__year=year
            ).aggregate(
            total_revenue=Sum('paid_amount')
        )['total_revenue'] or 0, 2)
        totalcost=round(Product.objects.filter(
            stockin_product__dated_order__year=year
            ).annotate(
                total_items=Sum('stockin_product__quantity')
            ).aggregate(
                total_cost=ExpressionWrapper(Sum(F('pr_achat') * F('total_items'), output_field=DecimalField()), output_field=DecimalField())
            )['total_cost'] or 0, 2)




    #for i in products:
        #totalcost+=round(float(i.stock)*float(i.pr_achat), 2)
        # stockout=PurchasedProduct.objects.filter(product=i)
        # if stockout:
        #     for i in stockout:
        #         totalprofit+=i.purchase_amount



    return JsonResponse({
        'totalprofit':totalprofit,
        'totalcost':totalcost,
        'netprofit':round(float(totalprofit)-float(totalcost), 2)
    })


def productsranking(request):
    year=this_year if request.POST.get('year')=='0' else request.POST.get('year')
    month=False if request.POST.get('month')=='0' else request.POST.get('month')
    if month:products = (
    PurchasedProduct.objects.filter(
        created_at__year=year, created_at__month=month
        ).values('product')
    .annotate(
        total_quantity=Sum('quantity'),
        total_purchase_amount=Sum('purchase_amount')
    )
    .order_by('-total_quantity')
    .values('product__ref', 'total_quantity', 'total_purchase_amount')[:10]
    )
    else:
        products = (
    PurchasedProduct.objects.filter(
        created_at__year=year
        ).values('product')
    .annotate(
        total_quantity=Sum('quantity'),
        total_purchase_amount=Sum('purchase_amount')
    )
    .order_by('-total_quantity')
    .values('product__ref', 'product__category__name', 'total_quantity', 'total_purchase_amount')[:10]
    )
    return JsonResponse({
        'data':render(request, 'products/productsranking.html', {'products':products}).content.decode('utf-8')
    })


def downranking(request):
    year=this_year if request.POST.get('year')=='0' else request.POST.get('year')
    month=False if request.POST.get('month')=='0' else request.POST.get('month')
    if month:products = (
    PurchasedProduct.objects.filter(
        created_at__year=year, created_at__month=month
        ).values('product')
    .annotate(
        total_quantity=Sum('quantity'),
        total_purchase_amount=Sum('purchase_amount')
    )
    .order_by('total_quantity')
    .values('product__name', 'total_quantity', 'total_purchase_amount')[:10]
    )

    else:
        products = (
    PurchasedProduct.objects.filter(
        created_at__year=year
        ).values('product')
    .annotate(
        total_quantity=Sum('quantity'),
        total_purchase_amount=Sum('purchase_amount')
    )
    .order_by('total_quantity')
    .values('product__name', 'total_quantity', 'total_purchase_amount')[:10]
    )

    return JsonResponse({
        'data':render(request, 'products/productsranking.html', {'products':products}).content.decode('utf-8')
    })

def relve(request):
    products=request.user.retailer_user.retailer.retailer_product.all()
    return render(request, 'products/relve.html', {'title': 'bilan Stock', 'products':products})


def statsofrelve(request):
    year=this_year if request.POST.get('year')=='0' else request.POST.get('year')
    month=False if request.POST.get('month')=='0' else request.POST.get('month')
    product_data = []
    products=request.user.retailer_user.retailer.retailer_product.all()
    # Loop through each product
    for product in products:
        if month:
        # Get the available and sold items for the product
            totalitems=StockIn.objects.filter(
                product=product, dated_order__year=year, dated_order__month=month
            ).aggregate(Sum('quantity'))['quantity__sum'] or 0
            available_items = product.stock
            sold_items = PurchasedProduct.objects.filter(
                product=product, created_at__year=year, created_at__month=month
            ).aggregate(Sum('quantity'))['quantity__sum'] or 0

            # Calculate the total cost and total profit for the product
            total_cost = round(float(product.pr_achat) * float(totalitems), 2)
            total_profit = PurchasedProduct.objects.filter(
                product=product, created_at__year=year, created_at__month=month
            ).aggregate(Sum('purchase_amount'))['purchase_amount__sum'] or 0

            # Calculate the net profit for the product
            net_profit = round(float(total_profit) - float(total_cost), 2)

            # Add the product data to the list
            product_data.append({
                'id': product.id,
                'name': f'{product.ref} {product.category}',
                'available_items': available_items,
                'sold_items': sold_items,
                'total_profit': total_profit,
                'total_cost': total_cost,
                'net_profit': net_profit,
            })
        else:
            totalitems=StockIn.objects.filter(
                product=product, dated_order__year=year
            ).aggregate(Sum('quantity'))['quantity__sum'] or 0
            available_items = product.stock
            sold_items = PurchasedProduct.objects.filter(
                product=product, created_at__year=year
            ).aggregate(Sum('quantity'))['quantity__sum'] or 0

            # Calculate the total cost and total profit for the product
            total_cost = round(float(product.pr_achat) * float(totalitems), 2)
            total_profit = PurchasedProduct.objects.filter(
                product=product, created_at__year=year
            ).aggregate(Sum('purchase_amount'))['purchase_amount__sum'] or 0

            # Calculate the net profit for the product
            net_profit = round(float(total_profit) - float(total_cost), 2)

            # Add the product data to the list
            product_data.append({
                'id': product.id,
                'name': f'{product.ref} {product.category}',
                'available_items': available_items,
                'sold_items': sold_items,
                'total_profit': total_profit,
                'total_cost': total_cost,
                'net_profit': net_profit,
            })
    sorted_list = sorted(product_data, key=lambda k: k['total_profit'], reverse=True)

    return JsonResponse({
        'data':render(request, 'products/relvestats.html', {"products":sorted_list}).content.decode('utf-8')
    })


def dailystatsstock(request):
    date=request.POST.get('date')
    product_data = []
    products=request.user.retailer_user.retailer.retailer_product.all()
    # Loop through each product
    for product in products:
        # Get the available and sold items for the product
        totalitems=StockIn.objects.filter(
            product=product, dated_order__date=date
        ).aggregate(Sum('quantity'))['quantity__sum'] or 0
        available_items = product.stock
        sold_items = PurchasedProduct.objects.filter(
            product=product, created_at__date=date
        ).aggregate(Sum('quantity'))['quantity__sum'] or 0

        # Calculate the total cost and total profit for the product
        total_cost = round(float(product.pr_achat) * float(totalitems), 2)
        total_profit = PurchasedProduct.objects.filter(
            product=product, created_at__date=date
        ).aggregate(Sum('purchase_amount'))['purchase_amount__sum'] or 0

        # Calculate the net profit for the product
        net_profit = round(float(total_profit) - float(total_cost), 2)

        # Add the product data to the list
        product_data.append({
            'id': product.id,
            'name': f'{product.ref} {product.category}',
            'available_items': available_items,
            'sold_items': sold_items,
            'total_profit': total_profit,
            'total_cost': total_cost,
            'net_profit': net_profit,
        })
    sorted_list = sorted(product_data, key=lambda k: k['total_profit'], reverse=True)

    return JsonResponse({
        'data':render(request, 'products/relvestats.html', {"products":sorted_list}).content.decode('utf-8')
    })

def supply(request):
    userprofile=UserProfile.objects.get(user=request.user)
    if not userprofile.cancreatebonachat:
        return render(request, 'products/nopermission.html')
    cc = Category.objects.filter(children__isnull=True).order_by('name')


    ctx={
        'title':'Recevoir des peoduits',
        'children':cc,
        'suppliers':Supplier.objects.all(),
        'marks':Mark.objects.all()
    }
    return render(request, 'products/supply.html', ctx)

def addproduct(request):
    userprofile=UserProfile.objects.get(user=request.user)
    if not userprofile.canseeproduits:
        return render(request, 'products/nopermission.html')
    cc = Category.objects.filter(children__isnull=True).order_by('name')


    ctx={
        'title':'Ajouter les produits',
        'children':cc,
        'suppliers':Supplier.objects.all(),
        'marks':Mark.objects.all()
    }
    return render(request, 'products/add_product.html', ctx)

def addpaymentssupp(request):
    supplier=Supplier.objects.get(pk=request.POST.get('supplier'))
    mantant=request.POST.get('mantant')
    date=request.POST.get('date')
    mode=request.POST.get('mode')
    echeance=request.POST.get('echeance') or None
    npiece=request.POST.get('npiece') or None
    note=request.POST.get('note') or None
    # get bons reglé
    PaymentSupplier.objects.create(
        supplier=supplier,
        date=date,
        amount=mantant,
        mode=mode,
        npiece=npiece,
        echeance=echeance,
        note=note
    )
    supplier.rest=float(supplier.rest)-float(mantant)
    supplier.save()
    if mode=='espece':
        retailer=Retailer.objects.get(pk=1)
        retailer.caisseexterieur-=float(mantant)
        Outcaisseext.objects.create(amount=mantant, raison=f'Paiement espece fournisseur {supplier.name}')
        retailer.save()
    
    return redirect('product:supplierinfo', id=request.POST.get('supplier'))

def updatebonachat(request, id):
    bon=Itemsbysupplier.objects.get(pk=id)
    bonitems=StockIn.objects.filter(reciept=bon)
    if request.method=="POST":
        nbon=request.POST.get('nbon')
        bondate=request.POST.get('bondate')
        newsupplier=Supplier.objects.get(pk=request.POST.get('supplier'))
        oldsupplier=bon.supplier
        if newsupplier==oldsupplier:

            oldsupplier.total=float(oldsupplier.total)-float(bon.total)+float(request.POST.get('total'))
            oldsupplier.rest=float(oldsupplier.rest)-float(bon.total)+float(request.POST.get('total'))
            oldsupplier.save()
        else:
            oldsupplier.total=float(oldsupplier.total)-float(bon.total)
            oldsupplier.rest=float(oldsupplier.rest)-float(bon.total)
            oldsupplier.save()
            newsupplier.total=float(request.POST.get('total'))+float(newsupplier.total)
            newsupplier.rest=float(request.POST.get('total'))+float(newsupplier.rest)
            newsupplier.save()
        bon.bondate=bondate
        bon.nbon=nbon
        bon.total=request.POST.get('total')
        bon.save()
        items = json.loads(request.POST.get('items'))
        # bon items are the items of this bon before modification
        for i in bonitems:
            product=i.product
            product.stock=float(product.stock)-float(i.quantity)
            product.save()
            i.delete()
        for i in items:

            item=i.get('item_id')
            remise=float(i.get('remise') or 0)
            product = Product.objects.get(pk=item)
            # add supplierprice
            supplierprice=Supplierprice.objects.filter(supplier=newsupplier, product=product).first()
            if supplierprice:
                supplierprice.price=float(i['price'])
                supplierprice.qty=int(i['qty'])
                supplierprice.remise=remise
                supplierprice.save()
            else:
                Supplierprice.objects.create(supplier=newsupplier, product=product, price=float(i['price']), qty=int(i['qty']), remise=remise)
            # if(not float(i['price'])==0):
            # product.pr_achat=float(i['price'])
            prices=json.loads(product.prices)

            prices.append([f'{newsupplier.name} - {nbon}', bondate, float(i['price']), float(i['qty'])])
            # update pondire

            # newnet=round(float(i['price'])-((float(i['price'])*int(i['remise']))/100), 2)
            # print('oldnet, newnet', product.prnet, newnet)
            # totalqtys=int(product.stock)+int(i['qty'])
            # actualtotal=float(product.prnet)*float(product.stock)
            # totalprices=round((float(i['qty'])*newnet)+actualtotal, 2)
            # pondire=round(totalprices/totalqtys, 2)
            #print(f'ttalqtys {totalqtys}, totalprices {totalprices}, pondire {pondire}')
            # assign pondire with 35%
            #product.pondire=round((pondire*100)/65, 2)
            # product.pondire=pondire

            #pondir will be calculated in button pondir
            # qts=0
            # prcs=0
            # for b in prices:
            #     qts+=b[3]
            #     prcs+=b[2]*b[3]
            # pondire=round(prcs/qts, 2)
            # product.pr_achat=pondire
            # prnet=round(pondire-(pondire*float(remise/100)), 2)
            # product.prnet=prnet
            #product.prices=json.dumps(prices)
            product.remise=remise
            # if float(product.pr_achat)!=float(i['price']):
            #     print('not equal')
            #     prices.append([float(i['price']), float(i['qty'])])
            #     product.prices=json.dumps(prices)
            # else:
            #     print('equal')
            #     for i, price in enumerate(prices):
            #         if price[0] == float(i['price']):
            #             # update the second item in the nested list
            #             prices[i][1] =float(prices[i][1])+float(i['qty'])
            #     product.prices=json.dumps(prices)
            # or get the average pr_achat
            #product.pr_achat=round((float(product.pr_achat)+float(i['price']))/2, 2)
            product.command=False
            product.originsupp=newsupplier
            product.supplier=None
            StockIn.objects.create(
                product=product,
                quantity=float(i['qty']),
                # this used to be captering the price for each item entered
                price=float(i['price']),
                total=float(i['total']),
                remise=remise,
                reciept=bon
            )
            product.stock=float(product.stock)+float(i['qty'])
            product.pr_achat=float(i['price']) #here
            prnet=round(float(i['price'])-(float(i['price'])*float(remise/100)), 2)
            product.prnet=prnet
            product.remise=remise
            product.save()
            originref=product.ref.split(' ')[0]
            simillar = Product.objects.filter(category=product.category.id).filter(Q(ref__startswith=originref+' ') | Q(ref=originref))
            simillar.update(disponibleinother=True)
            simillar.update(rcommand=False)
            simillar.update(command=False)
            simillar.update(supplier=None)
            simillar.update(commanded=False)

    ctx={
        'title':'Modifier bon Achat N° '+bon.nbon,
        'bon':bon,
        'items':bonitems
    }
    return render(request, 'products/updatebonacht.html', ctx)


def addsupply(request):
    nbon=request.POST.get('nbon').lower().strip()
    bondate=request.POST.get('bondate')
    items = json.loads(request.POST.get('items'))
    supplier=Supplier.objects.get(pk=request.POST.get('supplier'))
    # check if bon with the same supplier and nbon exist
    exist=Itemsbysupplier.objects.filter(supplier=supplier, nbon=nbon).exists()
    if exist:
        return JsonResponse({
            'success':False,
            'error':'Bon avec ce numero existe deja'
        })
    supplier.total=float(request.POST.get('total'))+float(supplier.total)
    supplier.rest=float(request.POST.get('total'))+float(supplier.rest)
    supplier.save()
    reciept=Itemsbysupplier.objects.create(supplier=supplier, total=float(request.POST.get('total')), nbon=nbon, rest=float(request.POST.get('total')), bondate=bondate)
    with transaction.atomic():
        for i in items:

            item=i.get('item_id')
            remise=float(i.get('remise') or 0)
            product = Product.objects.get(pk=item)
            # if there is alrady stock, calculate cout pondire
            if product.stock > 0:
            # sum of all qty / qty*prices
                newnet=round(float(i['price'])-((float(i['price'])*remise)/100), 2)
                print('oldnet, newnet', product.prnet, newnet)
                totalqtys=int(product.stock)+int(i['qty'])
                actualtotal=float(product.prnet)*float(product.stock)
                totalprices=round((float(i['qty'])*newnet)+actualtotal, 2)
                pondire=round(totalprices/totalqtys, 2)
                #print(f'ttalqtys {totalqtys}, totalprices {totalprices}, pondire {pondire}')
                # assign pondire with 35%
                #product.pondire=round((pondire*100)/65, 2)
                product.pondire=pondire
            # add supplierprice
            supplierprice=Supplierprice.objects.filter(supplier=supplier, product=product).first()
            if supplierprice:
                supplierprice.price=float(i['price'])
                supplierprice.qty=int(i['qty'])
                supplierprice.remise=remise
                supplierprice.save()
            else:
                Supplierprice.objects.create(supplier=supplier, product=product, price=float(i['price']), qty=int(i['qty']), remise=remise)
            # if(not float(i['price'])==0):
            # product.pr_achat=float(i['price'])
            prices=json.loads(product.prices)

            prices.append([f'{supplier.name} - {reciept.nbon}', bondate, float(i['price']), float(i['qty'])])
            # qts=0
            # prcs=0
            # for b in prices:
            #     qts+=b[3]
            #     prcs+=b[2]*b[3]
            # pondire=round(prcs/qts, 2)
            # price achat will be new price
            product.pr_achat=float(i['price'])
            prnet=round(float(i['price'])-(float(i['price'])*float(remise/100)), 2)
            product.prnet=prnet
            product.remise=remise
            product.prices=json.dumps(prices)
            # if float(product.pr_achat)!=float(i['price']):
            #     print('not equal')
            #     prices.append([float(i['price']), float(i['qty'])])
            #     product.prices=json.dumps(prices)
            # else:
            #     print('equal')
            #     for i, price in enumerate(prices):
            #         if price[0] == float(i['price']):
            #             # update the second item in the nested list
            #             prices[i][1] =float(prices[i][1])+float(i['qty'])
            #     product.prices=json.dumps(prices)
            # or get the average pr_achat
            #product.pr_achat=round((float(product.pr_achat)+float(i['price']))/2, 2)
            product.command=False
            product.originsupp=supplier
            product.supplier=None
            StockIn.objects.create(
                product=product,
                quantity=float(i['qty']),
                # this used to be captering the price for each item entered
                price=float(i['price']),
                total=float(i['total']),
                remise=remise,
                reciept=reciept
            )
            product.stock=float(product.stock)+float(i['qty'])
            product.save()
            originref=product.ref.split(' ')[0]
            simillar = Product.objects.filter(category=product.category.id).filter(Q(ref__startswith=originref+' ') | Q(ref=originref))
            simillar.update(disponibleinother=True)
            simillar.update(rcommand=False)
            simillar.update(command=False)
            simillar.update(supplier=None)
            simillar.update(commanded=False)

    return JsonResponse({
        'success': True,
    })

def bonentree(request, id):
    itemsbysupplier = StockIn.objects.filter(reciept_id=id)
    return JsonResponse({
        'data':render(request, 'products/bonentree.html', {
        'items':itemsbysupplier,
        'title':'Details bon entree',
        'bon':Itemsbysupplier.objects.get(id=id),
    }).content.decode('utf-8')
    })

def bonsentrees(request):
    userprofile=UserProfile.objects.get(user=request.user)
    if not userprofile.canseelistbonsachat:
        return render(request, 'products/nopermission.html')
    bb=Itemsbysupplier.objects.all().order_by('-bondate')
    return render(request, 'products/supplierslist.html', {
        'title':'Liste Bons Fournisseurs',
        'bonslist':bb,
        # bons is true to add condition in template to only use one teplate for suppliers list and bons list
        'bons':True
    })

def supplierslist(request):
    userprofile=UserProfile.objects.get(user=request.user)
    if not userprofile.canseesuppliers:
        return render(request, 'products/nopermission.html')
    suppliers=Supplier.objects.all().order_by('name')
    # supplier_data = []
    # for supplier in suppliers:
    #     rest = Itemsbysupplier.objects.filter(supplier=supplier).aggregate(rest=Sum('rest'))['rest'] or 0
    #     supplier_data.append({'id':supplier.id, 'name':supplier.name, 'phone1':supplier.phone1, 'rest':rest})
    # # order suppliers_data descending by rest
    # supplier_data = sorted(supplier_data, key=lambda k: k['rest'], reverse=True)
    return render(request, 'products/supplierslist.html', {
        'title':'Liste Fournisseurs',
        'suppliers':suppliers,
        'totalsold':suppliers.aggregate(rest=Sum('rest'))['rest'] or 0,
    })

def supplierinfo(request, id):
    userprofile=UserProfile.objects.get(user=request.user)
    if not userprofile.canseesupplier:
        return render(request, 'products/nopermission.html')
    supplier=Supplier.objects.get(pk=id)
    payments=PaymentSupplier.objects.filter(supplier=supplier).order_by('-date')
    nbrpayments=payments.count()
    totalpayments=payments.aggregate(total=Sum('amount'))['total'] or 0
    bons=Itemsbysupplier.objects.filter(supplier=supplier).order_by('-bondate')
    avoirs=Avoirsupp.objects.filter(supplier=supplier)
    navoirs=avoirs.count()
    totalavoirs=avoirs.aggregate(total=Sum('total'))['total'] or 0
    nbrbons=bons.count()
    paymentscount=payments.count()
    return render (request, 'products/supplierinfo.html', {
        'title':supplier.name.upper()+' Situation',
        'bons':bons,
        'bons':bons,
        'nbrbons':nbrbons,
        'supplier':supplier,
        'payments':payments,
        'nbrpayments':nbrpayments,
        'totalpayments':totalpayments,
        'paymentscount':paymentscount,
        'avoirs':avoirs,
        'navoirs':navoirs,
        'totalavoirs':totalavoirs

    })

def addpaymentsupplier(request, id):
    amount=request.POST.get('amount')
    details=request.POST.get('details')
    bon=Itemsbysupplier.objects.get(pk=id)
    avances=Avancesbon.objects.filter(bon=bon).aggregate(Sum('avance'))['avance__sum']
    if avances:
        avances=float(avances)+float(amount)
    else:avances=amount
    bon.rest=float(bon.total)-float(avances)
    bon.save()
    Avancesbon.objects.create(
        bon=bon,
        avance=amount,
        details=details,
    )
    #return reverse('product:bonentree', kwargs={'id':bon.id})
    return JsonResponse({
        'rr':'rest'
    })

def addsupplier(request):
    name=request.POST.get('name')
    sold=request.POST.get('sold') or 0
    phone1=request.POST.get('phone1')
    phone2=request.POST.get('phone2') or None
    address=request.POST.get('address') or None
    website=request.POST.get('website') or None
    Supplier.objects.create(name=name,
    phone1=phone1,
    phone2=phone2,
    address=address,
    website=website,
    rest=sold
    )
    if request.POST.get('dest')=='receive':
        return JsonResponse({
            'success':True
        })
    return redirect('product:supplierslist')

def editsupp(request):
    supp=Supplier.objects.get(pk=request.POST.get('pid'))
    supp.name=request.POST.get('pname')
    supp.phone1=request.POST.get('pphone1')
    supp.phone2=request.POST.get('pphone2')
    supp.address=request.POST.get('paddress')
    supp.website=request.POST.get('pwebsite')
    supp.save()
    return redirect('product:supplierslist')

def editclient(request):
    supp=Customer.objects.get(pk=request.POST.get('pid'))
    supp.customer_name=request.POST.get('pname')
    supp.customer_phone=request.POST.get('pphone1')
    supp.address=request.POST.get('paddress')
    supp.ice=request.POST.get('pice')
    supp.save()
    return redirect('ledger:customer_ledger_list')

def dailystats(request):
    date=request.POST.get('date')
    totalprofit=round(SalesHistory.objects.filter(
            created_at__date=date
            ).aggregate(
            total_revenue=Sum('paid_amount')
        )['total_revenue'] or 0, 2)
    totalcost=round(Product.objects.filter(
            stockin_product__dated_order__date=date
            ).annotate(
                total_items=Sum('stockin_product__quantity')
            ).aggregate(
                total_cost=ExpressionWrapper(Sum(F('pr_achat') * F('total_items'), output_field=DecimalField()), output_field=DecimalField())
            )['total_cost'] or 0, 2)
    return JsonResponse({
        'totalprofit':totalprofit,
        'totalcost':totalcost,
        'netprofit':totalprofit-totalcost
    })

def dailyproductsranking(request):
    date=request.POST.get('date')
    products = (
    PurchasedProduct.objects.filter(
        created_at__date=date
        ).values('product')
    .annotate(
        total_quantity=Sum('quantity'),
        total_purchase_amount=Sum('purchase_amount')
    )
    .order_by('-total_quantity')
    .values('product__ref', 'product__category__name', 'total_quantity', 'total_purchase_amount')
    )
    return JsonResponse({
        'data':render(request, 'products/productsranking.html', {'products':products}).content.decode('utf-8')
    })


def dailyproductsrankingdown(request):
    date=request.POST.get('date')
    products = (
    PurchasedProduct.objects.filter(
        created_at__date=date
        ).values('product')
    .annotate(
        total_quantity=Sum('quantity'),
        total_purchase_amount=Sum('purchase_amount')
    )
    .order_by('-total_quantity')
    .values('product__name', 'total_quantity', 'total_purchase_amount')
    )
    return JsonResponse({
        'data':render(request, 'products/productsranking.html', {'products':products}).content.decode('utf-8')
    })







class ProductDetailList(TemplateView):
    template_name = 'products/item_details.html'

    def dispatch(self, request, *args, **kwargs):
        if not self.request.user.is_authenticated:
            return HttpResponseRedirect(reverse('login'))

        return super(
            ProductDetailList, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ProductDetailList, self).get_context_data(**kwargs)
        try:
            product = (
                self.request.user.retailer_user.retailer.
                retailer_product.get(id=self.kwargs.get('pk'))
            )
        except ObjectDoesNotExist:
            raise Http404('Product not found with concerned User')

        context.update({
            'items_details': product.product_detail.all().order_by(
                '-created_at'),
            'product': product,
        })

        return context


class AddNewProduct(FormView):
    form_class = ProductForm
    template_name = 'products/add_product.html'

    def dispatch(self, request, *args, **kwargs):
        if not self.request.user.is_authenticated:
            return HttpResponseRedirect(reverse('login'))
        return super(
            AddNewProduct, self).dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        product = form.save()

        return HttpResponseRedirect(reverse('product:stock_items_list'))

    def form_invalid(self, form):
        return super(AddNewProduct, self).form_invalid(form)


class AddProductItems(FormView):
    template_name = 'products/add_product_items.html'
    form_class = ProductDetailsForm

    def dispatch(self, request, *args, **kwargs):
        if not self.request.user.is_authenticated:
            return HttpResponseRedirect(reverse('login'))
        return super(AddProductItems, self).dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        product_item_detail = form.save()
        return HttpResponseRedirect(
            reverse('product:item_details', kwargs={
                'pk': product_item_detail.product.id
            })
        )

    def form_invalid(self, form):
        return super(AddProductItems, self).form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super(AddProductItems, self).get_context_data(**kwargs)
        try:
            product = (
                self.request.user.retailer_user.retailer.
                retailer_product.get(id=self.kwargs.get('product_id'))
            )
        except ObjectDoesNotExist:
            raise Http404('Product not found with concerned User')

        context.update({
            'product': product
        })
        return context


class PurchasedItems(TemplateView):
    template_name = 'products/purchased_items.html'

    def dispatch(self, request, *args, **kwargs):
        if not self.request.user.is_authenticated:
            return HttpResponseRedirect(reverse('login'))
        return super(PurchasedItems, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(PurchasedItems, self).get_context_data(**kwargs)
        purchased_product = PurchasedProduct.objects.filter(
            product__retailer=self.request.user.retailer_user.retailer
        ).order_by('-created_at')

        context.update({
            'purchased_products': purchased_product
        })

        return context


class ExtraItemsView(TemplateView):
    template_name = 'products/purchased_extraitems.html'

    def dispatch(self, request, *args, **kwargs):
        if not self.request.user.is_authenticated:
            return HttpResponseRedirect(reverse('login'))
        return super(ExtraItemsView, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ExtraItemsView, self).get_context_data(**kwargs)
        extra_products = ExtraItems.objects.filter(
            retailer=self.request.user.retailer_user.retailer
        )

        context.update({
            'purchased_extra_items': extra_products
        })

        return context


class ClaimedProductFormView(FormView):
    template_name = 'products/claimed_product.html'
    form_class = ClaimedProductForm

    def dispatch(self, request, *args, **kwargs):
        if not self.request.user.is_authenticated:
            return HttpResponseRedirect(reverse('login'))
        return super(
            ClaimedProductFormView, self).dispatch(request, *args, **kwargs)

    @staticmethod
    def purchased_items_update(claimed_item, claimed_number):
        product = (
            claimed_item.product.product_detail.filter(
                available_item__gte=claimed_number
            ).first()
        )
        product.purchased_item = (
            product.purchased_item - claimed_number
        )
        product.save()

    # def claimed_items_payment(self, claimed_item, amount):
    #     payment_form_kwargs = {
    #         'customer': claimed_item.customer.id,
    #         'retailer': self.request.user.retailer_user.retailer.id,
    #         'amount': amount,
    #         'description': 'Amount Refunded from Claimed'
    #                        ' Item ID (%s)' % claimed_item.id
    #     }
    #     payment_form = PaymentForm(payment_form_kwargs)
    #     if payment_form.is_valid():
    #         payment_form.save()

    def form_valid(self, form):
        claimed_item = form.save()

        # update the purchased product accordingly
        self.purchased_items_update(
            claimed_item=claimed_item,
            claimed_number=int(form.cleaned_data.get('claimed_items'))
        )

        # Doing a payment of claimed amount
        # self.claimed_items_payment(
        #     claimed_item=claimed_item,
        #     amount=form.cleaned_data.get('claimed_amount')
        # )

        return HttpResponseRedirect(reverse('product:items_list'))

    def form_invalid(self, form):
        return super(ClaimedProductFormView, self).form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super(
            ClaimedProductFormView, self).get_context_data(**kwargs)

        products = (
            self.request.user.retailer_user.retailer.
            retailer_product.all().order_by('name')
        )
        customers = (
            self.request.user.retailer_user.retailer.
            retailer_customer.all().order_by('customer_name')
        )
        context.update({
            'products': products,
            'customers': customers,
        })

        return context


class ClaimedItemsListView(TemplateView):
    pass


class StockItemList(ListView):
    template_name = 'products/stock_list.html'


    def dispatch(self, request, *args, **kwargs):
        if not self.request.user.is_authenticated:
            return HttpResponseRedirect(reverse('login'))

        return super(
            StockItemList, self).dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = self.queryset


    def get_context_data(self, **kwargs):

        context = super(StockItemList, self).get_context_data(**kwargs)
        context.update({
            'search_value_name': self.request.GET.get('name'),
            'title':"Liste des produits",


        })
        return context


class AddStockItems(FormView):
    template_name = 'products/add_stock_item.html'
    form_class = StockDetailsForm

    def dispatch(self, request, *args, **kwargs):
        if not self.request.user.is_authenticated:
            return HttpResponseRedirect(reverse('login'))
        return super(AddStockItems, self).dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        product_item_detail = form.save()
        return HttpResponseRedirect(
             reverse('product:stockin_list', kwargs={'product_id': self.kwargs.get('product_id')})
            # used to reverse to entréé list
            #reverse('index')
        )

    def form_invalid(self, form):
        return super(AddStockItems, self).form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super(AddStockItems, self).get_context_data(**kwargs)
        try:
            product = (
                self.request.user.retailer_user.retailer.
                retailer_product.get(id=self.kwargs.get('product_id'))
            )
        except ObjectDoesNotExist:
            raise Http404('Product not found with concerned User')

        context.update({
            'product': product,
            'title':'Ajouter Entrée'
        })
        return context


class StockOutItems(FormView):
    form_class = StockOutForm
    template_name = 'products/stock_out.html'

    def dispatch(self, request, *args, **kwargs):
        if not self.request.user.is_authenticated:
            return HttpResponseRedirect(reverse('login'))
        return super(StockOutItems, self).dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        product_item_detail = form.save()
        return HttpResponseRedirect(
            reverse('product:stock_items_list')
        )

    def form_invalid(self, form):
        return super(StockOutItems, self).form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super(StockOutItems, self).get_context_data(**kwargs)
        try:
            product = (
                self.request.user.retailer_user.retailer.
                    retailer_product.get(id=self.kwargs.get('product_id'))
            )
        except ObjectDoesNotExist:
            raise Http404('Product not found with concerned User')

        context.update({
            'product': product,
            'title':"Sorties"
        })
        return context


class StockDetailView(TemplateView):
    template_name = 'products/stock_detail.html'

    def get_context_data(self, **kwargs):
        context = super(
            StockDetailView, self).get_context_data(**kwargs)

        try:
            item = Product.objects.get(id=self.kwargs.get('product_id'))
        except StockIn.DoesNotExist:
            return Http404('Item does not exists in database')

        item_stocks_in = item.stockin_product.all()
        item_stocks_out = item.stockout_product.all()

        context.update({
            'item': item,
            'item_stock_in': item_stocks_in.order_by('-dated_order'),
            'item_stock_out': item_stocks_out.order_by('-dated'),
        })

        return context


class StockInListView(ListView):
    template_name = 'products/stockin_list.html'
    paginate_by = 100
    model = StockIn
    ordering = '-id'

    def get_queryset(self):
        queryset = self.queryset
        if not queryset:
            queryset = StockIn.objects.all()

        queryset = queryset.filter(product=self.kwargs.get('product_id'))
        return queryset.order_by('-id')

    def get_context_data(self, **kwargs):
        context = super(StockInListView, self).get_context_data(**kwargs)
        context.update({
            'product': Product.objects.get(id=self.kwargs.get('product_id')),
            'title':'Entrée'
        })
        return context


class StockOutListView(ListView):
    template_name = 'products/stockout_list.html'
    paginate_by = 100
    model = StockOut
    ordering = '-id'

    def get_queryset(self, **kwargs):
        queryset = self.queryset
        if not queryset:
            queryset = StockOut.objects.all()

        queryset = queryset.filter(product=self.kwargs.get('product_id'))
        return queryset.order_by('-id')

    def get_context_data(self, **kwargs):
        context = super(StockOutListView, self).get_context_data(**kwargs)
        context.update({
            'product': Product.objects.get(id=self.kwargs.get('product_id'))
        })
        return context

#this update products
class ProductUpdateView(UpdateView):
    template_name = 'products/update_product.html'
    model = Product
    form_class = ProductForm
    success_url = reverse_lazy('index')


class StockInUpdateView(UpdateView):
    template_name = 'products/update_stockin.html'
    model = StockIn
    form_class = StockDetailsForm

    def form_valid(self, form):
        obj = form.save()
        return HttpResponseRedirect(
            reverse('product:stockin_list',
                    kwargs={'product_id': obj.product.id})
        )

    def form_invalid(self, form):
        return super(StockInUpdateView, self).form_invalid(form)


def deleteproduct(request):
    if request.method == 'POST':
        product_id = request.POST.get('id')
        product = Product.objects.get(id=product_id)
        product.delete()
        return JsonResponse({'status': 'success'})


def searchproduct(request):
    term = request.GET.get('term')
    print(term)
    search_terms = term.split('+')

    # Split the term into individual words separated by '*'

    # Create a list of Q objects for each search term and combine them with &
    q_objects = Q()
    for term in search_terms:
        if term:
            q_objects &= (Q(ref__iregex=term) | Q(car__iregex=term))

    products = Product.objects.filter(q_objects)
    results=[]
    for i in products:
        results.append({
            'id':f'{i.ref}§{i.car}§{i.pr_achat}§{i.stock}§{i.id}§{i.remise}§{i.prnet}',
            'text':f'{i.ref} - {i.car}'
        })
    return JsonResponse({'results': results})


def getclientprice(request):
    clientid=request.GET.get('clientid')
    productid=request.GET.get('productid')
    clientprice=Clientprice.objects.filter(client_id=clientid, product_id=productid).first()
    if clientprice:
        return JsonResponse({
            'price':clientprice.price,
            'qty':clientprice.qty
        })
    else:
        return JsonResponse({
            'price':0
        })
def getsupplierprice(request):
    supplierid=request.GET.get('supplierid')
    productid=request.GET.get('productid')
    try:
        supplierprice=Supplierprice.objects.filter(supplier_id=supplierid, product_id=productid).first()
        return JsonResponse({
            'price':supplierprice.price,
            'qty':supplierprice.qty,
            'remise':supplierprice.remise
        })
    except:
        return JsonResponse({
            'price':0
        })

def searchsupplier(request):
    term=request.GET.get('term')
    print('term', term)
    suppliers=Supplier.objects.filter(Q(name__icontains=term) | Q(phone1__icontains=term))
    print(suppliers)
    results=[]
    for i in suppliers:
        results.append({
            'id':i.id,
            'text':i.name
        })
    return JsonResponse({'results': results})

def sorticontoir(request):
    userprofile=UserProfile.objects.get(user=request.user)
    if not userprofile.cancreatecomptoir:
        return render(request, 'products/nopermission.html')
    ctx={
        'title':'Bon Sortie comptoir',
        'present_date': timezone.now().date(),
        'children':Category.objects.filter(children__isnull=True).order_by('name'),
        'marks':Mark.objects.all()
    }
    return render(request, 'products/sorticontoir.html', ctx)

# view to perform out stock
@csrf_exempt
def sortiecomptoir(request):
    datebon=request.POST.get('datebon')
    datebon=datetime.strptime(datebon, '%Y-%m-%d')
    total=request.POST.get('total')
    items=json.loads(request.POST.get('items'))
    retailer=request.user.retailer_user.retailer
    #create invoice
    invoice=SalesHistory.objects.create(retailer=retailer, grand_total=total, datebon=datebon)
    # add total to caisse
    retailer.caisse=float(retailer.caisse)+float(total)
    retailer.save()
    #create outproducts
    # todo: when contoir, we dont need to reduse qty from stock, it(s already done)
    purchased_items_id = []
    with transaction.atomic():
        for item in items:
            product = Product.objects.get(
                pk=item.get('item_id'),
                retailer=request.user.retailer_user.retailer
            )
            # product.stock=float(product.stock)-float(item.get('qty'))
            # product.save()
            purchased=PurchasedProduct.objects.create(
                product=product,
                quantity=item.get('qty'),
                price=item.get('price'),
                purchase_amount=item.get('total'),
                invoice=invoice


            )
            purchased_items_id.append(purchased.id)
    invoice.purchased_items.set(purchased_items_id)
    return JsonResponse({
        'success':True
    })

def createavoircomptoir(request):
    datebon=request.GET.get('datebon')
    datebon=datetime.strptime(datebon, '%Y-%m-%d')
    total=request.GET.get('total')
    items=json.loads(request.GET.get('items'))
    retailer=request.user.retailer_user.retailer
    #create invoice
    items=json.loads(request.GET.get('items'))
    total=request.GET.get('total')
    avoir=Avoir.objects.create(
        dateavoir=datebon,
        grand_total=total,
        retailer=request.user.retailer_user.retailer,
    )
    # add total to caisse
    retailer.caisse=float(retailer.caisse)-float(total)
    retailer.save()
    #create outproducts
    # todo: when contoir, we dont need to reduse qty from stock, it(s already done)
    returned=[]
    with transaction.atomic():
        for i in items:
            item=i.get('item_id')
            product = Product.objects.get(pk=item)
            # append product.prices
            product.disponibleinother=True
            product.command=False
            product.supplier=None
            StockIn.objects.create(
                product=product,
                quantity=float(i['qty']),
                price=float(i['price']),
                avoir_reciept=avoir,
                status=0
            )
            r=Returned.objects.create(
                product=product,
                qty=float(i['qty']),
                price=float(i['price']),
                avoir=avoir,
                total=float(i['total'])
            )
            returned.append(r.id)
            product.stock=float(product.stock)+float(i['qty'])
            product.save()
            originref=product.ref.split(' ')[0]
            simillar = Product.objects.filter(category=product.category.id).filter(Q(ref__startswith=originref+' ') | Q(ref=originref))
            simillar.update(disponibleinother=True)
            simillar.update(rcommand=False)
            simillar.update(command=False)
            simillar.update(supplier=None)
            simillar.update(commanded=False)
        avoir.returneditems.set(returned)
        avoir.save()
    return JsonResponse({
        'valid':True
    })

def getproductdata(request):
    id=request.GET.get('id')
    product=Product.objects.get(pk=id)
    return JsonResponse({
        'stock':float(product.stock),
        'price':product.pr_achat,
        'prnet':product.prnet
    })

def updatestockcontoir(request):
    productid=request.GET.get('productid')
    qty=float(request.GET.get('qty'))
    increase=request.GET.get('increase', False)
    product=Product.objects.get(pk=productid)
    if increase:
        product.stock=float(product.stock)+qty
    else:
        product.stock=float(product.stock)-qty
    product.save()
    return JsonResponse({
        'success':True
    })

def updatemark(request):
    id=request.GET.get('id')
    name=request.GET.get('name')
    print('>>>>>>', name)
    mark=Mark.objects.get(pk=id)
    mark.name=name
    mark.save()
    return JsonResponse({
        'success':True
    })

def updatestock(request):
    productid=request.GET.get('productid')
    stock=request.GET.get('stock')
    product=Product.objects.get(pk=productid)
    product.stock=stock
    product.save()
    return JsonResponse({
        'success':True
    })
def users(request):
    userprofile=UserProfile.objects.get(user=request.user)
    if not userprofile.canseeusers:
        return render(request, 'products/nopermission.html')
    ctx={
        'users':User.objects.all().exclude(pk=request.user.id),
        'userprofile':UserProfile.objects.get(user=request.user),
        'title':'Utilisateurs'
    }
    return render(request, 'products/users.html', ctx)
def adduser(request):
    password=request.GET.get('password')
    username=request.GET.get('username')
    user=User.objects.filter(username=username).first()
    if user:
        return redirect('product:users')

    user=User.objects.create_user(username=username, password=password)
    RetailerUser.objects.create(user=user, retailer=request.user.retailer_user.retailer)

    return redirect('product:users')

def userinfo(request, id):
    user=User.objects.get(pk=id)
    ctx={
        'user':user,
        'title':user.username,
        'userprofile':UserProfile.objects.get(user=user)
    }
    return render(request, 'products/userinfo.html', ctx)

def updatepermission(request):
    permission=request.GET.get('permission')
    userid=request.GET.get('userid')
    userprofile=UserProfile.objects.get(user_id=userid)
    print('>>>>', permission, getattr(userprofile, permission), userid)

    setattr(userprofile, permission, not getattr(userprofile, permission))
    userprofile.save()
    return JsonResponse({
        'done':True
    })
def zakat(request):
    totalpdcts = round(Product.objects.filter(stock__gt=0).aggregate(
        total_price=ExpressionWrapper(
            Sum(F('stock') * F('prnet')),
            output_field=DecimalField()
        )
    )['total_price'] or 0, 2)
    totalsoldfrs=round(Supplier.objects.aggregate(Sum('rest'))['rest__sum'] or 0, 2)
    totalsoldclient=round(Customer.objects.aggregate(Sum('rest'))['rest__sum'] or 0, 2)
    caisext=Retailer.objects.get(pk=1).caisseexterieur
    ctx={
        'title':'Zakat',
        'totalpdcts':totalpdcts,
        'totalsoldfrs':totalsoldfrs,
        'totalsoldclient':totalsoldclient,
        'caisext':caisext
    }
    return render(request, 'products/zakat.html', ctx)

def gettotalpdtstock(request):
    # pdcts=Product.objects.filter(stock__gt=0)

    print(Product.objects.filter(stock__gt=0).count())
    total = round(Product.objects.filter(stock__gt=0).aggregate(
        total_price=ExpressionWrapper(
            Sum(F('stock') * F('prnet')),
            output_field=DecimalField()
        )
    )['total_price'] or 0, 2)

    return JsonResponse({
        'success': True,
        'total': total
    })

def modifierboncomptoir(request, id):
    bon=SalesHistory.objects.get(pk=id)
    items=PurchasedProduct.objects.filter(invoice=bon)
    retailer=Retailer.objects.get(pk=1)
    if request.method == 'POST':
        print('post update comptoir')
        newitems=json.loads(request.POST.get('items'))
        total=request.POST.get('total')
        retailer.caisse=float(retailer.caisse)-float(bon.grand_total)+float(total)
        retailer.save()

        bon.grand_total=total
        bon.save()

        print(newitems)
        for item in newitems:
            product = Product.objects.get(
                pk=item.get('item_id'),
                retailer=request.user.retailer_user.retailer
            )
            # product.stock=float(product.stock)-float(item.get('qty'))
            # product.save()
            PurchasedProduct.objects.create(
                product=product,
                quantity=item.get('qty'),
                price=item.get('price'),
                purchase_amount=item.get('total'),
                invoice=bon
            )
    ctx={
        'title':'Modifier bon comptoir',
        'bon':bon,
        'items':items
    }
    return render(request, 'products/updatesorticontoir.html', ctx)

def echeances(request):
    echeances=PaymentSupplier.objects.filter(Q(mode="effet")| Q(mode="cheque")).order_by("echeance")
    totalamount=round(echeances.aggregate(Sum('amount'))['amount__sum'] or 0, 2)
    today=date.today()
    tomorrow=today+timedelta(days=1)
    ctx={
        'tomorrow':tomorrow,
        'today':today,
        'title':'Echeances',
        'echeances':echeances,
        'totalamount':totalamount
    }
    return render(request, 'products/echeances.html', ctx)

def makeecheancepaid(request):
    id=request.GET.get('id')
    echeance=PaymentSupplier.objects.get(pk=id)
    # substract amount from bank
    request.user.retailer_user.retailer.bank=float(request.user.retailer_user.retailer.bank)-float(echeance.amount)
    request.user.retailer_user.retailer.save()
    # create an outbank
    Outbank.objects.create(
        amount=echeance.amount,
        raison=f'Paiement effet {echeance.npiece} - {echeance.supplier.name}'
    )
    echeance.ispaid=True
    echeance.save()
    return JsonResponse({
        'success':True
    })

def makeecheancecash(request):
    id=request.GET.get('id')
    echeance=PaymentSupplier.objects.get(pk=id)
    echeance.iscash=True
    echeance.save()
    retailer=Retailer.objects.get(pk=1)
    amount=echeance.amount
    raison=f'payment espece {echeance.mode} {echeance.npiece} - {echeance.supplier.name}'
    retailer.caisseexterieur=float(retailer.caisseexterieur)-float(amount)
    retailer.save()
    Outcaisseext.objects.create(
        amount=amount,
        raison=raison,
    )
    return JsonResponse({
        'success':True
    })

def updatecaisse(request):
    amount=request.GET.get('amount')
    retailer=Retailer.objects.get(pk=1)
    retailer.caisse=float(amount)
    retailer.save()
    return JsonResponse({
        'success':True
    })

def searchclient(request):
    search_terms=request.GET.get('term')

    # Create a list of Q objects for each search term and combine them with &
    q_objects = Q()
    for term in search_terms:
        if term:
            q_objects &= (Q(customer_name__icontains=term) |
                Q(address__icontains=term))
    clients=Customer.objects.filter(q_objects)
    # if '+' in term:
    #     term=term.split('+')
    #     for i in term:
    #         clients=Client.objects.filter(
    #             Q(name__icontains=i) |
    #             Q(code__icontains=i) |
    #             Q(region__icontains=i) |
    #             Q(city__icontains=i)
    #         )
    # else:
    #     clients=Client.objects.filter(
    #         Q(name__icontains=term) |
    #         Q(code__icontains=term) |
    #         Q(region__icontains=term) |
    #         Q(city__icontains=term)
    #     )
    results=[]
    for i in clients:
        results.append({
            'id':i.id,
            'text':f'{i.name} - {i.city}',
            'diver':i.diver
        })
    return JsonResponse({'results': results})

def bank(request):
    outs=Outbank.objects.all()
    outspaymentsuppp=PaymentSupplier.objects.filter(mode="verment")
    ins=Outcaisseext.objects.filter(bank=True)
    insclientpayments=PaymentClient.objects.filter(mode="verment")
    totalout=round(float(outs.aggregate(Sum('amount'))['amount__sum']) or 0, 2)+round(float(outspaymentsuppp.aggregate(Sum('amount'))['amount__sum']) or 0, 2)
    totalin=round(float(ins.aggregate(Sum('amount'))['amount__sum']) or 0, 2)+round(float(insclientpayments.aggregate(Sum('amount'))['amount__sum']) or 0, 2)
    releve = chain(*[
    ((m_out, 'outs') for m_out in outs),
    ((m_outpaysupp, 'outssupp') for m_outpaysupp in outspaymentsuppp),
    ((m_in, 'ins') for m_in in ins),
    ((m_inpaycl, 'inscl') for m_inpaycl in insclientpayments),
    #((inext, 'inext') for inext in infromcaisseexterne),
    ])
    print('sold >>', (request.user.retailer_user.retailer.bank or 0)-2000)
    # Sort the items by date
    releve = sorted(releve, key=lambda item: item[0].date, reverse=True)
    ctx={
        'title':'Gestion compte banquaire',
        "initialbank":request.user.retailer_user.retailer.initialbank or 0,
        "bank":float(totalin)-float(totalout)+float(request.user.retailer_user.retailer.bank or 0),
        # "bank":request.user.retailer_user.retailer.bank or 0,
        "totalbankouts":totalout,
        "totalbankins":totalin,
        "releve":releve
    }
    return render(request, 'products/bank.html', ctx)

def productdata(request):
    id=request.GET.get('id')
    product=Product.objects.get(pk=id)
    return JsonResponse({
        'data':render(request, 'products/productdata.html', {'product':product, 'marks':Mark.objects.all(), 'categories':Category.objects.all().order_by('name'), 'suppliers':Supplier.objects.all()}).content.decode('utf-8')
    })

def deletereglsupp(request):
    reglid=request.GET.get('reglid')
    regl=PaymentSupplier.objects.get(pk=reglid)
    supplier=regl.supplier
    supplier.rest=float(supplier.rest)+float(regl.amount)
    supplier.save()
    regl.delete()
    return JsonResponse({
        'success':True
    })

def addmarkajax(request):
    mark=request.GET.get('mark').lower()
    # check if mark already exists
    exist=Mark.objects.filter(name=mark).first()
    if exist:
        print('>> lark exist')
        return JsonResponse({
            'success':False,
            'error':'Cette marque existe deja'
        })
    mark=Mark.objects.create(name=mark)
    return JsonResponse({
        'success':True,
        'id':mark.id,
    })

def addcategoryajax(request):
    category=request.GET.get('category').lower()
    # check if category already exists
    exist=Category.objects.filter(name=category).first()
    if exist:
        print('>> category exist')
        return JsonResponse({
            'success':False,
            'error':'Cette categorie existe deja'
        })
    category=Category.objects.create(name=category, parent_id=4)
    return JsonResponse({
        'success':True,
        'id':category.id,
    })

def searchclient(request):
    term=request.GET.get('term')
    #regex_search_term = term.replace('+', '*')

    # Split the term into individual words separated by '*'
    search_terms = term.split('+')

    # Create a list of Q objects for each search term and combine them with &
    q_objects = Q()
    for term in search_terms:
        if term:
            q_objects &= (Q(customer_name__icontains=term) |
                Q(address__icontains=term))
    clients=Customer.objects.filter(q_objects)
    # if '+' in term:
    #     term=term.split('+')
    #     for i in term:
    #         clients=Client.objects.filter(
    #             Q(name__icontains=i) |
    #             Q(code__icontains=i) |
    #             Q(region__icontains=i) |
    #             Q(city__icontains=i)
    #         )
    # else:
    #     clients=Client.objects.filter(
    #         Q(name__icontains=term) |
    #         Q(code__icontains=term) |
    #         Q(region__icontains=term) |
    #         Q(city__icontains=term)
    #     )
    results=[]
    for i in clients:
        results.append({
            'id':i.id,
            'text':f'{i.customer_name}',
        })
    return JsonResponse({'results': results})
# set client for the supplier
def setclient(request):
    supplierid=request.GET.get('supplierid')
    clientid=request.GET.get('clientid')
    client=Customer.objects.get(pk=clientid)
    supplier=Supplier.objects.get(pk=supplierid)
    supplier.client_id=clientid
    client.supplier_id=supplierid
    print(client, supplier)
    client.save()
    supplier.save()
    return JsonResponse({
    'success':True
    })
# set supplier for the client
def setsupplier(request):
    supplierid=request.GET.get('supplierid')
    clientid=request.GET.get('clientid')
    client=Customer.objects.get(pk=clientid)
    supplier=Supplier.objects.get(pk=supplierid)
    supplier.client_id=clientid
    client.supplier_id=supplierid
    print(client, supplier)
    client.save()
    supplier.save()
    return JsonResponse({
    'success':True
    })

def getsoldmonth(request):
    year=request.GET.get('year')
    month=request.GET.get('month')
    outs=round(Outcaisse.objects.filter(date__year=year, date__month=month).aggregate(total=Sum('amount'))['total'] or 0, 2)
    comptoir=round(SalesHistory.objects.filter(customer=None, datebon__year=year,datebon__month=month).aggregate(total=Sum('grand_total'))['total'] or 0, 2)
    payments=round(PaymentClient.objects.filter(created_at__year=year, created_at__month=month).exclude(mode='remise').aggregate(total=Sum('amount'))['total'] or 0, 2)
    ins=round(float(comptoir)+float(payments), 2)
    soldmonth=round(float(ins)-float(outs), 2)
    print(soldmonth)
    return JsonResponse({
        'success':True,
        'ins':ins,
        'outs':outs,
        'soldmonth':soldmonth
    })

def getsoldextmonth(request):
    year=request.GET.get('year')
    month=request.GET.get('month')
    outs=round(Outcaisseext.objects.filter(date__year=year, date__month=month).aggregate(total=Sum('amount'))['total'] or 0, 2)
    ins=round(Outcaisse.objects.filter(externe=True, date__year=year, date__month=month).aggregate(total=Sum('amount'))['total'] or 0, 2)
    soldmonth=ins-outs
    return JsonResponse({
        'success':True,
        'ins':ins,
        'outs':outs,
        'soldmonth':soldmonth
    })
def getsupplierlow(request):
    supplierid=request.GET.get('supplierid')
    products=Product.objects.filter(originsupp_id=supplierid, stock__lte=F('minstock')).order_by('category')
    ctx={
        'products':products,
    }
    return JsonResponse({
        'data':render(request, 'products/low_stock.html', ctx).content.decode('utf-8')
    })

def factureprint(request, id):
    order=SalesHistory.objects.get(pk=id)
    orderitems=PurchasedProduct.objects.filter(invoice=order)
    # split the orderitems into chunks of 10 items
    orderitems=list(orderitems)
    orderitems=[orderitems[i:i+33] for i in range(0, len(orderitems), 33)]
    tva=round(float(order.grand_total)-(float(order.grand_total)/1.2), 2)
    ctx={
        'title':f'Facture {order.receipt_no}',
        'facture':order,
        'orderitems':orderitems,
        'tva':tva,
        'ttc':order.grand_total,
        'ht':round(float(order.grand_total)-tva, 2),
    }
    return render(request, 'products/factureprint.html', ctx)

def bonprint(request, id):
    order=SalesHistory.objects.get(pk=id)
    orderitems=PurchasedProduct.objects.filter(invoice=order)
    # split the orderitems into chunks of 10 items
    orderitems=list(orderitems)
    orderitems=[orderitems[i:i+37] for i in range(0, len(orderitems), 37)]
    tva=round(float(order.grand_total)-(float(order.grand_total)/1.2), 2)
    ctx={
        'title':f'bon {order.receipt_no}',
        'facture':order,
        'orderitems':orderitems,
        'tva':tva,
        'ttc':order.grand_total,
        'ht':round(float(order.grand_total)-tva, 2),
    }
    return render(request, 'products/bonprint.html', ctx)

def generate_barcode(request, code):
    print('>>> code', barcode)
    # Ensure the code parameter is valid (for example, non-empty and within allowed characters)
    if not code:
        return HttpResponse("Invalid code", status=400)
    code_class = barcode.get_barcode_class('code128')
    print(code_class)
    # Generate barcodes for the specified quantity

    barcode_instance = code_class(code, writer=ImageWriter())
    # Define custom writer options to remove text (bars only)
    options = {
        'write_text': False,  # Set font size to 0 to hide the code string
    }
    # Create a BytesIO buffer
    buffer = BytesIO()

    # Write the barcode to the buffer
    barcode_instance.write(buffer, options)

    # Create an HttpResponse object with image content type
    response = HttpResponse(buffer.getvalue(), content_type='image/png')
    response['Content-Disposition'] = f'inline; filename="barcode_{code}.png"'

    return response


def printbarcodes(request):
    productid = request.GET.get('productid')
    qty = int(request.GET.get('qty', 1))  # Default to 1 if not provided
    price = request.GET.get('price')

    # Retrieve the product from the database
    product = Product.objects.get(pk=productid)

    # Combine price and barcode, separated by ':' (do not include company name)
    code = str(price) + ':' + product.bar_code
    code_class = barcode.get_barcode_class('code128')
    # List to hold the barcodes in base64 format
    barcodes = []

    # Generate barcodes for the specified quantity
    for _ in range(qty):
        barcode_instance = code_class(code, writer=ImageWriter())
        options = {
            'write_text': False,  # Set font size to 0 to hide the code string
        }
        # Create a BytesIO buffer
        buffer = BytesIO()

        # Write the barcode to the buffer
        barcode_instance.write(buffer, options)

        # Convert the image to base64 and append it to the list
        barcode_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        barcodes.append(barcode_base64)
        buffer.close()

    # Pass the barcodes and quantity to the template for rendering
    return render(request, 'products/barcode.html', {
        'barcodes': barcodes,
        'qty': qty,
        'company_name': 'Your Company Name',  # This is just a placeholder
    })


def facturemanual(request):
    ctx={
    'title':'Facture manual',
    'customers':Customer.objects.all(),
    'present_date': timezone.now().date(),
    }
    return render(request, 'products/facturemanual.html', ctx)
def createfacturemanual(request):
    customer=Customer.objects.get(id=request.POST.get('customer_id'))
    datebon=request.POST.get('datebon')
    # make it datetime object
    datebon=datetime.strptime(datebon, '%Y-%m-%d')
    sub_total = request.POST.get('sub_total')
    discount = request.POST.get('discount')
    shipping = request.POST.get('shipping')
    grand_total = request.POST.get('grand_total')
    totalQty = request.POST.get('totalQty')
    remaining_payment = request.POST.get('remaining_amount')
    paid_amount = request.POST.get('paid_amount')
    cash_payment = request.POST.get('cash_payment')
    returned_cash = request.POST.get('returned_cash')
    items = json.loads(request.POST.get('items'))
    purchased_items_id = []
    extra_items_id = []
    # comptoir
    # deprecated for the moment, we have seperated bon comptoir
    # if customer.id==7:
    #     PaymentClient.objects.create(
    #         client=customer,
    #         amount=float(grand_total),
    #         mode='espece'
    #         )
    with transaction.atomic():

        billing_form_kwargs = {
            'created_at':datebon,
            'datebon':datebon,
            'discount': discount,
            'grand_total': grand_total,
            'total_quantity': totalQty,
            'shipping': shipping,
            'paid_amount': paid_amount,
            'remaining_payment': remaining_payment,
            'cash_payment': cash_payment,
            'returned_payment': returned_cash,
            'retailer': request.user.retailer_user.retailer.id,
        }

        if request.POST.get('customer_id'):
            billing_form_kwargs.update({
                'customer': request.POST.get('customer_id')
            })

        billing_form = BillingForm(billing_form_kwargs)
        invoice = billing_form.save()

        for item in items:
            try:
                product = Product.objects.get(
                    pk=item.get('item_id'),
                    retailer=request.user.retailer_user.retailer
                )
                # add client price:


                #prices=json.loads(product.prices)
            #     for pr in prices:
            # #         print(pr[0], float(prachat))
            # # except:
            # #     pass
            #         if float(pr[2])==float(prachat):
            #             pr[3] =float(pr[3])-float(qty)
            #             product.prices=json.dumps(prices)
            #             break
                form_kwargs = {
                    'product': product.id,
                    'invoice': invoice.id,
                    'quantity': item.get('qty'),
                    'price': item.get('price'),
                    'discount_percentage': item.get('prachat'),
                    'purchase_amount': item.get('total'),
                }
                form = PurchasedProductForm(form_kwargs)
                if form.is_valid():
                    purchased_item = form.save()
                    purchased_items_id.append(purchased_item.id)

                    # latest_stock_in = (
                    #     product.stockin_product.all().latest('id'))

                    stock_out_form_kwargs = {
                        'product': product.id,
                        'invoice': invoice.id,
                        'purchased_item': purchased_item.id,
                        'stock_out_quantity': float(item.get('qty')),
                        'dated': timezone.now().date()
                    }

                    stock_out_form = StockOutForm(stock_out_form_kwargs)
                    if stock_out_form.is_valid():
                        stock_out = stock_out_form.save()
            except Product.DoesNotExist:
                pass


        invoice.purchased_items.set(purchased_items_id)
        invoice.extra_items.set(extra_items_id)
        invoice.ismanual=True
        invoice.save()
        return JsonResponse({
        'success':True
        })

def listfactures(request):
    ctx={
        'title':'List factures',
        'bons':SalesHistory.objects.filter(ismanual=True)
    }

    return render(request, 'products/listfactures.html', ctx)
def barcodescan(request):
    return render(request, 'products/barcodescan.html')

def typeofouts(request):
    type=request.GET.get('type')
    if type=='charges':
        outs=Outcaisse.objects.filter(charge=True)
    else:
        outs=Outcaisse.objects.filter(externe=True)
    # elif type=='externe':
    #     outs=Outcaisse.objects.filter(externe=True)[:30]
    # else:
    #     outs=Outcaisse.objects.all()[:30]
    total=outs.aggregate(Sum('amount')).get('amount__sum') or 0
    return JsonResponse({
        'outs':list(outs.values()),
        'total':total
    })

def typeofoutsbank(request):
    type=request.GET.get('type')
    if type=='intern':
        outs=Outbank.objects.filter(intern=True)
    elif type=='charge':
        outs=Outbank.objects.filter(charge=True)
    
    else:
        outs=Outbank.objects.filter(externe=True)
    # elif type=='externe':
    #     outs=Outcaisse.objects.filter(externe=True)[:30]
    # else:
    #     outs=Outcaisse.objects.all()[:30]
    total=outs.aggregate(Sum('amount')).get('amount__sum') or 0
    return JsonResponse({
        'outs':list(outs.values()),
        'total':total
    })

def typeofoutsexterne(request):
    type=request.GET.get('type')
    if type=='intern':
        outs=Outcaisseext.objects.filter(interne=True)
    elif type=='charge':
        outs=Outcaisseext.objects.filter(charge=True)
    
    else:
        outs=Outcaisseext.objects.filter(bank=True)
    # elif type=='externe':
    #     outs=Outcaisse.objects.filter(externe=True)[:30]
    # else:
    #     outs=Outcaisse.objects.all()[:30]
    total=outs.aggregate(Sum('amount')).get('amount__sum') or 0
    return JsonResponse({
        'outs':list(outs.values()),
        'total':total
    })
