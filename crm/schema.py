# crm/schema.py
import graphene
from graphene_django import DjangoObjectType
from graphene_django.filter import DjangoFilterConnectionField
from graphene import relay

from .models import Customer, Product, Order
from .filters import CustomerFilter, ProductFilter, OrderFilter

# Relay nodes with filterset_class set
class CustomerNode(DjangoObjectType):
    class Meta:
        model = Customer
        interfaces = (relay.Node,)
        filterset_class = CustomerFilter
        fields = ("id", "name", "email", "phone", "created_at")


class ProductNode(DjangoObjectType):
    class Meta:
        model = Product
        interfaces = (relay.Node,)
        filterset_class = ProductFilter
        fields = ("id", "name", "price", "stock")


class OrderNode(DjangoObjectType):
    class Meta:
        model = Order
        interfaces = (relay.Node,)
        filterset_class = OrderFilter
        # include nested relations
        fields = ("id", "customer", "products", "total_amount", "order_date")


class Query(graphene.ObjectType):
    # Expose Relay connection fields that support filtering
    all_customers = DjangoFilterConnectionField(CustomerNode)  # accepts filter: { nameIcontains, emailIcontains, ... }
    all_products = DjangoFilterConnectionField(ProductNode)    # accepts filter: { priceGte, priceLte, ... } and orderBy
    all_orders = DjangoFilterConnectionField(OrderNode)        # accepts filter including customerName/productName/productId

    # You can still add simple resolvers for non-filtered lists if needed
    customer = relay.Node.Field(CustomerNode)
    product = relay.Node.Field(ProductNode)
    order = relay.Node.Field(OrderNode)

# ------- ensure `Mutation` exists so project-level imports don't fail -------

# If you already declared a Mutation class above, this will leave it alone.
# If not, this defines a minimal placeholder so imports like
# `from crm.schema import Mutation` succeed.
try:
    Mutation  # reference the name to see if it exists
except NameError:
    class Mutation(graphene.ObjectType):
        """Placeholder Mutation class so other modules can import Mutation."""
        pass
