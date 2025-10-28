import pytest
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MovieModel, GenreModel, StarModel, DirectorModel, CertificationModel, OrdersModel, OrderItemModel
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


class TestMovies():
    async def create_moderator_token(self):
        async with engine.begin() as conn:
            await conn.execute(insert(UserGroupModel).values(name=UserGroupEnum.MODERATOR))
            result = await conn.execute(
                insert(UserModel).values(
                    email="moder@example.com",
                    hashed_password=hash_password("Password123!"),
                    is_active=True,
                    group_id=2
                ).returning(UserModel.id)
            )
            moder_id = result.scalar_one()
            await conn.commit()

        jwt_access_token = jwt_manager.create_access_token(
            {
                "user_id": moder_id
            }
        )
        return {"Authorization": f"Bearer {jwt_access_token}"}

    async def create_movie(self):
        async with AsyncSession(engine) as session:
            genre = GenreModel(name="Drama")
            star = StarModel(name="Actor")
            director = DirectorModel(name="Director")
            certification = CertificationModel(name="PG-13")

            movie = MovieModel(
                name="Test1 Film",
                year=2024,
                time=120,
                imdb=7.5,
                votes=1000,
                meta_score=70.0,
                gross=1000000.0,
                description="Example movie",
                price=10.5,
                certification=certification,
                genres=[genre],
                stars=[star],
                directors=[director],
            )

            session.add(movie)
            await session.flush()
            await session.commit()
            await session.refresh(movie)
            return movie.id


class TestMovieGet(TestMovies):
    async def test_get_movie_success(self, test_app):
        headers = await self.create_moderator_token()
        await self.create_movie()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/movies/?page=1&per_page=10", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert "movies" in data

    async def test_get_movie_invalid_sort(self, test_app):
        headers = await self.create_moderator_token()
        await self.create_movie()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/movies/?sort_by=fake", headers=headers)

        assert response.status_code == 422
        assert "detail" in response.json()

    async def test_get_movie_not_found(self, test_app):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/movies/")

        assert response.status_code == 404
        assert response.json() == {"detail": "No movies found matching the specified criteria"}

    async def test_get_movie_invalid_page(self, test_app):
        headers = await self.create_moderator_token()
        await self.create_movie()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/movies/?page=5&per_page=30", headers=headers)

        assert response.status_code == 404
        assert response.json() == {"detail": "No movies found matching the specified criteria"}


class TestMovieGetByID(TestMovies):
    async def test_get_movie_by_id_success(self, test_app):
        headers = await self.create_moderator_token()
        movie_id = await self.create_movie()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/movies/{movie_id}", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == movie_id

    async def test_get_movie_by_id_not_found(self, test_app):
        movie_id = 9999
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/v1/movies/{movie_id}")

        assert response.status_code == 404
        assert "detail" in response.json()


class TestMovieCreate(TestMovies):
    async def test_create_movies_success(self, test_app):
        headers = await self.create_moderator_token()
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response1 = await client.post(
                "api/v1/movies/",
                json={
                    "name": "Test Film",
                    "year": 2024,
                    "time": 120,
                    "imdb": 7.5,
                    "votes": 1000,
                    "meta_score": 70.0,
                    "gross": 1000000.0,
                    "description": "Example movie",
                    "price": 10.0,
                    "certification": "PG-13",
                    "genres": ["Drama"],
                    "stars": ["Actor One"],
                    "directors": ["Director One"],
                },
                headers=headers,
            )
            assert response1.status_code == 201

            response2 = await client.post(
                "api/v1/movies/",
                json={
                    "name": "Test Film",
                    "year": 2023,
                    "time": 120,
                    "imdb": 7,
                    "votes": 1000,
                    "meta_score": 70.0,
                    "gross": 100000.0,
                    "description": "Example movie",
                    "price": 10.0,
                    "certification": "PG-13",
                    "genres": ["Drama"],
                    "stars": ["Actor One"],
                    "directors": ["Director One"],
                },
                headers=headers,
            )

    async def test_create_movies_existing(self, test_app):
        headers = await self.create_moderator_token()
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response1 = await client.post(
                "api/v1/movies/",
                json={
                    "name": "Test Film",
                    "year": 2024,
                    "time": 120,
                    "imdb": 7.5,
                    "votes": 1000,
                    "meta_score": 70.0,
                    "gross": 1000000.0,
                    "description": "Example movie",
                    "price": 10.0,
                    "certification": "PG-13",
                    "genres": ["Drama"],
                    "stars": ["Actor One"],
                    "directors": ["Director One"],
                },
                headers=headers,
            )
            assert response1.status_code == 201

            response2 = await client.post(
                "api/v1/movies/",
                json={
                    "name": "Test Film",
                    "year": 2023,
                    "time": 120,
                    "imdb": 7,
                    "votes": 1000,
                    "meta_score": 70.0,
                    "gross": 100000.0,
                    "description": "Example movie",
                    "price": 10.0,
                    "certification": "PG-13",
                    "genres": ["Drama"],
                    "stars": ["Actor One"],
                    "directors": ["Director One"],
                },
                headers=headers,
            )

        assert response2.status_code == 409
        assert "detail" in response2.json()


class TestMovieUpdate(TestMovies):
    async def test_update_movies_success(self, test_app):
        headers = await self.create_moderator_token()
        movie_id = await self.create_movie()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/movies/{movie_id}",
                json={
                    "name": "Test Film11",
                    "description": "Test Film",
                },
                headers=headers
            )

        assert response.status_code == 200
        assert response.json() == {"detail": "Movie updated successfully."}

    async def test_update_movies_not_found_user(self, test_app):
        headers = await self.create_moderator_token()
        movie_id = 9999

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                f"/api/v1/movies/{movie_id}",
                json={
                    "name": "Test Film11",
                    "description": "Test Film",
                },
                headers=headers
            )

        assert response.status_code == 404
        assert response.json() == {"detail": f"Movie with ID '{movie_id}' not found."}


class TestMovieDelete(TestMovies):
    async def test_delete_movie_success(self, test_app):
        headers = await self.create_moderator_token()
        movie_id = await self.create_movie()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(
                f"/api/v1/movies/{movie_id}",
                headers=headers
            )

        assert response.status_code == 204

    async def test_delete_movie_not_found_user(self, test_app):
        headers = await self.create_moderator_token()
        movie_id = 9999

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(
                f"/api/v1/movies/{movie_id}",
                headers=headers
            )

        assert response.status_code == 404
        assert response.json() == {"detail": f"Movie with ID '{movie_id}' not found."}

    async def test_delete_movie_with_existing_order_returns(self, test_app):
        headers = await self.create_moderator_token()
        movie_id = await self.create_movie()
        hashed = hash_password("Password123!")
        async with engine.begin() as conn:
            result = await conn.execute(
                insert(UserModel).values(
                    email="user@example.com",
                    hashed_password=hash_password("Password123!"),
                    is_active=True,
                    group_id=1
                ).returning(UserModel.id)
            )
            user_id = result.scalar_one()
            result = await conn.execute(
                insert(OrdersModel).values(
                    user_id=user_id,
                ).returning(OrdersModel.id)
            )
            order_id = result.scalar_one()
            await conn.execute(
                insert(OrderItemModel).values(
                    order_id=order_id,
                    movie_id=movie_id,
                    price_at_order=10,
                )
            )
            await conn.commit()

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(
                f"/api/v1/movies/{movie_id}",
                headers=headers
            )

        assert response.status_code == 400
        assert response.json() == {"detail": "Cannot delete a movie that has been "
                                             "purchased by at least one user."}
