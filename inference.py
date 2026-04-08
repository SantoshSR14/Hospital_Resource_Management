#!/usr/bin/env python3
"""
Baseline Inference Script for Hospital Resource Management
Updated to use the unified Hugging Face Router for free inference.
Emits structured [START], [STEP], [END] logs for evaluation.
"""

import json
import os
import sys
import time
from typing import Dict, Any, List

import requests
from openai import OpenAI

# ===================== CONFIGURATION =====================

# Defaults ONLY for API_BASE_URL and MODEL_NAME
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
# Unified model name for free serverless inference
MODEL_NAME = os.getenv("MODEL_NAME", "meta-llama/Llama-3.3-70B-Instruct")
HF_TOKEN = os.getenv("HF_TOKEN")                         # Required Secret
LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME")         

TASK_NAME = "hospital_resource_management"
BENCHMARK = "HospitalResourceManagement"
MAX_STEPS = 30
SUCCESS_SCORE_THRESHOLD = 0.5

# Configure client to use the unified Hugging Face router
client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=HF_TOKEN if HF_TOKEN else "hf_placeholder"
)

# ===================== REQUIRED LOG FORMAT =====================

def log_start(task: str, env: str, model: str):
    """Emit [START] log — exact format required by evaluator."""
    payload = {
        "type": "START",
        "task": task,
        "env": env,
        "model": model,
        "timestamp": time.time(),
    }
    print(json.dumps(payload), flush=True)
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: Any, reward: float, done: bool, error: Any = None):
    """Emit [STEP] log — exact format required by evaluator."""
    payload = {
        "type": "STEP",
        "step": step,
        "action": action,
        "reward": round(reward, 4),
        "done": done,
        "error": error,
        "timestamp": time.time(),
    }
    print(json.dumps(payload), flush=True)
    print(f"[STEP] step={step} action={action} reward={reward:.4f} done={done}", flush=True)


def log_end(success: bool, steps: int, score: float, rewards: List[float]):
    """Emit [END] log — exact format required by evaluator."""
    payload = {
        "type": "END",
        "success": success,
        "steps": steps,
        "score": round(score, 4),
        "rewards": [round(r, 4) for r in rewards],
        "timestamp": time.time(),
    }
    print(json.dumps(payload), flush=True)
    print(f"[END] success={success} steps={steps} score={score:.4f}", flush=True)


# ===================== ENVIRONMENT API =====================

def reset_environment(task: str) -> Dict[str, Any]:
    resp = requests.post(f"{API_BASE_URL}/reset", json={"task": task}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def step_environment(action: Dict[str, Any]) -> Dict[str, Any]:
    resp = requests.post(f"{API_BASE_URL}/step", json={"action": action}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_state() -> Dict[str, Any]:
    resp = requests.get(f"{API_BASE_URL}/state", timeout=30)
    resp.raise_for_status()
    return resp.json()


def grade_task() -> Dict[str, Any]:
    resp = requests.post(f"{API_BASE_URL}/grade", timeout=30)
    resp.raise_for_status()
    return resp.json()


# ===================== AGENT =====================

class HospitalAgent:
    """Hospital operations agent optimized for Llama-3 instruction following."""

    def decide_action(self, state: Dict[str, Any], task_description: str) -> Dict[str, Any]:
        state_summary = self._summarize_state(state)

        # Refined prompt for Llama-3 to ensure strict JSON output
        messages = [
            {
                "role": "system", 
                "content": "You are a hospital manager. Your task is to output exactly ONE JSON object representing an action. No conversation."
            },
            {
                "role": "user", 
                "content": f"STATE:\n{state_summary}\n\nTASK:\n{task_description}\n\nValid action types: assign_bed, allocate_staff, discharge_patient, transfer_patient, request_equipment, escalate_shortage, skip. Return ONE JSON action:"
            }
        ]

        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                max_tokens=100,
                messages=messages,
                temperature=0.0, # Greedy decoding for reliability
            )

            text = response.choices[0].message.content.strip()

            # Robust JSON boundary finding
            start = text.find('{')
            end = text.rfind('}') + 1
            if start != -1 and end != 0:
                return json.loads(text[start:end])

            return {"type": "skip"}
        except Exception:
            return {"type": "skip"}

    def _summarize_state(self, state: Dict[str, Any]) -> str:
        s = state.get("state", state)
        beds = s.get("beds", {})
        icu = beds.get("icu", {})
        general = beds.get("general", {})
        pending = s.get("pending_patients", [])

        icu_free = [b['id'] for b in icu.get("details", []) if b.get("status") == "free"][:2]
        gen_free = [b['id'] for b in general.get("details", []) if b.get("status") == "free"][:2]

        return f"ICU Free: {icu_free} | Gen Free: {gen_free} | Pending: {len(pending)}"


# ===================== TASK RUNNER =====================

def run_task(task: str) -> tuple:
    print(f"\n--- Running Task: {task.upper()} ---", flush=True)
    rewards: List[float] = []
    steps_taken = 0
    score = 0.0
    success = False

    log_start(task=task, env=BENCHMARK, model=MODEL_NAME)

    try:
        reset_resp = reset_environment(task)
        task_desc = reset_resp.get("task_description", "")
        state = reset_resp.get("initial_state", {})

        agent = HospitalAgent()

        for step in range(1, MAX_STEPS + 1):
            action = agent.decide_action({"state": state}, task_desc)
            
            reward = 0.0
            done = False
            error = None
            try:
                step_resp = step_environment(action)
                reward = step_resp.get("reward", 0.0)
                done = step_resp.get("done", False)
                state = step_resp.get("state", state)
            except Exception as e:
                error = str(e)
                done = True

            rewards.append(reward)
            steps_taken = step
            log_step(step=step, action=json.dumps(action), reward=reward, done=done, error=error)

            if done:
                break

        grade_resp = grade_task()
        score = min(max(float(grade_resp.get("score", 0.0)), 0.0), 1.0)
        success = score >= SUCCESS_SCORE_THRESHOLD

    except Exception as e:
        print(f"Task Failed: {e}")

    log_end(success=success, steps=steps_taken, score=score, rewards=rewards)
    return score, rewards

def main():
    tasks = ["easy", "medium", "hard"]
    for task in tasks:
        run_task(task)

if __name__ == "__main__":
    main()