import re
from decimal import Decimal
from django.db import transaction
import graphene
from graphene import Field, List, String, Int, Float, ID
from graphene_django import DjangoObjectType
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from .models import Customer, Product, Order

# ---------------------
# Graphene types
# ---------------------
class CustomerType(DjangoObjectType):
    class Meta:
        model = Customer
        fields = ("id", "name", "email", "phone", "created_at")


class ProductType(DjangoObjectType):
    class Meta:
        model = Product
        fields = ("id", "name", "price", "stock", "created_at")


class OrderType(DjangoObjectType):
    class Meta:
        model = Order
        fields = ("id", "customer", "products", "order_date", "total_amount", "created_at")


# ---------------------
# Helpers & validators
# ---------------------
PHONE_REGEXES = [
    re.compile(r'^\+\d{7,15}$'),          # +1234567890...
    re.compile(r'^\d{3}-\d{3}-\d{4}$'),   # 123-456-7890
]

def validate_phone(phone: str) -> bool:
    if phone is None or phone == "":
        return True
    for rx in PHONE_REGEXES:
        if rx.match(phone):
            return True
    return False

# ---------------------
# Mutations
# ---------------------

# 1) CreateCustomer
class CreateCustomerInput(graphene.InputObjectType):
    name = graphene.String(required=True)
    email = graphene.String(required=True)
    phone = graphene.String(required=False)


class CreateCustomerPayload(graphene.ObjectType):
    customer = Field(CustomerType)
    success = graphene.Boolean()
    message = graphene.String()


class CreateCustomer(graphene.Mutation):
    class Arguments:
        input = CreateCustomerInput(required=True)

    Output = CreateCustomerPayload

    @classmethod
    def mutate(cls, root, info, input):
        name = input.name.strip()
        email = input.email.strip().lower()
        phone = input.phone.strip() if input.phone else None

        # Validate phone
        if not validate_phone(phone):
            return CreateCustomerPayload(
                customer=None,
                success=False,
                message="Invalid phone format. Use +1234567890 or 123-456-7890."
            )

        # Ensure unique email
        if Customer.objects.filter(email=email).exists():
            return CreateCustomerPayload(
                customer=None,
                success=False,
                message="Email already exists."
            )

        customer = Customer.objects.create(name=name, email=email, phone=phone)
        return CreateCustomerPayload(customer=customer, success=True, message="Customer created.")


# 2) BulkCreateCustomers
class OneCustomerInput(graphene.InputObjectType):
    name = graphene.String(required=True)
    email = graphene.String(required=True)
    phone = graphene.String(required=False)


class BulkCreateCustomersPayload(graphene.ObjectType):
    customers = List(CustomerType)
    errors = List(String)


class BulkCreateCustomers(graphene.Mutation):
    class Arguments:
        input = List(OneCustomerInput, required=True)

    Output = BulkCreateCustomersPayload

    @classmethod
    def mutate(cls, root, info, input):
        created = []
        errors = []

        # We attempt to create each customer independently so partial success is possible.
        # If you want single-transaction behavior (all-or-nothing), wrap in transaction.atomic()
        for idx, c in enumerate(input, start=1):
            name = c.name.strip()
            email = c.email.strip().lower()
            phone = c.phone.strip() if getattr(c, "phone", None) else None

            # Basic validations
            if not name:
                errors.append(f"Record {idx}: name is required.")
                continue
            if not email:
                errors.append(f"Record {idx}: email is required.")
                continue
            if not validate_phone(phone):
                errors.append(f"Record {idx}: invalid phone format for email {email}.")
                continue
            if Customer.objects.filter(email=email).exists():
                errors.append(f"Record {idx}: email {email} already exists.")
                continue

            # Create the customer
            try:
                cust = Customer.objects.create(name=name, email=email, phone=phone)
                created.append(cust)
            except Exception as exc:
                errors.append(f"Record {idx}: unexpected error creating {email}: {str(exc)}")
                continue

        return BulkCreateCustomersPayload(customers=created, errors=errors)


# 3) CreateProduct
class CreateProductInput(graphene.InputObjectType):
    name = graphene.String(required=True)
    price = graphene.Float(required=True)
    stock = graphene.Int(required=False, default_value=0)


class CreateProductPayload(graphene.ObjectType):
    product = Field(ProductType)
    success = graphene.Boolean()
    message = graphene.String()


class CreateProduct(graphene.Mutation):
    class Arguments:
        input = CreateProductInput(required=True)

    Output = CreateProductPayload

    @classmethod
    def mutate(cls, root, info, input):
        name = input.name.strip()
        price = Decimal(str(input.price))
        stock = input.stock if input.stock is not None else 0

        if price <= 0:
            return CreateProductPayload(product=None, success=False, message="Price must be positive.")
        if stock < 0:
            return CreateProductPayload(product=None, success=False, message="Stock cannot be negative.")

        product = Product.objects.create(name=name, price=price, stock=stock)
        return CreateProductPayload(product=product, success=True, message="Product created.")


# 4) CreateOrder
class CreateOrderInput(graphene.InputObjectType):
    customer_id = ID(required=True)
    product_ids = List(ID, required=True)
    order_date = graphene.String(required=False)  # optional ISO string (we'll parse if provided)


class CreateOrderPayload(graphene.ObjectType):
    order = Field(OrderType)
    success = graphene.Boolean()
    message = graphene.String()
    errors = List(String)


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

        # Validate product IDs and collect products
        product_ids = input.product_ids or []
        if not product_ids:
            return CreateOrderPayload(order=None, success=False, message="At least one product must be selected.", errors=["At least one product is required."])

        products = []
        for pid in product_ids:
            try:
                p = Product.objects.get(pk=pid)
                products.append(p)
            except (Product.DoesNotExist, ValueError):
                errors.append(f"Invalid product ID: {pid}")

        if errors:
            return CreateOrderPayload(order=None, success=False, message="One or more product IDs are invalid.", errors=errors)

        # All validations passed. Create the Order and associate products.
        try:
            with transaction.atomic():
                order = Order.objects.create(customer=customer)
                # add products and compute total
                order.products.set(products)
                # calculate total_amount as sum of product.price
                total = Decimal('0.00')
                for p in products:
                    total += p.price
                order.total_amount = total
                order.save()
        except Exception as exc:
            return CreateOrderPayload(order=None, success=False, message=f"Error creating order: {str(exc)}", errors=[str(exc)])

        return CreateOrderPayload(order=order, success=True, message="Order created.", errors=[])


# ---------------------
# Mutation registration
# ---------------------
class Mutation(graphene.ObjectType):
    create_customer = CreateCustomer.Field()
    bulk_create_customers = BulkCreateCustomers.Field()
    create_product = CreateProduct.Field()
    create_order = CreateOrder.Field()


# Expose Query placeholders (if CRM app later adds Query fields)
class Query(graphene.ObjectType):
    # You can add query fields here for customers/products/orders (optional)
    customers = List(CustomerType)
    products = List(ProductType)
    orders = List(OrderType)

    def resolve_customers(root, info):
        return Customer.objects.all()

    def resolve_products(root, info):
        return Product.objects.all()

    def resolve_orders(root, info):
        return Order.objects.select_related("customer").prefetch_related("products").all()

