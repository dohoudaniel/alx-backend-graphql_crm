# alx_backend_graphql_crm/schema.py
import graphene
from crm.schema import Query as CRMQuery, Mutation as CRMMutation

class Query(CRMQuery, graphene.ObjectType):
    # you can add other global query fields here
    pass

class Mutation(CRMMutation, graphene.ObjectType):
    # you can add other global mutations here
    pass

schema = graphene.Schema(query=Query, mutation=Mutation)

