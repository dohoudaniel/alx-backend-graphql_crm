import django
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "alx_backend_graphql_crm.settings")
django.setup()

from crm.models import Customer, Product

def seed():
    customers_data = [
        {"name": "Alice", "email": "alice@example.com", "phone": "+1234567890"},
        {"name": "Bob", "email": "bob@example.com", "phone": "123-456-7890"},
    ]
    products_data = [
        {"name": "Laptop", "price": 999.99, "stock": 10},
        {"name": "Mouse", "price": 19.99, "stock": 50},
    ]

    for c in customers_data:
        Customer.objects.get_or_create(**c)
    for p in products_data:
        Product.objects.get_or_create(**p)

    print("Database seeded successfully.")

if __name__ == "__main__":
    seed()
