"""
REST API for React Graph Visualization

Provides endpoints for:
- Root task retrieval
- Batch task fetching
- Paginated subtask loading
- Callback retrieval
- WebSocket for real-time updates
"""

from typing import Optional
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import rapyer

from mageflow.signature.model import TaskSignature
from mageflow.chain.model import ChainTaskSignature
from mageflow.swarm.model import SwarmTaskSignature, BatchItemTaskSignature
from mageflow.visualizer.data import extract_signatures
from mageflow.visualizer.builder import create_builders, find_unmentioned_tasks


# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="MageFlow Visualizer API",
    description="REST API for workflow graph visualization",
    version="1.0.0",
)

# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Pydantic Models
# ============================================================================

class TaskResponse(BaseModel):
    """Serialized task for API response"""
    id: str
    type: str
    name: str
    status: str
    parent_id: Optional[str] = None
    subtask_ids: list[str] = []
    success_callback_ids: list[str] = []
    error_callback_ids: list[str] = []
    kwargs: dict = {}
    created_at: str


class RootTasksResponse(BaseModel):
    """Response for root tasks endpoint"""
    taskIds: list[str]


class BatchRequest(BaseModel):
    """Request body for batch task fetch"""
    taskIds: list[str]


class SubtasksResponse(BaseModel):
    """Response for paginated subtasks"""
    taskIds: list[str]
    totalCount: int
    page: int
    pageSize: int


class CallbacksResponse(BaseModel):
    """Response for task callbacks"""
    success_callback_ids: list[str]
    error_callback_ids: list[str]


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: str


# ============================================================================
# Helper Functions
# ============================================================================

def serialize_task(task: TaskSignature) -> TaskResponse:
    """Convert TaskSignature to API response format"""

    # Determine task type
    if isinstance(task, ChainTaskSignature):
        task_type = "chain"
        subtask_ids = list(task.tasks) if hasattr(task, 'tasks') else []
    elif isinstance(task, SwarmTaskSignature):
        task_type = "swarm"
        subtask_ids = list(task.tasks) if hasattr(task, 'tasks') else []
    elif isinstance(task, BatchItemTaskSignature):
        task_type = "batch_item"
        subtask_ids = []
    else:
        task_type = "task"
        subtask_ids = []

    # Get callbacks
    success_callbacks = list(task.success_callbacks) if task.success_callbacks else []
    error_callbacks = list(task.error_callbacks) if task.error_callbacks else []

    # Get creation time
    created_at = task.creation_time.isoformat() if task.creation_time else datetime.now().isoformat()

    # Get status
    status = str(task.task_status.value) if task.task_status else "pending"

    return TaskResponse(
        id=task.key,
        type=task_type,
        name=task.task_name,
        status=status,
        parent_id=None,  # Will be set by client based on context
        subtask_ids=subtask_ids,
        success_callback_ids=success_callbacks,
        error_callback_ids=error_callbacks,
        kwargs=dict(task.kwargs) if task.kwargs else {},
        created_at=created_at,
    )


async def get_task_by_id(task_id: str) -> Optional[TaskSignature]:
    """Fetch a single task by ID from Redis"""
    try:
        task = await rapyer.aget(task_id)
        return task
    except Exception:
        return None


async def get_tasks_by_ids(task_ids: list[str]) -> list[TaskSignature]:
    """Fetch multiple tasks by ID from Redis"""
    tasks = []
    for task_id in task_ids:
        task = await get_task_by_id(task_id)
        if task:
            tasks.append(task)
    return tasks


# ============================================================================
# REST Endpoints
# ============================================================================

@app.get("/api/v1/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat()
    )


@app.get("/api/v1/workflows/roots", response_model=RootTasksResponse)
async def get_root_tasks():
    """
    Get all root task IDs.
    Root tasks are tasks that are not called by any other task.
    """
    try:
        signatures = await extract_signatures()
        ctx = create_builders(signatures)
        root_ids = find_unmentioned_tasks(ctx)
        return RootTasksResponse(taskIds=root_ids)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/tasks/batch", response_model=list[TaskResponse])
async def get_tasks_batch(request: BatchRequest):
    """
    Batch fetch multiple tasks by ID.
    Returns task details for all requested IDs that exist.
    """
    try:
        tasks = await get_tasks_by_ids(request.taskIds)
        return [serialize_task(task) for task in tasks]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """Get a single task by ID"""
    task = await get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return serialize_task(task)


@app.get("/api/v1/tasks/{task_id}/subtasks", response_model=SubtasksResponse)
async def get_task_subtasks(
    task_id: str,
    page: int = Query(0, ge=0, description="Page number (0-indexed)"),
    pageSize: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """
    Get paginated subtasks for a swarm or chain task.
    Returns subtask IDs for the requested page.
    """
    task = await get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    # Get subtask IDs based on task type
    if isinstance(task, (SwarmTaskSignature, ChainTaskSignature)):
        all_subtask_ids = list(task.tasks) if hasattr(task, 'tasks') else []
    else:
        all_subtask_ids = []

    # Calculate pagination
    total_count = len(all_subtask_ids)
    start_idx = page * pageSize
    end_idx = start_idx + pageSize
    page_ids = all_subtask_ids[start_idx:end_idx]

    return SubtasksResponse(
        taskIds=page_ids,
        totalCount=total_count,
        page=page,
        pageSize=pageSize,
    )


@app.get("/api/v1/tasks/{task_id}/callbacks", response_model=CallbacksResponse)
async def get_task_callbacks(task_id: str):
    """Get callback IDs for a task"""
    task = await get_task_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    success_callbacks = list(task.success_callbacks) if task.success_callbacks else []
    error_callbacks = list(task.error_callbacks) if task.error_callbacks else []

    return CallbacksResponse(
        success_callback_ids=success_callbacks,
        error_callback_ids=error_callbacks,
    )


# ============================================================================
# WebSocket for Real-time Updates
# ============================================================================

class ConnectionManager:
    """Manages WebSocket connections"""

    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.subscriptions: dict[str, set[WebSocket]] = {}  # task_id -> set of websockets

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        # Remove from all subscriptions
        for task_id in list(self.subscriptions.keys()):
            self.subscriptions[task_id].discard(websocket)
            if not self.subscriptions[task_id]:
                del self.subscriptions[task_id]

    def subscribe(self, websocket: WebSocket, task_id: str):
        if task_id not in self.subscriptions:
            self.subscriptions[task_id] = set()
        self.subscriptions[task_id].add(websocket)

    def unsubscribe(self, websocket: WebSocket, task_id: str):
        if task_id in self.subscriptions:
            self.subscriptions[task_id].discard(websocket)

    async def broadcast(self, message: dict):
        """Broadcast to all connections"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

    async def send_to_subscribers(self, task_id: str, message: dict):
        """Send to subscribers of a specific task"""
        if task_id in self.subscriptions:
            for websocket in self.subscriptions[task_id]:
                try:
                    await websocket.send_json(message)
                except Exception:
                    pass


manager = ConnectionManager()


@app.websocket("/ws/tasks")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time task updates.

    Client can send:
    - {"type": "subscribe", "taskId": "..."}
    - {"type": "unsubscribe", "taskId": "..."}
    - {"type": "ping"}

    Server sends:
    - {"type": "task_status_changed", "taskId": "...", "status": "..."}
    - {"type": "task_updated", "taskId": "..."}
    - {"type": "subtask_added", "taskId": "...", "parentId": "..."}
    - {"type": "pong"}
    """
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()

            if data.get("type") == "subscribe":
                task_id = data.get("taskId")
                if task_id:
                    manager.subscribe(websocket, task_id)

            elif data.get("type") == "unsubscribe":
                task_id = data.get("taskId")
                if task_id:
                    manager.unsubscribe(websocket, task_id)

            elif data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ============================================================================
# Event Publishing Functions (for use by task system)
# ============================================================================

async def publish_task_status_changed(task_id: str, status: str):
    """Publish task status change event"""
    await manager.send_to_subscribers(task_id, {
        "type": "task_status_changed",
        "taskId": task_id,
        "status": status,
    })
    # Also broadcast to all for general updates
    await manager.broadcast({
        "type": "task_status_changed",
        "taskId": task_id,
        "status": status,
    })


async def publish_task_updated(task_id: str):
    """Publish task update event"""
    await manager.send_to_subscribers(task_id, {
        "type": "task_updated",
        "taskId": task_id,
    })


async def publish_subtask_added(task_id: str, parent_id: str):
    """Publish subtask added event"""
    await manager.send_to_subscribers(parent_id, {
        "type": "subtask_added",
        "taskId": task_id,
        "parentId": parent_id,
    })


# ============================================================================
# Run with Uvicorn
# ============================================================================

def run_api(host: str = "0.0.0.0", port: int = 8000):
    """Run the API server"""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_api()
