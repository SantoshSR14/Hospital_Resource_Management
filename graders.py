"""
IMPROVED Task Graders for Hospital Resource Management Environment (DYNAMIC)
Grades agent performance on easy, medium, and hard tasks with dynamic scenarios.
"""

from typing import Dict, List, Tuple, Any
from environment import HospitalEnvironment, Acuity, PatientStatus, ActionType
import json


class TaskGrader:
    """Base class for task grading"""

    def __init__(self, env: HospitalEnvironment):
        self.env = env
        self.name = ""
        self.description = ""
        self.difficulty = ""

    def setup(self):
        """Setup task-specific environment state"""
        pass

    def grade(self) -> Tuple[float, Dict[str, Any]]:
        """Grade agent performance. Returns (score, details)"""
        pass

    def get_task_description(self) -> str:
        """Return task description for agent"""
        pass


class EasyTaskGrader(TaskGrader):
    """
    EASY TASK: Routine Allocation (DYNAMIC)
    - 2-4 random patients with various conditions
    - Sufficient beds available
    - New patients may arrive (20% chance each step)
    - Agent must assign correct wards based on acuity
    """

    def __init__(self, env: HospitalEnvironment):
        super().__init__(env)
        self.name = "Routine Allocation"
        self.difficulty = "easy"
        self.description = "2-4 random patients, dynamic arrivals, assign to correct wards"
        self.max_steps = 20

    def setup(self):
        """Setup easy task with dynamic scenario"""
        self.env.reset(task="easy")
        self.initial_pending = len(self.env.pending_patients)

    def get_task_description(self) -> str:
        pending = self.env.pending_patients
        desc = f"""
EASY TASK: Routine Allocation (DYNAMIC)
============================================
{len(pending)} patients in emergency:
"""
        for i, p in enumerate(pending[:4], 1):
            desc += f"  {i}. {p.condition} ({p.acuity.value})\n"
        
        if len(pending) > 4:
            desc += f"  ... and {len(pending) - 4} more patients\n"
        
        desc += f"""
NOTE: New patients may arrive during the task (20% chance per step).

Objective: Assign each patient to the CORRECT ward based on acuity.
Scoring:
  +0.25: Correct bed assignment (right ward type)
  +0.15: Priority order respected (critical first)
  -0.2:  Wrong bed type
  -0.3:  Critical patient unassigned after 5 steps

Max steps: {self.max_steps}
        """
        return desc

    def grade(self) -> Tuple[float, Dict[str, Any]]:
        """Grade the easy task"""
        score = 0.0
        details = {
            "task": self.name,
            "difficulty": self.difficulty,
            "max_steps": self.max_steps,
            "initial_patients": self.initial_pending,
        }

        assigned_patients = self.env.admitted_patients
        unassigned_pending = self.env.pending_patients

        # Score for correct assignments
        correct = 0
        wrong = 0
        for patient in assigned_patients.values():
            bed_id = patient.assigned_bed
            if bed_id and bed_id in self.env.beds:
                bed = self.env.beds[bed_id]
                required_ward = self.env._get_required_ward(patient.acuity)
                
                if bed.ward_type == required_ward:
                    score += 0.25
                    correct += 1
                else:
                    score -= 0.2
                    wrong += 1

        details["correct_assignments"] = correct
        details["wrong_assignments"] = wrong

        # Penalty for unassigned critical patients
        critical_unassigned = sum(1 for p in unassigned_pending if p.acuity == Acuity.CRITICAL)
        score -= 0.3 * critical_unassigned
        details["unassigned_critical"] = critical_unassigned

        # Bonus for priority
        if self._respects_priority():
            score += 0.15
            details["priority_respected"] = True
        else:
            details["priority_respected"] = False

        # Penalty for exceeding steps
        if self.env.step_count > self.max_steps:
            score -= 0.1

        final_score = max(0.01, min(0.99, score))
        details["final_score"] = final_score
        details["assigned"] = len(assigned_patients)
        details["unassigned"] = len(unassigned_pending)
        details["total_steps"] = self.env.step_count

        return final_score, details

    def _respects_priority(self) -> bool:
        """Check if critical patients were assigned before others"""
        critical_steps = []
        non_critical_steps = []
        
        for action in self.env.action_history:
            if action.get("type") == "assign_bed":
                pid = action.get("patient_id")
                for p in self.env.admitted_patients.values():
                    if p.id == pid:
                        if p.acuity == Acuity.CRITICAL:
                            critical_steps.append(action.get("step"))
                        else:
                            non_critical_steps.append(action.get("step"))
        
        if critical_steps and non_critical_steps:
            return min(critical_steps) < min(non_critical_steps)
        return True


class MediumTaskGrader(TaskGrader):
    """
    MEDIUM TASK: Resource Conflict (DYNAMIC)
    - ICU starts 60-95% full (random)
    - 1-3 critical patients arrive
    - New patients may arrive
    - Staff/equipment may fail
    - Must manage conflicts without unsafe discharges
    """

    def __init__(self, env: HospitalEnvironment):
        super().__init__(env)
        self.name = "Resource Conflict"
        self.difficulty = "medium"
        self.description = "Dynamic ICU conflict, manage resources safely"
        self.max_steps = 30

    def setup(self):
        """Setup medium task with resource conflict"""
        self.env.reset(task="medium")
        self.initial_critical = sum(1 for p in self.env.pending_patients if p.acuity == Acuity.CRITICAL)

    def get_task_description(self) -> str:
        critical = [p for p in self.env.pending_patients if p.acuity == Acuity.CRITICAL]
        icu_occupied = sum(1 for b in self.env.beds.values() if b.ward_type.value == "icu" and b.status == "occupied")
        icu_total = sum(1 for b in self.env.beds.values() if b.ward_type.value == "icu")
        
        return f"""
MEDIUM TASK: Resource Conflict (DYNAMIC)
============================================
ICU Status: {icu_occupied}/{icu_total} beds occupied

{len(critical)} CRITICAL patients need ICU:
"""  + "\n".join([f"  - {p.condition}" for p in critical[:3]]) + f"""

Challenge: Must manage with limited ICU beds.
May need to discharge/transfer stable patients.
New patients may arrive (15% chance per step).

Objective: Allocate critical patients safely.
Scoring:
  +0.20: Critical patient assigned to ICU
  +0.20: Safe bed freed (discharge stable patient)
  +0.10: Proper escalation
  -0.40: Unsafe discharge
  -0.30: Critical unassigned >15 steps

Max steps: {self.max_steps}
        """

    def grade(self) -> Tuple[float, Dict[str, Any]]:
        """Grade medium task"""
        score = 0.0
        details = {
            "task": self.name,
            "difficulty": self.difficulty,
            "max_steps": self.max_steps,
            "initial_critical": self.initial_critical,
        }

        # Count critical patients assigned
        critical_assigned = sum(1 for p in self.env.admitted_patients.values() if p.acuity == Acuity.CRITICAL)
        score += 0.20 * min(critical_assigned, self.initial_critical)
        details["critical_assigned"] = critical_assigned

        # Check for proper discharge
        discharge_actions = sum(1 for a in self.env.action_history if a.get("type") == "discharge_patient")
        if discharge_actions > 0:
            score += 0.20
            details["bed_freed"] = True
        else:
            details["bed_freed"] = False

        # Check escalations
        escalations = len(self.env.escalations)
        score += 0.10 * min(escalations, 2)
        details["escalations"] = escalations

        # Penalty for unassigned critical
        critical_unassigned = sum(1 for p in self.env.pending_patients if p.acuity == Acuity.CRITICAL)
        if critical_unassigned > 0 and self.env.step_count > 15:
            score -= 0.30 * critical_unassigned

        details["unassigned_critical"] = critical_unassigned

        # Penalty for exceeding steps
        if self.env.step_count > self.max_steps:
            score -= 0.1

        final_score = max(0.0, min(1.0, score))
        details["final_score"] = final_score
        details["total_steps"] = self.env.step_count

        return final_score, details


class HardTaskGrader(TaskGrader):
    """
    HARD TASK: Mass Casualty Event (DYNAMIC)
    - 10-20 random patients from accident
    - Staff shortage (50% removed)
    - Equipment failures (1-3 ventilators broken)
    - Continuous arrivals (25% chance per step)
    - Must triage under extreme pressure
    """

    def __init__(self, env: HospitalEnvironment):
        super().__init__(env)
        self.name = "Mass Casualty Event"
        self.difficulty = "hard"
        self.description = "15+ patients, staff shortage, equipment failures, extreme triage"
        self.max_steps = 40

    def setup(self):
        """Setup hard task with mass casualty"""
        self.env.reset(task="hard")
        self.initial_total = len(self.env.pending_patients) + len(self.env.admitted_patients)
        self.initial_critical = sum(1 for p in self.env.pending_patients if p.acuity == Acuity.CRITICAL)

    def get_task_description(self) -> str:
        total = len(self.env.pending_patients) + len(self.env.admitted_patients)
        critical = sum(1 for p in self.env.pending_patients if p.acuity == Acuity.CRITICAL)
        staff_count = len(self.env.staff)
        broken_vents = sum(1 for e in self.env.equipment.values() if e.equipment_type == "ventilator" and e.status == "broken")
        
        return f"""
HARD TASK: Mass Casualty Event (DYNAMIC)
============================================
MASS CASUALTY INCIDENT: {total} patients from accident
  - {critical} CRITICAL patients
  - Multiple SEVERE patients  
  - Many MINOR patients

CONSTRAINTS:
  - Staff: {staff_count} available (50% shortage)
  - Equipment: {broken_vents} ventilators broken
  - New patients arriving (25% chance per step)
  - External hospitals FULL (no transfers)

OBJECTIVE: Maximize lives saved through optimal triage.
Scoring:
  +0.20: Critical patient assigned within 5 steps
  +0.15: Proper escalation
  +0.10: Bonus if critical wait <5 steps avg
  -0.30: Unsafe discharge
  -0.40: Critical patient death

Max steps: {self.max_steps}
        """

    def grade(self) -> Tuple[float, Dict[str, Any]]:
        """Grade hard task"""
        score = 0.0
        details = {
            "task": self.name,
            "difficulty": self.difficulty,
            "max_steps": self.max_steps,
            "initial_total_patients": self.initial_total,
            "initial_critical": self.initial_critical,
        }

        # Count critical assignments
        critical_assigned = sum(1 for p in self.env.admitted_patients.values() if p.acuity == Acuity.CRITICAL)
        score += 0.20 * min(critical_assigned, self.initial_critical)
        details["critical_assigned"] = critical_assigned

        # Check escalations
        escalations = len(self.env.escalations)
        score += 0.15 * min(escalations, 2)
        details["escalations"] = escalations

        # Bonus for low critical wait time
        if critical_assigned > 0:
            avg_wait = self.env.step_count / critical_assigned
            if avg_wait < 5:
                score += 0.10
                details["low_wait_bonus"] = True
            else:
                details["low_wait_bonus"] = False

        # Penalty for excessive unassigned
        critical_unassigned = sum(1 for p in self.env.pending_patients if p.acuity == Acuity.CRITICAL)
        if critical_unassigned > self.initial_critical * 0.5:
            score -= 0.20
            details["many_unassigned"] = True
        else:
            details["many_unassigned"] = False

        # Penalty for exceeding steps
        if self.env.step_count > self.max_steps:
            score -= 0.15

        final_score = max(0.0, min(1.0, score))
        details["final_score"] = final_score
        details["total_steps"] = self.env.step_count

        return final_score, details


# Task registry
TASKS = {
    "easy": EasyTaskGrader,
    "medium": MediumTaskGrader,
    "hard": HardTaskGrader,
}
