"""Test tenant user assignment."""
import asyncio
import httpx
from database.config import AsyncSessionLocal
from database.models.user import User
from sqlalchemy import select
import bcrypt

async def create_test_user():
    """Create test user if doesn't exist."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.username == 'testuser')
        )
        existing = result.scalar_one_or_none()
        if existing:
            print(f"Test user exists: {existing.id}")
            return str(existing.id)
        
        user = User(
            username='testuser',
            email='test@example.com',
            hashed_password=bcrypt.hashpw(b'password123', bcrypt.gensalt()).decode('utf-8'),
            full_name='Test User',
            is_active=True,
            is_superuser=False,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        print(f"Created test user: {user.id}")
        return str(user.id)

async def main():
    # Create test user
    test_user_id = await create_test_user()
    
    # Admin login
    login = httpx.post('http://127.0.0.1:8008/api/v1/auth/login',
                       json={'username': 'admin', 'password': 'admin123'})
    token = login.json()['access_token']
    
    # Get tenant
    tenants = httpx.get('http://127.0.0.1:8008/api/v1/tenants',
                        headers={'Authorization': f'Bearer {token}'})
    tenant_id = tenants.json()[0]['id']
    print(f"Tenant: {tenants.json()[0]['name']}")
    
    # Assign user to tenant
    assign = httpx.post(
        f'http://127.0.0.1:8008/api/v1/tenants/{tenant_id}/users',
        headers={'Authorization': f'Bearer {token}'},
        json={'user_id': test_user_id, 'role': 'member'}
    )
    print(f"Assignment: {assign.status_code}")
    if assign.status_code != 204:
        print(f"Error: {assign.text}")
        return
    
    # Login as test user
    test_login = httpx.post('http://127.0.0.1:8008/api/v1/auth/login',
                            json={'username': 'testuser', 'password': 'password123'})
    test_token = test_login.json()['access_token']
    
    # Verify test user can see tenant
    test_tenants = httpx.get('http://127.0.0.1:8008/api/v1/tenants',
                             headers={'Authorization': f'Bearer {test_token}'})
    print(f"Test user sees {len(test_tenants.json())} tenant(s)")
    if test_tenants.json():
        print(f"✓ Success! Test user can access: {test_tenants.json()[0]['name']}")
    else:
        print("✗ Failed - test user cannot see tenant")

if __name__ == "__main__":
    asyncio.run(main())


