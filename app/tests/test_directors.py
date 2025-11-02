import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DirectorModel
from app.core.database import engine
from httpx import AsyncClient, ASGITransport


pytestmark = pytest.mark.asyncio


class TestDirectors():
    async def create_director(self):
        async with AsyncSession(engine) as session:
            director = DirectorModel(name="Test")

            session.add(director)
            await session.commit()
            await session.refresh(director)
            return director.id


class TestDirectorsGet(TestDirectors):
    async def test_get_directors_success(self, test_app):
        await self.create_director()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/v1/directors/?page=1&per_page=10"
            )

        assert response.status_code == 200
        data = response.json()
        assert "directors" in data

    async def test_get_directors_items_not_found(self, test_app):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/directors/")

        assert response.status_code == 404
        assert response.json() == {
            "detail": "No directors found in the database"
        }

    async def test_get_directors_not_found(self, test_app):
        await self.create_director()
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/v1/directors/?page=5&per_page=30"
            )

        assert response.status_code == 404
        assert response.json() == {
            "detail": "Page not found - no directors "
                      "available for the requested page"
        }


class TestDirectorsGetById(TestDirectors):
    async def test_get_director_by_id_success(self, test_app):
        director_id = await self.create_director()
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/directors/{director_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == director_id

    async def test_get_director_by_id_not_found(self, test_app):
        director_id = 9999
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/directors/{director_id}")

        assert response.status_code == 404
        assert "detail" in response.json()


class TestDirectorsCreate(TestDirectors):
    async def test_create_director_success(self, test_app):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/directors/",
                json={
                    "name": "Test",
                }
            )

        assert response.status_code == 201

    async def test_create_director_exists_name(self, test_app):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response1 = await client.post(
                "/api/v1/directors/",
                json={"name": "Test"}
            )
            assert response1.status_code == 201

            response2 = await client.post(
                "/api/v1/directors/",
                json={"name": "Test"}
            )

        assert response2.status_code == 409
        assert "detail" in response2.json()


class TestDirectorsUpdate(TestDirectors):
    async def test_update_director_success(self, test_app):
        director_id = await self.create_director()
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.patch(
                f"/api/v1/directors/{director_id}",
                json={"name": "Test"}
            )

        assert response.status_code == 200

    async def test_update_director_not_found(self, test_app):
        director_id = 9999
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.patch(
                f"/api/v1/directors/{director_id}",
                json={"name": "Test"}
            )

        assert response.status_code == 404
        assert "detail" in response.json()

    async def test_update_director_exists_name(self, test_app):
        director_id = await self.create_director()
        async with AsyncSession(engine) as session:
            session.add(DirectorModel(name="Duplicate"))
            await session.commit()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test"
        ) as client:
            response = await client.patch(
                f"/api/v1/directors/{director_id}",
                json={"name": "Duplicate"}
            )

        assert response.status_code == 409
        assert "detail" in response.json()


class TestDirectorsDelete(TestDirectors):
    async def test_delete_director_success(self, test_app):
        director_id = await self.create_director()
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.delete(f"/api/v1/directors/{director_id}")

        assert response.status_code == 204

    async def test_delete_director_not_found(self, test_app):
        director_id = 9999
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.delete(f"/api/v1/directors/{director_id}")

        assert response.status_code == 404
        assert "detail" in response.json()
