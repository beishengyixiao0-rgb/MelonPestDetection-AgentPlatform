from app.api.analytics import router as analytics_router
from app.api.auth import router as auth_router

print(f"Analytics router prefix: {analytics_router.prefix}")
print(f"Auth router prefix: {auth_router.prefix}")

from main import app
import json

openapi_schema = app.openapi()
for path in sorted(openapi_schema['paths'].keys()):
    if 'analytics' in path:
        print(f"Path in OpenAPI: {path}")