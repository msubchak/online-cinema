import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import StarModel
from app.core.database import engine
from httpx import AsyncClient, ASGITransport


pytestmark = pytest.mark.asyncio


class TestStars():
    async def create_stars(self):
        async with AsyncSession(engine) as session:
            star = StarModel(name="Test")

            session.add(star)
            await session.commit()
            await session.refresh(star)
            return star.id


class TestStarsGet(TestStars):
    async def test_get_stars_success(self, test_app):
        await self.create_stars()

        transport = ASGITransport(test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/stars/?page=1&per_page=10")

        assert response.status_code == 200
        data = response.json()
        assert "stars" in data

    async def test_get_stars_items_not_found(self, test_app):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/stars/")

        assert response.status_code == 404
        assert response.json() == {
            "detail": "No stars found in the database."
        }

    async def test_get_stars_not_found(self, test_app):
        await self.create_stars()
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/v1/stars/?page=5&per_page=30"
            )

        assert response.status_code == 404
        assert "detail" in response.json()


class TestStarsGetById(TestStars):
    async def test_get_stars_by_id_success(self, test_app):
        star_id = await self.create_stars()
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/stars/{star_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == star_id

    async def test_get_stars_by_id_not_found(self, test_app):
        star_id = 9999
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/stars/{star_id}")

        assert response.status_code == 404
        assert "detail" in response.json()


class TestStarsCreate(TestStars):
    async def test_create_stars_success(self, test_app):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/stars/",
                json={"name": "Test"}
            )

        assert response.status_code == 201

    async def test_create_stars_exist_name(self, test_app):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response1 = await client.post(
                "/api/v1/stars/",
                json={"name": "Test"},
            )
            assert response1.status_code == 201

            response2 = await client.post(
                "/api/v1/stars/",
                json={"name": "Test"},
            )

        assert response2.status_code == 409
        assert "detail" in response2.json()


class TestStarsUpdate(TestStars):
    async def test_update_stars_success(self, test_app):
        star_id = await self.create_stars()
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.patch(
                f"/api/v1/stars/{star_id}",
                json={"name": "Test"}
            )

        assert response.status_code == 200
        assert response.json() == {"detail": "Star updated successfully."}

    async def test_update_stars_not_found(self, test_app):
        star_id = 9999
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.patch(
                f"/api/v1/stars/{star_id}",
                json={"name": "Test"}
            )

        assert response.status_code == 404
        assert "detail" in response.json()

    async def test_update_stars_exits_name(self, test_app):
        star_id = await self.create_stars()
        async with AsyncSession(engine) as session:
            session.add(StarModel(name="Duplicate"))
            await session.commit()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.patch(
                f"/api/v1/stars/{star_id}",
                json={"name": "Duplicate"}
            )

        assert response.status_code == 409
        assert "detail" in response.json()


class TestStarsDelete(TestStars):
    async def test_delete_stars_success(self, test_app):
        star_id = await self.create_stars()
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.delete(f"/api/v1/stars/{star_id}")

        assert response.status_code == 204

    async def test_delete_stars_not_found(self, test_app):
        star_id = 9999
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.delete(f"/api/v1/stars/{star_id}")

        assert response.status_code == 404
        assert "detail" in response.json()
