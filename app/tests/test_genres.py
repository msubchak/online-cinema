import pytest
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    MovieModel,
    GenreModel,
    StarModel,
    DirectorModel,
    CertificationModel,
    OrdersModel,
    OrderItemModel
)
from app.models.accounts import (
    UserModel,
    UserGroupModel,
    UserGroupEnum,
)
from app.core.database import engine
from httpx import AsyncClient, ASGITransport

from app.security.password import hash_password
from app.tests.test_accounts import jwt_manager

pytestmark = pytest.mark.asyncio


class TestGenres():
    async def create_genre(self):
        async with AsyncSession(engine) as session:
            genre = GenreModel(name="Test")

            session.add(genre)
            await session.commit()
            await session.refresh(genre)
            return genre.id


class TestGenresGet(TestGenres):
    async def test_get_genres_success(self, test_app):
        await self.create_genre()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/genres/?page=1&per_page=10")

        assert response.status_code == 200
        data = response.json()
        assert "genres" in data

    async def test_get_genres_items_not_found(self, test_app):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/genres/")

        assert response.status_code == 404
        assert response.json() == {
            "detail": "No genres found in the database."
        }

    async def test_get_genres_not_found(self, test_app):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/genres/?page=1&per_page=10")

        assert response.status_code == 404
        assert response.json() == {
            "detail": "No genres found in the database."
        }


class TestGenresGetByID(TestGenres):
    async def test_get_genres_by_id_success(self, test_app):
        genre_id = await self.create_genre()
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/genres/{genre_id}/")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == genre_id

    async def test_get_genres_by_id_not_found(self, test_app):
        genre_id = 9999
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.get(f"/api/v1/genres/{genre_id}/")

        assert response.status_code == 404
        assert "detail" in response.json()


class TestGenresCreate(TestGenres):
    async def test_create_genres_success(self, test_app):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/genres/",
                json={
                    "name": "Test",
                }
            )
        assert response.status_code == 201

    async def test_create_genres_exists_name(self, test_app):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response1 = await client.post(
                "/api/v1/genres/",
                json={
                    "name": "Test",
                }
            )
            assert response1.status_code == 201

            response2 = await client.post(
                "/api/v1/genres/",
                json={
                    "name": "Test",
                }
            )

        assert response2.status_code == 409
        assert "detail" in response2.json()


class TestGenresUpdate(TestGenres):
    async def test_update_genres_success(self, test_app):
        genre_id = await self.create_genre()
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.patch(
                f"/api/v1/genres/{genre_id}/",
                json={
                    "name": "Test1",
                }
            )

        assert response.status_code == 200
        assert "detail" in response.json()

    async def test_update_genres_not_found(self, test_app):
        genre_id = 9999
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.patch(
                f"/api/v1/genres/{genre_id}/",
                json={
                    "name": "Test1",
                }
            )

        assert response.status_code == 404
        assert "detail" in response.json()

    async def test_update_genres_exists_name(self, test_app):
        genre_id = await self.create_genre()

        async with AsyncSession(engine) as session:
            session.add(GenreModel(name="Duplicate"))
            await session.commit()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.patch(
                f"/api/v1/genres/{genre_id}/",
                json={
                    "name": "Duplicate",
                }
            )

        assert response.status_code == 409
        assert "detail" in response.json()


class TestGenresDelete(TestGenres):
    async def test_delete_genres_success(self, test_app):
        genre_id = await self.create_genre()
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.delete(
                f"/api/v1/genres/{genre_id}/",
            )

        assert response.status_code == 204

    async def test_delete_genres_not_found(self, test_app):
        genre_id = 9999
        transport = ASGITransport(app=test_app)
        async with AsyncClient(
                transport=transport,
                base_url="http://test"
        ) as client:
            response = await client.delete(
                f"/api/v1/genres/{genre_id}/",
            )

        assert response.status_code == 404
        assert "detail" in response.json()
