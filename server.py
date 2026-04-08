"""
FastAPI Server for Hospital Resource Management Environment
Implements OpenEnv spec with /reset, /step, /state endpoints
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import json
from environment import HospitalEnvironment, Acuity, ActionType
from graders import EasyTaskGrader, MediumTaskGrader, HardTaskGrader, TASKS
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Hospital Resource Management",
    description="OpenEnv environment for hospital operations management",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global environment instance
env: Optional[HospitalEnvironment] = None
current_task_grader = None
current_task = None


# Pydantic models
class ResetRequest(BaseModel):
    """Reset request model"""
    task: str = Field(
        ...,
        description="Task to run: 'easy', 'medium', or 'hard'"
    )
    seed: Optional[int] = None


class StepRequest(BaseModel):
    """Step request model"""
    action: Dict[str, Any] = Field(
        ...,
        description="Action to execute. Must have 'type' field."
    )


class ResetResponse(BaseModel):
    """Reset response model"""
    status: str
    task: str
    initial_state: Dict[str, Any]
    task_description: str


class StepResponse(BaseModel):
    """Step response model"""
    status: str
    state: Dict[str, Any]
    reward: float
    done: bool
    info: Dict[str, Any]


class StateResponse(BaseModel):
    """State response model"""
    status: str
    state: Dict[str, Any]
    task: str
    stats: Dict[str, Any]


class GradeResponse(BaseModel):
    """Grade response model"""
    status: str
    task: str
    score: float
    details: Dict[str, Any]


class TaskInfoResponse(BaseModel):
    """Task info response model"""
    available_tasks: List[str]
    current_task: Optional[str]
    task_descriptions: Dict[str, str]


# ===================== ENDPOINTS =====================


@app.post("/reset", response_model=ResetResponse)
async def reset(request: ResetRequest):
    """
    Reset the environment for a specific task.
    
    Args:
        request: ResetRequest with task name
    
    Returns:
        Initial state and task description
    """
    global env, current_task_grader, current_task
    
    if request.task not in TASKS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid task. Choose from: {list(TASKS.keys())}"
        )
    
    try:
        # Create environment
        env = HospitalEnvironment()
        
        # Setup grader for task
        grader_class = TASKS[request.task]
        current_task_grader = grader_class(env)
        current_task = request.task
        
        # Setup task-specific scenario
        current_task_grader.setup()
        
        initial_state = env.state()
        task_description = current_task_grader.get_task_description()
        
        logger.info(f"Reset environment for task: {request.task}")
        
        return ResetResponse(
            status="success",
            task=request.task,
            initial_state=initial_state,
            task_description=task_description,
        )
    
    except Exception as e:
        logger.error(f"Reset failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/step", response_model=StepResponse)
async def step(request: StepRequest):
    """
    Execute one step in the environment.
    
    Args:
        request: StepRequest with action
    
    Returns:
        New state, reward, done flag, and info dict
    """
    global env
    
    if env is None:
        raise HTTPException(
            status_code=400,
            detail="Environment not initialized. Call /reset first."
        )
    
    try:
        # Validate action has required 'type' field
        if "type" not in request.action:
            raise ValueError("Action must have 'type' field")
        
        # Execute step
        state, reward, done, info = env.step(request.action)
        
        logger.info(f"Step {env.step_count}: action={request.action.get('type')}, reward={reward}")
        
        return StepResponse(
            status="success",
            state=state,
            reward=reward,
            done=done,
            info=info,
        )
    
    except Exception as e:
        logger.error(f"Step failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/state", response_model=StateResponse)
async def state():
    """
    Get current environment state without executing action.
    
    Returns:
        Current state and statistics
    """
    global env, current_task
    
    if env is None:
        raise HTTPException(
            status_code=400,
            detail="Environment not initialized. Call /reset first."
        )
    
    try:
        current_state = env.state()
        stats = env.get_stats()
        
        return StateResponse(
            status="success",
            state=current_state,
            task=current_task or "unknown",
            stats=stats,
        )
    
    except Exception as e:
        logger.error(f"State retrieval failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/grade", response_model=GradeResponse)
async def grade():
    """
    Grade the current task based on environment state and agent actions.
    
    Returns:
        Score and detailed grading information
    """
    global env, current_task_grader, current_task
    
    if env is None or current_task_grader is None:
        raise HTTPException(
            status_code=400,
            detail="Environment not initialized. Call /reset first."
        )
    
    try:
        score, details = current_task_grader.grade()
        
        logger.info(f"Task {current_task} graded: score={score}")
        
        return GradeResponse(
            status="success",
            task=current_task,
            score=score,
            details=details,
        )
    
    except Exception as e:
        logger.error(f"Grading failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tasks", response_model=TaskInfoResponse)
async def get_tasks():
    """
    Get information about available tasks.
    
    Returns:
        List of available tasks and their descriptions
    """
    try:
        task_descriptions = {}
        for task_name, grader_class in TASKS.items():
            grader = grader_class(HospitalEnvironment())
            task_descriptions[task_name] = grader.get_task_description()
        
        return TaskInfoResponse(
            available_tasks=list(TASKS.keys()),
            current_task=current_task,
            task_descriptions=task_descriptions,
        )
    
    except Exception as e:
        logger.error(f"Task info retrieval failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "version": "1.0.0"}


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "Hospital Resource Management",
        "version": "1.0.0",
        "description": "OpenEnv environment for hospital operations management",
        "endpoints": {
            "reset": "POST /reset - Initialize environment for a task",
            "step": "POST /step - Execute one action",
            "state": "GET /state - Get current state",
            "grade": "POST /grade - Grade current task",
            "tasks": "GET /tasks - List available tasks",
            "health": "GET /health - Health check",
        }
    }


# ===================== ERROR HANDLERS =====================


@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    return {
        "status": "error",
        "detail": str(exc)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
