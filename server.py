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

# Configure logging to be more descriptive for HF Container Logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Hospital Resource Management",
    description="OpenEnv environment for hospital operations management",
    version="1.0.0",
)

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
    """Reset request model - Made 'task' optional to prevent 422 errors during auto-checks"""
    task: Optional[str] = Field(
        default="easy",
        description="Task to run: 'easy', 'medium', or 'hard'"
    )
    seed: Optional[int] = None

class StepRequest(BaseModel):
    action: Dict[str, Any] = Field(..., description="Action to execute.")

class ResetResponse(BaseModel):
    status: str
    task: str
    initial_state: Dict[str, Any]
    task_description: str

class StepResponse(BaseModel):
    status: str
    state: Dict[str, Any]
    reward: float
    done: bool
    info: Dict[str, Any]

class StateResponse(BaseModel):
    status: str
    state: Dict[str, Any]
    task: str
    stats: Dict[str, Any]

class GradeResponse(BaseModel):
    status: str
    task: str
    score: float
    details: Dict[str, Any]

class TaskInfoResponse(BaseModel):
    available_tasks: List[str]
    current_task: Optional[str]
    task_descriptions: Dict[str, str]

# ===================== ENDPOINTS =====================

@app.post("/reset", response_model=ResetResponse)
async def reset(request: ResetRequest = None):
    """
    Reset the environment. Handles empty bodies and invalid tasks for auto-evaluator compliance.
    """
    global env, current_task_grader, current_task
    
    # Fallback logic for robust reset handling
    selected_task = "easy"
    if request and request.task in TASKS:
        selected_task = request.task
    
    try:
        logger.info(f"Received reset request for task: {selected_task}")
        
        # Re-initialize the environment
        env = HospitalEnvironment()
        
        # Setup grader for task
        grader_class = TASKS[selected_task]
        current_task_grader = grader_class(env)
        current_task = selected_task
        
        # Setup task-specific scenario
        current_task_grader.setup()
        
        initial_state = env.state()
        task_description = current_task_grader.get_task_description()
        
        return ResetResponse(
            status="success",
            task=selected_task,
            initial_state=initial_state,
            task_description=task_description,
        )
    
    except Exception as e:
        logger.error(f"CRITICAL ERROR during reset: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@app.post("/step", response_model=StepResponse)
async def step(request: StepRequest):
    global env
    if env is None:
        # Auto-reset if step is called before reset (rare but helpful for checks)
        await reset(ResetRequest(task="easy"))
    
    try:
        if "type" not in request.action:
            return StepResponse(
                status="error",
                state=env.state(),
                reward=-0.1,
                done=False,
                info={"error": "Action must have 'type' field"}
            )
        
        state, reward, done, info = env.step(request.action)
        return StepResponse(status="success", state=state, reward=reward, done=done, info=info)
    except Exception as e:
        logger.error(f"Step failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/state", response_model=StateResponse)
async def state():
    global env
    if env is None:
        raise HTTPException(status_code=400, detail="Initialize environment first.")
    return StateResponse(status="success", state=env.state(), task=current_task or "unknown", stats=env.get_stats())

@app.post("/grade", response_model=GradeResponse)
async def grade():
    global env, current_task_grader
    if env is None or current_task_grader is None:
        raise HTTPException(status_code=400, detail="Initialize environment first.")
    score, details = current_task_grader.grade()
    return GradeResponse(status="success", task=current_task, score=score, details=details)

@app.get("/health")
async def health():
    return {"status": "healthy", "version": "1.0.0"}

@app.get("/")
async def root():
    return {"name": "Hospital Resource Management", "status": "active"}

if __name__ == "__main__":
    import uvicorn
    # Host 0.0.0.0 is mandatory for HF Spaces
    uvicorn.run(app, host="0.0.0.0", port=8000)
