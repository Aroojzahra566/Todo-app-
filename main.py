import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel

API_TITLE = "todo app backend"

app = FastAPI(title=API_TITLE, docs_url=None)


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
