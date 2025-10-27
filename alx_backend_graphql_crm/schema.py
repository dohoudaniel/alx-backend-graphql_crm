import graphene
from crm.schema import Query as CRMQuery, Mutation as CRMMutation

class Query(CRMQuery, graphene.ObjectType):
    # additional global query fields can go here
    pass

class Mutation(CRMMutation, graphene.ObjectType):
    # additional global mutations can go here
    pass

schema = graphene.Schema(query=Query, mutation=Mutation)

