"""A small Todo API: in-memory storage, full CRUD, input validation."""

from threading import Lock

from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel, Field

app = FastAPI(title="Todo API", version="1.0.0")


class TodoCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    done: bool = False


class TodoUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    done: bool | None = None


class Todo(TodoCreate):
    id: int


class TodoStore:
    """Thread-safe in-memory store. Swap for a database in a real app."""

    def __init__(self) -> None:
        self._items: dict[int, Todo] = {}
        self._next_id = 1
        self._lock = Lock()

    def list(self, done: bool | None = None) -> list[Todo]:
        with self._lock:
            items = list(self._items.values())
        return items if done is None else [t for t in items if t.done == done]

    def get(self, todo_id: int) -> Todo | None:
        with self._lock:
            return self._items.get(todo_id)

    def create(self, data: TodoCreate) -> Todo:
        with self._lock:
            todo = Todo(id=self._next_id, **data.model_dump())
            self._items[todo.id] = todo
            self._next_id += 1
            return todo

    def update(self, todo_id: int, data: TodoUpdate) -> Todo | None:
        with self._lock:
            todo = self._items.get(todo_id)
            if todo is None:
                return None
            # Explicit nulls mean "no change"; model_copy skips validation, so they must not get through.
            updated = todo.model_copy(update=data.model_dump(exclude_unset=True, exclude_none=True))
            self._items[todo_id] = updated
            return updated

    def delete(self, todo_id: int) -> bool:
        with self._lock:
            return self._items.pop(todo_id, None) is not None


store = TodoStore()


def _not_found(todo_id: int) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Todo {todo_id} not found")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/todos", response_model=list[Todo])
def list_todos(done: bool | None = None) -> list[Todo]:
    return store.list(done)


@app.post("/todos", response_model=Todo, status_code=status.HTTP_201_CREATED)
def create_todo(data: TodoCreate) -> Todo:
    return store.create(data)


@app.get("/todos/{todo_id}", response_model=Todo)
def get_todo(todo_id: int) -> Todo:
    todo = store.get(todo_id)
    if todo is None:
        raise _not_found(todo_id)
    return todo


@app.patch("/todos/{todo_id}", response_model=Todo)
def update_todo(todo_id: int, data: TodoUpdate) -> Todo:
    todo = store.update(todo_id, data)
    if todo is None:
        raise _not_found(todo_id)
    return todo


@app.delete("/todos/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_todo(todo_id: int) -> Response:
    if not store.delete(todo_id):
        raise _not_found(todo_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
