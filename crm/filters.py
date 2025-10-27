# crm/filters.py
import django_filters
from django.db.models import Q
from .models import Customer, Product, Order

class CustomerFilter(django_filters.FilterSet):
    # nameIcontains -> name_icontains in python, Graphene converts to nameIcontains
    name_icontains = django_filters.CharFilter(field_name="name", lookup_expr="icontains")
    email_icontains = django_filters.CharFilter(field_name="email", lookup_expr="icontains")
    created_at_gte = django_filters.DateFilter(field_name="created_at", lookup_expr="gte")
    created_at_lte = django_filters.DateFilter(field_name="created_at", lookup_expr="lte")

    # phone_pattern: method filter to support startswith, contains, etc.
    phone_pattern = django_filters.CharFilter(method="filter_phone_pattern")

    # Optional ordering
    order_by = django_filters.OrderingFilter(
        fields=(
            ("name", "name"),
            ("created_at", "created_at"),
            ("email", "email"),
        )
    )

    class Meta:
        model = Customer
        # fields names are not necessary here because we declared explicit filters
        fields = []

    def filter_phone_pattern(self, queryset, name, value):
        """
        Support patterns like:
        - +1  (starts with +1)
        - 123 (contains 123)
        If value starts with '^' treat as startswith
        """
        if not value:
            return queryset
        # simple convention: if value starts with + or digits, do startswith; else use contains
        if value.startswith("+") or value[0].isdigit():
            return queryset.filter(phone__startswith=value)
        return queryset.filter(phone__icontains=value)


class ProductFilter(django_filters.FilterSet):
    name_icontains = django_filters.CharFilter(field_name="name", lookup_expr="icontains")
    price_gte = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    price_lte = django_filters.NumberFilter(field_name="price", lookup_expr="lte")
    stock_gte = django_filters.NumberFilter(field_name="stock", lookup_expr="gte")
    stock_lte = django_filters.NumberFilter(field_name="stock", lookup_expr="lte")

    # low_stock: custom filter (stock less than provided value)
    low_stock = django_filters.NumberFilter(method="filter_low_stock")

    order_by = django_filters.OrderingFilter(
        fields=(
            ("name", "name"),
            ("price", "price"),
            ("stock", "stock"),
        )
    )

    class Meta:
        model = Product
        fields = []

    def filter_low_stock(self, queryset, name, value):
        try:
            threshold = int(value)
        except (TypeError, ValueError):
            return queryset
        return queryset.filter(stock__lt=threshold)


class OrderFilter(django_filters.FilterSet):
    total_amount_gte = django_filters.NumberFilter(field_name="total_amount", lookup_expr="gte")
    total_amount_lte = django_filters.NumberFilter(field_name="total_amount", lookup_expr="lte")
    order_date_gte = django_filters.DateFilter(field_name="order_date", lookup_expr="gte")
    order_date_lte = django_filters.DateFilter(field_name="order_date", lookup_expr="lte")

    # Filter by related customer name or product name
    customer_name_icontains = django_filters.CharFilter(field_name="customer__name", lookup_expr="icontains")
    product_name_icontains = django_filters.CharFilter(field_name="products__name", lookup_expr="icontains")

    # product_id: filter orders that include a specific product id
    product_id = django_filters.NumberFilter(method="filter_by_product_id")

    order_by = django_filters.OrderingFilter(
        fields=(
            ("order_date", "order_date"),
            ("total_amount", "total_amount"),
        )
    )

    class Meta:
        model = Order
        fields = []

    def filter_by_product_id(self, queryset, name, value):
        # include orders that have product with given id
        if value is None:
            return queryset
        return queryset.filter(products__id=value).distinct()

