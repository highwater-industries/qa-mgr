from database.models.user import UserLogin
import json

# Check what fields UserLogin actually has
fields = UserLogin.model_fields
print("UserLogin fields:")
for field_name, field_info in fields.items():
    print(f"  - {field_name}: {field_info.annotation}")

# Verify it's the right one
schema = UserLogin.model_json_schema()
print("\nJSON Schema:")
print(json.dumps(schema, indent=2))
