from django.urls import re_path


from pis_sales.views import (
    GenerateInvoiceAPIView, ProductItemAPIView, CreateInvoiceView,
    UpdateInvoiceView, InvoiceDetailView, UpdateInvoiceAPIView, InvoicesList,
    ProductDetailsAPIView, facture, bon, deleteinvoice, avoirclient, generateavoir
)

urlpatterns = [
    re_path(r'generateavoir',generateavoir,name='generateavoir'),
    re_path(r'avoirclient',avoirclient,name='avoirclient'),
    re_path(r'^create/invoice/$',CreateInvoiceView.as_view(),name='create_invoice'),
    re_path(r'^update/(?P<id>\d+)/api/$',UpdateInvoiceView.as_view(),name='invoice_update'),
    re_path(r'^product/items/details/$',ProductItemAPIView.as_view(),name='product_item_api'),
    re_path(r'^invoice/list/$',InvoicesList.as_view(),name='invoice_list'),
    re_path(r'^api/generate/invoice/$',GenerateInvoiceAPIView.as_view(),name='generate_invoice_api'),
    re_path(r'^api/update/invoice/$',UpdateInvoiceAPIView.as_view(),name='update_invoice_api'),
    re_path(r'^invoice/(?P<invoice_id>\d+)/detail/$',InvoiceDetailView.as_view(),name='invoice_detail'),
    re_path(r'^api/product/details/$',ProductDetailsAPIView.as_view(),name='product_details_api'),
    re_path(r'^delete/(?P<id>\d+)$',deleteinvoice,name='delete'),
    # re_path(r'^deleteinvoice/(?P<pk>\d+)$',deleteinvoice,name='deleteinvoice'),
    re_path(r'^facture/(?P<pk>\d+)/$',facture, name='facture'),
    re_path(r'^bon/(?P<pk>\d+)/$',bon, name='bon'),
]
