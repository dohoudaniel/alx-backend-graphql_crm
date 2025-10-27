# crm/schema.py
import graphene
from graphene_django import DjangoObjectType
from .models import Customer

class CustomerType(DjangoObjectType):
    class Meta:
        model = Customer
        fields = ("id", "name", "email", "phone")


class Query(graphene.ObjectType):
    # exact form expected by checks
    all_customers = graphene.List(CustomerType)

    def resolve_all_customers(root, info, **kwargs):
        return Customer.objects.all()


# Provide an (empty) Mutation class so other modules can import Mutation from crm.schema
class Mutation(graphene.ObjectType):
    # you can later add create/update/delete mutations here
    pass

