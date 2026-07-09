import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import bcrypt
import jwt
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, EmailStr, Field

API_TITLE = "todo app backend"

app = FastAPI(title=API_TITLE, docs_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=API_TITLE,
        version="0.1.0",
        routes=app.routes,
    )
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


@app.get("/docs", include_in_schema=False)
async def swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=API_TITLE,
    )

TODOS_FILE = Path(__file__).parent / "todos.json"
USERS_FILE = Path(__file__).parent / "users.json"
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-change-in-production-now")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60 * 24


class SignUpRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)


class SignInRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    email: str


class CreateTodoRequest(BaseModel):
    todo_text: str
    status: str = "uncompleted"


class UpdateTodoRequest(BaseModel):
    todo_text: Optional[str] = None
    status: Optional[str] = None


def _load_todos() -> list[dict]:
    if not TODOS_FILE.exists():
        return []
    with TODOS_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def _save_todos(todos: list[dict]) -> None:
    with TODOS_FILE.open("w", encoding="utf-8") as file:
        json.dump(todos, file, indent=2)


def _get_next_id(todos: list[dict]) -> int:
    if not todos:
        return 1
    return max(todo["todo_id"] for todo in todos) + 1


def _load_users() -> list[dict]:
    if not USERS_FILE.exists():
        return []
    with USERS_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def _save_users(users: list[dict]) -> None:
    with USERS_FILE.open("w", encoding="utf-8") as file:
        json.dump(users, file, indent=2)


def _get_next_user_id(users: list[dict]) -> int:
    if not users:
        return 1
    return max(user["user_id"] for user in users) + 1


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))


def _create_access_token(user_id: int, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "email": email, "exp": expire}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


@app.post("/signup", response_model=AuthResponse, status_code=201)
def sign_up(request: SignUpRequest):
    users = _load_users()
    email = request.email.lower()

    if any(user["email"] == email for user in users):
        raise HTTPException(status_code=400, detail="Email is already registered")

    new_user = {
        "user_id": _get_next_user_id(users),
        "email": email,
        "password_hash": _hash_password(request.password),
    }
    users.append(new_user)
    _save_users(users)

    return AuthResponse(
        access_token=_create_access_token(new_user["user_id"], new_user["email"]),
        user_id=new_user["user_id"],
        email=new_user["email"],
    )


@app.post("/signin", response_model=AuthResponse)
def sign_in(request: SignInRequest):
    users = _load_users()
    email = request.email.lower()
    user = next((user for user in users if user["email"] == email), None)

    if user is None or not _verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return AuthResponse(
        access_token=_create_access_token(user["user_id"], user["email"]),
        user_id=user["user_id"],
        email=user["email"],
    )


@app.post("/create_todo")
def create_todo(request: CreateTodoRequest):
    todos = _load_todos()
    new_todo = {
        "todo_id": _get_next_id(todos),
        "todo_text": request.todo_text,
        "status": request.status,
    }
    todos.append(new_todo)
    _save_todos(todos)
    return new_todo


@app.get("/get_todos")
def get_todos():
    return _load_todos()


@app.put("/update_todo")
def update_todo(todo_id: int, request: UpdateTodoRequest):
    todos = _load_todos()
    todo_index = next((i for i, todo in enumerate(todos) if todo["todo_id"] == todo_id), None)

    if todo_index is None:
        raise HTTPException(status_code=404, detail=f"Todo with id {todo_id} not found")

    if request.todo_text is None and request.status is None:
        raise HTTPException(status_code=400, detail="At least one of todo_text or status must be provided")

    if request.todo_text is not None:
        todos[todo_index]["todo_text"] = request.todo_text
    if request.status is not None:
        todos[todo_index]["status"] = request.status

    _save_todos(todos)
    return todos[todo_index]


@app.delete("/delete_todo")
def delete_todo(todo_id: int):
    todos = _load_todos()
    todo_index = next((i for i, todo in enumerate(todos) if todo["todo_id"] == todo_id), None)

    if todo_index is None:
        raise HTTPException(status_code=404, detail=f"Todo with id {todo_id} not found")

    todos.pop(todo_index)
    _save_todos(todos)
    return {"message": f"Todo with id {todo_id} deleted successfully"}
