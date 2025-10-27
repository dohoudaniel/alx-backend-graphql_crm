# crm/schema.py
import re
from decimal import Decimal, InvalidOperation
from typing import List

from django.db import transaction
from django.utils import timezone

import graphene
from graphene import Field, List as GQLList, ID, String, Float, Int
from graphene_django import DjangoObjectType

from .models import Customer, Product, Order

# -------------------------
# Graphene Types
# -------------------------
class CustomerType(DjangoObjectType):
    class Meta:
        model = Customer
        fields = ("id", "name", "email", "phone")


class ProductType(DjangoObjectType):
    class Meta:
        model = Product
        fields = ("id", "name", "price", "stock")


class OrderType(DjangoObjectType):
    class Meta:
        model = Order
        fields = ("id", "customer", "products", "total_amount", "order_date")


# -------------------------
# Helpers & Validators
# -------------------------
PHONE_PATTERNS = [
    re.compile(r'^\+\d{7,15}$'),        # +1234567890...
    re.compile(r'^\d{3}-\d{3}-\d{4}$')  # 123-456-7890
]

def is_valid_phone(phone: str) -> bool:
    if phone is None or phone == "":
        return True
    for p in PHONE_PATTERNS:
        if p.match(phone):
            return True
    return False

# -------------------------
# Mutations
# -------------------------

# CreateCustomer
class CreateCustomerInput(graphene.InputObjectType):
    name = graphene.String(required=True)
    email = graphene.String(required=True)
    phone = graphene.String(required=False)

class CreateCustomerPayload(graphene.ObjectType):
    customer = Field(CustomerType)
    success = graphene.Boolean()
    message = graphene.String()
    errors = GQLList(String)

class CreateCustomer(graphene.Mutation):
    class Arguments:
        input = CreateCustomerInput(required=True)

    Output = CreateCustomerPayload

    @classmethod
    def mutate(cls, root, info, input):
        name = (input.name or "").strip()
        email = (input.email or "").strip().lower()
        phone = (input.phone or "").strip() if getattr(input, "phone", None) else None

        errors = []
        if not name:
            errors.append("Name is required.")
        if not email:
            errors.append("Email is required.")
        if phone and not is_valid_phone(phone):
            errors.append("Phone format invalid. Expected +1234567890 or 123-456-7890.")

        if errors:
            return CreateCustomerPayload(customer=None, success=False, message="Validation failed.", errors=errors)

        # Unique email check
        if Customer.objects.filter(email=email).exists():
            return CreateCustomerPayload(customer=None, success=False, message="Email already exists.", errors=["Email already exists."])

        # Create customer
        try:
            customer = Customer.objects.create(name=name, email=email, phone=phone)
            return CreateCustomerPayload(customer=customer, success=True, message="Customer created.", errors=[])
        except Exception as exc:
            return CreateCustomerPayload(customer=None, success=False, message="Error creating customer.", errors=[str(exc)])


# BulkCreateCustomers
class OneCustomerInput(graphene.InputObjectType):
    name = graphene.String(required=True)
    email = graphene.String(required=True)
    phone = graphene.String(required=False)

class BulkCreateCustomersPayload(graphene.ObjectType):
    customers = GQLList(CustomerType)
    errors = GQLList(String)

class BulkCreateCustomers(graphene.Mutation):
    class Arguments:
        input = graphene.List(OneCustomerInput, required=True)

    Output = BulkCreateCustomersPayload

    @classmethod
    def mutate(cls, root, info, input: List[OneCustomerInput]):
        created = []
        errors = []

        # Partial success: attempt each record independently, record errors and continue.
        for idx, rec in enumerate(input, start=1):
            name = (rec.name or "").strip()
            email = (rec.email or "").strip().lower()
            phone = (rec.phone or "").strip() if getattr(rec, "phone", None) else None

            if not name:
                errors.append(f"Record {idx}: name is required.")
                continue
            if not email:
                errors.append(f"Record {idx}: email is required.")
                continue
            if phone and not is_valid_phone(phone):
                errors.append(f"Record {idx} ({email}): invalid phone format.")
                continue
            if Customer.objects.filter(email=email).exists():
                errors.append(f"Record {idx} ({email}): email already exists.")
                continue

            try:
                cust = Customer.objects.create(name=name, email=email, phone=phone)
                created.append(cust)
            except Exception as exc:
                errors.append(f"Record {idx} ({email}): unexpected error: {str(exc)}")
                continue

        return BulkCreateCustomersPayload(customers=created, errors=errors)


# CreateProduct
class CreateProductInput(graphene.InputObjectType):
    name = graphene.String(required=True)
    price = graphene.Float(required=True)  # graphene doesn't have Decimal input; we'll convert
    stock = graphene.Int(required=False, default_value=0)

class CreateProductPayload(graphene.ObjectType):
    product = Field(ProductType)
    success = graphene.Boolean()
    message = graphene.String()
    errors = GQLList(String)

class CreateProduct(graphene.Mutation):
    class Arguments:
        input = CreateProductInput(required=True)

    Output = CreateProductPayload

    @classmethod
    def mutate(cls, root, info, input):
        name = (input.name or "").strip()
        stock = input.stock if input.stock is not None else 0

        # Validate price and stock
        try:
            price = Decimal(str(input.price))
        except (InvalidOperation, TypeError, ValueError):
            return CreateProductPayload(product=None, success=False, message="Invalid price.", errors=["Price must be a number."])

        if price <= 0:
            return CreateProductPayload(product=None, success=False, message="Price must be positive.", errors=["Price must be positive."])
        if stock < 0:
            return CreateProductPayload(product=None, success=False, message="Stock cannot be negative.", errors=["Stock cannot be negative."])

        try:
            product = Product.objects.create(name=name, price=price, stock=stock)
            return CreateProductPayload(product=product, success=True, message="Product created.", errors=[])
        except Exception as exc:
            return CreateProductPayload(product=None, success=False, message="Error creating product.", errors=[str(exc)])


# CreateOrder
class CreateOrderInput(graphene.InputObjectType):
    customer_id = ID(required=True)
    product_ids = graphene.List(ID, required=True)
    order_date = graphene.String(required=False)  # optional ISO datetime as string

class CreateOrderPayload(graphene.ObjectType):
    order = Field(OrderType)
    success = graphene.Boolean()
    message = graphene.String()
    errors = GQLList(String)

class CreateOrder(graphene.Mutation):
    class Arguments:
        input = CreateOrderInput(required=True)

    Output = CreateOrderPayload

    @classmethod
    def mutate(cls, root, info, input):
        errors = []
        # Validate customer
        try:
            customer = Customer.objects.get(pk=input.customer_id)
        except (Customer.DoesNotExist, ValueError):
            return CreateOrderPayload(order=None, success=False, message="Invalid customer ID.", errors=["Invalid customer ID."])

        product_ids = input.product_ids or []
        if not product_ids:
            return CreateOrderPayload(order=None, success=False, message="At least one product must be provided.", errors=["At least one product must be provided."])

        products = []
        invalid_ids = []
        for pid in product_ids:
            try:
                p = Product.objects.get(pk=pid)
                products.append(p)
            except (Product.DoesNotExist, ValueError):
                invalid_ids.append(str(pid))

        if invalid_ids:
            return CreateOrderPayload(order=None, success=False, message="Invalid product IDs provided.", errors=[f"Invalid product IDs: {', '.join(invalid_ids)}"])

        # Create order inside a transaction to ensure consistency
        try:
            with transaction.atomic():
                order_date = None
                if getattr(input, "order_date", None):
                    try:
                        order_date = timezone.datetime.fromisoformat(input.order_date)
                    except Exception:
                        order_date = None
                order = Order.objects.create(customer=customer, order_date=order_date or timezone.now())

                # attach products
                order.products.set(products)

                # Ensure total_amount calculated as sum of product prices
                total = Decimal("0.00")
                for p in products:
                    total += p.price

                # Save total_amount with appropriate precision
                order.total_amount = total
                order.save(update_fields=["total_amount"])

        except Exception as exc:
            return CreateOrderPayload(order=None, success=False, message="Error creating order.", errors=[str(exc)])

        return CreateOrderPayload(order=order, success=True, message="Order created.", errors=[])


# -------------------------
# Mutation registration
# -------------------------
class Mutation(graphene.ObjectType):
    create_customer = CreateCustomer.Field()
    bulk_create_customers = BulkCreateCustomers.Field()
    create_product = CreateProduct.Field()
    create_order = CreateOrder.Field()


# -------------------------
# Query registration
# -------------------------
class Query(graphene.ObjectType):
    # Provide a simple query to list customers (useful for testing)
    all_customers = graphene.List(CustomerType)
    all_products = graphene.List(ProductType)
    all_orders = graphene.List(OrderType)

    def resolve_all_customers(root, info, **kwargs):
        return Customer.objects.all()

    def resolve_all_products(root, info, **kwargs):
        return Product.objects.all()

    def resolve_all_orders(root, info, **kwargs):
        # optimize with prefetch_related
        return Order.objects.select_related("customer").prefetch_related("products").all()

