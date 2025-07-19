# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.contrib.auth import forms as auth_forms
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth import authenticate
from django.views.generic import TemplateView, RedirectView, UpdateView
from django.views.generic import FormView, ListView
from django.http import HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.db.models import Sum, F, Q
from django.utils import timezone

from pis_com.models import Customer
from pis_com.forms import CustomerForm,FeedBackForm

from pis_retailer.models import RetailerUser
from pis_retailer.forms import RetailerForm, RetailerUserForm
# import render
from django.shortcuts import render, redirect
from pis_product.models import Product, Category, PaymentClient
from pis_sales.models import SalesHistory
import shutil
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# @csrf_exempt
# def makebackup(request):
#     if request.method == 'POST':
#         backup_path =  "C://"
#         shutil.copy2(os.path.join(BASE_DIR, 'db.sqlite3'), backup_path)
#         return JsonResponse({'success': True, 'message': 'Backup created successfully.'})
#     else:
#         return JsonResponse({'success': False, 'error': 'Invalid request method.'})



class LoginView(FormView):
    template_name = 'login.html'
    form_class = auth_forms.AuthenticationForm
    
    def dispatch(self, request, *args, **kwargs):
        if not RetailerUser.objects.exists():
            return redirect('product:initpage')
        if self.request.user.is_authenticated:
            print('login view', not Category.objects.exists())
            if not Category.objects.exists():
                return redirect('product:initpage')
            if (
                self.request.user.retailer_user.role_type ==
                self.request.user.retailer_user.ROLE_TYPE_LEDGER_VIEW
            ):
                return HttpResponseRedirect(
                    reverse('ledger:customer_ledger_list'))

            return HttpResponseRedirect(reverse('index'))

        return super(LoginView, self).dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.get_user()
        print('>> auth user here')
        auth_login(self.request, user)
        if not Category.objects.exists():
            return redirect('product:initpage')
        return HttpResponseRedirect(reverse('index'))
    
    def form_invalid(self, form):
        return super(LoginView, self).form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super(LoginView, self).get_context_data(**kwargs)
        
        return context


class LogoutView(RedirectView):

    def dispatch(self, request, *args, **kwargs):
        auth_logout(self.request)
        return super(LogoutView, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        return HttpResponseRedirect(reverse('login'))




# def HomePageView(request):
#     if RetailerUser.objects.exists():
#         return render(request, 'initpage.html')
#     if not request.user.is_authenticated:
#         return HttpResponseRedirect(reverse('login'))
#     return render(request, 'index.html')
class HomePageView(ListView):
    template_name = 'index.html'
    def dispatch(self, request, *args, **kwargs):
        if not RetailerUser.objects.exists():
            return redirect('product:initpage')
        
        if not self.request.user.is_authenticated:
            return HttpResponseRedirect(reverse('login'))
        print('>>> here')
        if not RetailerUser.objects.exists():
            return redirect('product:initpage')
        if not request.user.retailer_user.retailer.working:
            return render(request, 'products/nopermission.html')
        return super(
            HomePageView, self).dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = self.queryset
        if not queryset:
            queryset = (
                #self.request.user.retailer_user.retailer.objects.all()

                self.request.user.retailer_user.retailer
                    .retailer_product.all()
            )

        return queryset.order_by('name')

    def get_context_data(self, **kwargs):
        context = super(HomePageView, self).get_context_data(**kwargs)
        return context

    # def dispatch(self, request, *args, **kwargs):
    #     a = self.request
    #     print(a)

    #     if not self.request.user.is_authenticated:
    #         return HttpResponseRedirect(reverse('login'))
    #     else:

    #         if self.request.user.retailer_user:
    #             if (
    #                 self.request.user.retailer_user.role_type ==
    #                     self.request.user.retailer_user.ROLE_TYPE_SALESMAN
    #             ):
    #                 return HttpResponseRedirect(reverse('sales:invoice_list'))
    #         if self.request.user.retailer_user:
    #             if (
    #                     self.request.user.retailer_user.role_type ==
    #                     self.request.user.retailer_user.ROLE_TYPE_DATA_ENTRY_USER
    #             ):
    #                 return HttpResponseRedirect(reverse('product:items_list'))

    #     return super(
    #         HomePageView, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(HomePageView, self).get_context_data(**kwargs)

        sales = self.request.user.retailer_user.retailer.retailer_sales.all()
        sales_sum = sales.aggregate(
            total_sales=Sum('grand_total')
        )

        today_sales = SalesHistory.objects.filter(customer=None, datebon__date=timezone.now().date()).aggregate(total_sales=Sum('grand_total'))['total_sales'] or 0
        todayreglementespece=PaymentClient.objects.filter(Q(mode='espece')|Q(iscash=True), date__date=timezone.now().date()).aggregate(totalamount=Sum('amount'))['totalamount'] or 0
        

        context.update({
            'totalproducts':Product.objects.all().count(),
            'totalclients':Customer.objects.all().count(),
            'totalsoldclients':Customer.objects.aggregate(total=Sum('rest'))['total'] or 0,
            'notpaid':SalesHistory.objects.filter(paid_amount__lt=F('grand_total')).count(),
            'sales_count': sales.count(),
            'sales_sum': round(
                today_sales+todayreglementespece, 2
            ),
            
            #'cc':Category.objects.filter(children__isnull=True),
            'title':'Dashboard'
        })

        return context


class CreateCustomer(FormView):
    form_class = CustomerForm
    template_name = 'customer/create_customer.html'

    def dispatch(self, request, *args, **kwargs):
        if not self.request.user.is_authenticated:
            return HttpResponseRedirect(reverse('login'))
        return super(
            CreateCustomer, self).dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.save()
        return HttpResponseRedirect(reverse('customers'))
    
    def form_invalid(self, form):
        return super(CreateCustomer, self).form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super(
            CreateCustomer, self).get_context_data(**kwargs)

        customers = Customer.objects.filter(
            retailer=self.request.user.retailer_user.retailer.id)
        context.update({
            'customers': customers
        })
        return context


class CustomerTemplateView(TemplateView):
    template_name = 'customer/customer_list.html'

    def dispatch(self, request, *args, **kwargs):
        if not self.request.user.is_authenticated:
            return HttpResponseRedirect(reverse('login'))
        return super(
            CustomerTemplateView, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(
            CustomerTemplateView, self).get_context_data(**kwargs)

        customers = (
            self.request.user.retailer_user.retailer.
            retailer_customer.all().order_by('customer_name'))
        context.update({
            'customers': customers
        })
        return context


class CustomerUpdateView(UpdateView):
    form_class = CustomerForm
    template_name = 'customer/update_customer.html'
    model = Customer
    success_url = reverse_lazy('customers')

    def dispatch(self, request, *args, **kwargs):
        if not self.request.user.is_authenticated:
            return HttpResponseRedirect(reverse('login'))
        return super(
            CustomerUpdateView, self).dispatch(request, *args, **kwargs)


class CreateFeedBack(FormView):
    form_class = FeedBackForm
    template_name = 'create_feedback.html'

    def dispatch(self, request, *args, **kwargs):
        if not self.request.user.is_authenticated:
            return HttpResponseRedirect(reverse('login'))
        return super(
            CreateFeedBack, self).dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.save()
        return HttpResponseRedirect(reverse('create_feedback'))

    def form_invalid(self, form):
        return super(CreateFeedBack, self).form_invalid(form)

class ReportsView(TemplateView):
    template_name = 'reports.html'

    def dispatch(self, request, *args, **kwargs):
        if not self.request.user.is_authenticated:
            return HttpResponseRedirect(reverse('login'))
        else:

            if self.request.user.retailer_user:
                if (
                    self.request.user.retailer_user.role_type ==
                        self.request.user.retailer_user.ROLE_TYPE_SALESMAN
                ):
                    return HttpResponseRedirect(reverse('sales:invoice_list'))
            if self.request.user.retailer_user:
                if (
                        self.request.user.retailer_user.role_type ==
                        self.request.user.retailer_user.ROLE_TYPE_DATA_ENTRY_USER
                ):
                    return HttpResponseRedirect(reverse('product:items_list'))

        return super(
            ReportsView, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ReportsView, self).get_context_data(**kwargs)

        sales = self.request.user.retailer_user.retailer.retailer_sales.all()
        sales_sum = sales.aggregate(
            total_sales=Sum('grand_total')
        )

        today_sales = (
            self.request.user.retailer_user.retailer.
            retailer_sales.filter(
                created_at__icontains=timezone.now().date()
            )
        )
        today_sales_sum = today_sales.aggregate(
            total_sales=Sum('grand_total')
        )

        context.update({
            'sales_count': sales.count(),
            'sales_sum': (
                int(sales_sum.get('total_sales')) if
                sales_sum.get('total_sales') else 0
            ),
            'today_sales_count': today_sales.count(),
            'today_sales_sum': (
                int(today_sales_sum.get('total_sales')) if
                today_sales_sum.get('total_sales') else 0
            )
        })

        return context
