import asyncio

from sentinelscan_cloud.db.session import get_session_factory
from sentinelscan_cloud.domain.organization import Organization
from sentinelscan_cloud.domain.user import User
from sentinelscan_cloud.domain.enums import RoleEnum
from sentinelscan_cloud.security.password_hashing import hash_password


async def main():
    session_factory = get_session_factory()

    async with session_factory() as session:
        org = Organization(
            name="SentinelScan",
            slug="sentinelscan"
        )

        session.add(org)
        await session.flush()

        admin = User(
            organization_id=org.id,
            email="admin@sentinelscan.local",
            hashed_password=hash_password("Admin@123"),
            display_name="Administrator",
            role=RoleEnum.ADMIN,
            is_active=True,
        )

        session.add(admin)

        await session.commit()

        print()
        print("====================================")
        print("Admin account created successfully!")
        print("Email    : admin@sentinelscan.local")
        print("Password : Admin@123")
        print("====================================")


asyncio.run(main())