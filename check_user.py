import asyncio
from sqlalchemy import select
from database.config import AsyncSessionLocal
from database.models.user import User

async def check():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.username == 'admin'))
        user = result.scalar_one_or_none()
        if user:
            print(f'Username: {user.username}')
            print(f'Email: {user.email}')
        else:
            print('No user found')

asyncio.run(check())
