#!/bin/bash

# Path to project root (adjust if needed)
PROJECT_DIR="$(dirname "$(dirname "$(realpath "$0")")")"

# Activate virtual environment if required
# source $PROJECT_DIR/venv/bin/activate

# Run Django command to clean inactive customers
DELETED_COUNT=$(python $PROJECT_DIR/manage.py shell -c "
from crm.models import Customer
from django.utils import timezone
from datetime import timedelta

one_year_ago = timezone.now() - timedelta(days=365)
qs = Customer.objects.filter(orders__isnull=True, created_at__lt=one_year_ago)
count = qs.count()
qs.delete()
print(count)
")

# Log result with timestamp
echo \"\$(date): Deleted \$DELETED_COUNT inactive customers\" >> /tmp/customer_cleanup_log.txt
