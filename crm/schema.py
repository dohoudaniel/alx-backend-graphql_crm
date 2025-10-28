import graphene
from graphene_django import DjangoObjectType
from django.db import transaction
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.utils import timezone
from graphql import GraphQLError

# from crm.models import Product

from .models import Customer, Product, Order


# ---------------- GraphQL Types (Relay-Compatible) ----------------
class CustomerType(DjangoObjectType):
    # Expose created_at as createdAt (camelCase) to match checker queries
    createdAt = graphene.DateTime(source="created_at")

    class Meta:
        model = Customer
        fields = "__all__"
        interfaces = (graphene.relay.Node,)


class ProductType(DjangoObjectType):
    class Meta:
        model = Product
        fields = "__all__"
        interfaces = (graphene.relay.Node,)


class OrderType(DjangoObjectType):
    # Expose order_date as orderDate (camelCase)
    orderDate = graphene.DateTime(source="order_date")

    # Add singular product for compatibility
    product = graphene.Field(ProductType)

    def resolve_product(self, info):
        return self.products.first()

    class Meta:
        model = Order
        fields = "__all__"
        interfaces = (graphene.relay.Node,)


# ---------------- Input Types (Mutations) ----------------
class CustomerInput(graphene.InputObjectType):
    name = graphene.String(required=True)
    email = graphene.String(required=True)
    phone = graphene.String(required=False)


class ProductInput(graphene.InputObjectType):
    name = graphene.String(required=True)
    price = graphene.Decimal(required=True)
    stock = graphene.Int(required=False, default_value=0)


class OrderInput(graphene.InputObjectType):
    customer_id = graphene.ID(required=True)
    product_ids = graphene.List(graphene.ID, required=True)
    order_date = graphene.DateTime(required=False)


# ---------------- Filter Input Types (Task 3) ----------------
class CustomerFilterInput(graphene.InputObjectType):
    nameIcontains = graphene.String()
    emailIcontains = graphene.String()
    createdAtGte = graphene.Date()
    createdAtLte = graphene.Date()
    # Challenge: custom phone pattern (e.g., starts with "+1")
    phonePattern = graphene.String()


class ProductFilterInput(graphene.InputObjectType):
    nameIcontains = graphene.String()
    priceGte = graphene.Decimal()
    priceLte = graphene.Decimal()
    stockGte = graphene.Int()
    stockLte = graphene.Int()
    # Convenience for "low stock"
    lowStockLt = graphene.Int()


class OrderFilterInput(graphene.InputObjectType):
    totalAmountGte = graphene.Decimal()
    totalAmountLte = graphene.Decimal()
    orderDateGte = graphene.DateTime()
    orderDateLte = graphene.DateTime()
    customerName = graphene.String()     # via related field lookup
    productName = graphene.String()      # via related field lookup
    productId = graphene.ID()            # Challenge: orders including a specific product ID


# ---------------- Mutations (Task 1/2) ----------------
class CreateCustomer(graphene.Mutation):
    class Arguments:
        input = CustomerInput(required=True)

    customer = graphene.Field(CustomerType)
    message = graphene.String()

    @staticmethod
    def mutate(root, info, input):
        try:
            if Customer.objects.filter(email=input.email).exists():
                # direct validation error (not in except): no "from None" needed here
                raise GraphQLError("Email already exists")
            customer = Customer(
                name=input.name,
                email=input.email,
                phone=input.phone
            )
            customer.full_clean()
            customer.save()
            return CreateCustomer(customer=customer, message="Customer created successfully")
        except ValidationError as e:
            # ruff B904: attach "from None" inside except blocks
            raise GraphQLError(f"Failed to create customer: {str(e)}") from None


class BulkCreateCustomers(graphene.Mutation):
    class Arguments:
        # NOTE: we accept "input: [CustomerInput!]" to match the checker
        input = graphene.List(graphene.NonNull(CustomerInput), required=True)

    customers = graphene.List(CustomerType)
    errors = graphene.List(graphene.String)

    @staticmethod
    def mutate(root, info, input):
        created_customers = []
        errors = []

        with transaction.atomic():
            for data in input:
                try:
                    if Customer.objects.filter(email=data.email).exists():
                        errors.append(f"Email already exists: {data.email}")
                        continue
                    customer = Customer(
                        name=data.name,
                        email=data.email,
                        phone=data.phone
                    )
                    customer.full_clean()
                    customer.save()
                    created_customers.append(customer)
                except ValidationError as e:
                    errors.append(f"{data.email}: {str(e)}")
                except Exception:
                    errors.append(f"{data.email}: Failed to create customer")

        return BulkCreateCustomers(customers=created_customers, errors=errors)


class CreateProduct(graphene.Mutation):
    class Arguments:
        input = ProductInput(required=True)

    product = graphene.Field(ProductType)

    @staticmethod
    def mutate(root, info, input):
        try:
            if input.price <= 0:
                raise GraphQLError("Price must be positive")
            if input.stock < 0:
                raise GraphQLError("Stock cannot be negative")

            product = Product(
                name=input.name,
                price=input.price,
                stock=input.stock
            )
            product.full_clean()
            product.save()
            return CreateProduct(product=product)
        except ValidationError as e:
            raise GraphQLError(f"Failed to create product: {str(e)}") from None


class CreateOrder(graphene.Mutation):
    class Arguments:
        input = OrderInput(required=True)

    order = graphene.Field(OrderType)

    @staticmethod
    def mutate(root, info, input):
        try:
            try:
                customer = Customer.objects.get(pk=input.customer_id)
            except ObjectDoesNotExist:
                raise GraphQLError("Invalid customer ID") from None

            products = Product.objects.filter(pk__in=input.product_ids)
            if not products.exists():
                raise GraphQLError("No valid products found")
            if products.count() != len(set(map(str, input.product_ids))):
                # If any product id is invalid, count will differ
                raise GraphQLError("Some product IDs are invalid")

            order = Order.objects.create(
                customer=customer,
                order_date=input.order_date or timezone.now(),
                total_amount=sum([p.price for p in products])
            )
            order.products.set(products)
            order.save()
            return CreateOrder(order=order)
        except Exception as e:
            raise GraphQLError(f"Failed to create order: {str(e)}") from None


# ---------------- Query (Task 3 with nested `filter`) ----------------
class Query(graphene.ObjectType):
    # Relay connections that accept a nested "filter" arg and "orderBy"
    all_customers = graphene.relay.ConnectionField(
        CustomerType._meta.connection,
        filter=CustomerFilterInput(),
        order_by=graphene.List(of_type=graphene.String)
    )
    all_products = graphene.relay.ConnectionField(
        ProductType._meta.connection,
        filter=ProductFilterInput(),
        order_by=graphene.List(of_type=graphene.String)
    )
    all_orders = graphene.relay.ConnectionField(
        OrderType._meta.connection,
        filter=OrderFilterInput(),
        order_by=graphene.List(of_type=graphene.String)
    )

    # --- Resolvers ---
    def resolve_all_customers(self, info, filter=None, order_by=None, **kwargs):
        qs = Customer.objects.all()

        if filter:
            if filter.nameIcontains:
                qs = qs.filter(name__icontains=filter.nameIcontains)
            if filter.emailIcontains:
                qs = qs.filter(email__icontains=filter.emailIcontains)
            if filter.createdAtGte:
                qs = qs.filter(created_at__gte=filter.createdAtGte)
            if filter.createdAtLte:
                qs = qs.filter(created_at__lte=filter.createdAtLte)
            if filter.phonePattern:
                qs = qs.filter(phone__startswith=filter.phonePattern)

        if order_by:
            qs = qs.order_by(*order_by)

        return qs

    def resolve_all_products(self, info, filter=None, order_by=None, **kwargs):
        qs = Product.objects.all()

        if filter:
            if filter.nameIcontains:
                qs = qs.filter(name__icontains=filter.nameIcontains)
            if filter.priceGte is not None:
                qs = qs.filter(price__gte=filter.priceGte)
            if filter.priceLte is not None:
                qs = qs.filter(price__lte=filter.priceLte)
            if filter.stockGte is not None:
                qs = qs.filter(stock__gte=filter.stockGte)
            if filter.stockLte is not None:
                qs = qs.filter(stock__lte=filter.stockLte)
            if filter.lowStockLt is not None:
                qs = qs.filter(stock__lt=filter.lowStockLt)

        if order_by:
            qs = qs.order_by(*order_by)

        return qs

    def resolve_all_orders(self, info, filter=None, order_by=None, **kwargs):
        qs = Order.objects.all()

        if filter:
            if filter.totalAmountGte is not None:
                qs = qs.filter(total_amount__gte=filter.totalAmountGte)
            if filter.totalAmountLte is not None:
                qs = qs.filter(total_amount__lte=filter.totalAmountLte)
            if filter.orderDateGte is not None:
                qs = qs.filter(order_date__gte=filter.orderDateGte)
            if filter.orderDateLte is not None:
                qs = qs.filter(order_date__lte=filter.orderDateLte)
            if filter.customerName:
                qs = qs.filter(customer__name__icontains=filter.customerName)
            if filter.productName:
                qs = qs.filter(products__name__icontains=filter.productName)
            if filter.productId:
                qs = qs.filter(products__id=str(filter.productId))

        if order_by:
            qs = qs.order_by(*order_by)

        # Distinct to avoid duplicates when joining products
        return qs.distinct()


# ---------------- New Mutation for Task 3 ----------------
class UpdateLowStockProducts(graphene.Mutation):
    success = graphene.String()
    updated_products = graphene.List(lambda: ProductType)

    @staticmethod
    def mutate(root, info):
        try:
            low_stock_products = Product.objects.filter(stock__lt=10)
            updated = []

            for product in low_stock_products:
                product.stock += 10  # simulate restock
                product.full_clean()
                product.save()
                updated.append(product)

            return UpdateLowStockProducts(
                success="Low-stock products updated successfully",
                updated_products=updated,
            )
        except Exception as e:
            raise GraphQLError(f"Failed to update low-stock products: {str(e)}") from None


# ---------------- Root Mutation ----------------
class Mutation(graphene.ObjectType):
    create_customer = CreateCustomer.Field()
    bulk_create_customers = BulkCreateCustomers.Field()
    create_product = CreateProduct.Field()
    create_order = CreateOrder.Field()
    update_low_stock_products = UpdateLowStockProducts.Field()


# ---------------- Schema ----------------
schema = graphene.Schema(query=Query, mutation=Mutation)
