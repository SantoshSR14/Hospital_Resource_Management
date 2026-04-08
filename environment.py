"""
Hospital Resource Management OpenEnv Environment
Simulates real-time hospital operations: bed allocation, staff management, equipment allocation, and patient flow.
"""

import json
import random
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from enum import Enum
from dataclasses import dataclass, asdict
import uuid


class Acuity(str, Enum):
    """Patient acuity levels"""
    CRITICAL = "critical"
    SEVERE = "severe"
    MODERATE = "moderate"
    MINOR = "minor"


class WardType(str, Enum):
    """Hospital ward types"""
    ICU = "icu"
    GENERAL = "general"
    ISOLATION = "isolation"
    PEDIATRIC = "pediatric"


class PatientStatus(str, Enum):
    """Patient status in hospital"""
    WAITING = "waiting"
    ADMITTED = "admitted"
    IN_RECOVERY = "in_recovery"
    DISCHARGED = "discharged"
    TRANSFERRED = "transferred"
    DECEASED = "deceased"


class ActionType(str, Enum):
    """Valid agent actions"""
    ASSIGN_BED = "assign_bed"
    ALLOCATE_STAFF = "allocate_staff"
    DISCHARGE_PATIENT = "discharge_patient"
    TRANSFER_PATIENT = "transfer_patient"
    REQUEST_EQUIPMENT = "request_equipment"
    ESCALATE_SHORTAGE = "escalate_shortage"
    SKIP = "skip"


@dataclass
class Bed:
    """Hospital bed representation"""
    id: str
    ward_type: WardType
    status: str  # "free" or "occupied"
    patient_id: Optional[str] = None
    has_monitor: bool = False
    has_ventilator_support: bool = False
    has_isolation: bool = False

    def to_dict(self):
        return asdict(self)


@dataclass
class Patient:
    """Patient representation"""
    id: str
    condition: str
    acuity: Acuity
    status: PatientStatus
    admitted_at: Optional[float] = None
    assigned_bed: Optional[str] = None
    requires_isolation: bool = False
    requires_ventilator: bool = False
    critical_condition_time: float = 0.0  # Time critical patient waits unallocated
    recovery_duration: float = 0.0  # How long recovery should take

    def to_dict(self):
        return {
            "id": self.id,
            "condition": self.condition,
            "acuity": self.acuity.value,
            "status": self.status.value,
            "admitted_at": self.admitted_at,
            "assigned_bed": self.assigned_bed,
            "requires_isolation": self.requires_isolation,
            "requires_ventilator": self.requires_ventilator,
            "critical_condition_time": self.critical_condition_time,
        }


@dataclass
class Staff:
    """Staff member representation"""
    id: str
    role: str  # "doctor" or "nurse"
    specialty: str
    shift_hours_remaining: float
    current_patient_load: int
    max_patient_load: int

    def to_dict(self):
        return asdict(self)


@dataclass
class Equipment:
    """Equipment representation"""
    id: str
    equipment_type: str  # "ventilator", "monitor", etc.
    status: str  # "available" or "in_use"
    location: Optional[str] = None
    patient_id: Optional[str] = None

    def to_dict(self):
        return asdict(self)


class HospitalEnvironment:
    """Main Hospital Resource Management Environment"""

    def __init__(self, config: Optional[Dict] = None):
        """Initialize hospital environment with optional config"""
        self.config = config or self._default_config()
        self.current_task = "easy"  # Default task
        self.reset()

    def _default_config(self) -> Dict:
        """Default hospital configuration"""
        return {
            "total_beds": {
                "icu": 10,
                "general": 50,
                "isolation": 15,
                "pediatric": 25,
            },
            "staff": {
                "doctors": 12,
                "nurses": 30,
            },
            "equipment": {
                "ventilators": 5,
                "monitors": 20,
            },
            "max_steps": 50,
        }

    def reset(self, task: str = "easy") -> Dict[str, Any]:
        """Reset environment to initial state with dynamic scenario generation"""
        self.step_count = 0
        self.time = 0.0
        self.current_task = task
        self.pending_patients: List[Patient] = []
        self.admitted_patients: Dict[str, Patient] = {}
        self.discharged_patients: List[Patient] = []
        self.deceased_patients: List[Patient] = []
        self.beds: Dict[str, Bed] = self._initialize_beds()
        self.staff: Dict[str, Staff] = self._initialize_staff()
        self.equipment: Dict[str, Equipment] = self._initialize_equipment()
        self.action_history: List[Dict] = []
        self.escalations: List[str] = []
        
        # DYNAMIC: Generate scenario based on task difficulty
        self._setup_dynamic_scenario(task)

        return self.state()

    def _initialize_beds(self) -> Dict[str, Bed]:
        """Initialize hospital beds"""
        beds = {}
        bed_id = 0
        for ward_type, count in self.config["total_beds"].items():
            for i in range(count):
                bed_id += 1
                bed_key = f"{ward_type.upper()}-{i+1}"
                beds[bed_key] = Bed(
                    id=bed_key,
                    ward_type=WardType(ward_type),
                    status="free",
                    has_monitor=(ward_type in ["icu", "isolation"]),
                    has_ventilator_support=(ward_type == "icu"),
                    has_isolation=(ward_type == "isolation"),
                )
        return beds

    def _initialize_staff(self) -> Dict[str, Staff]:
        """Initialize hospital staff"""
        staff = {}
        doctor_id = 0
        for i in range(self.config["staff"]["doctors"]):
            doctor_id += 1
            staff[f"D{doctor_id}"] = Staff(
                id=f"D{doctor_id}",
                role="doctor",
                specialty=random.choice(["emergency", "cardiology", "general"]),
                shift_hours_remaining=8.0,
                current_patient_load=random.randint(0, 3),
                max_patient_load=5,
            )

        nurse_id = 0
        for i in range(self.config["staff"]["nurses"]):
            nurse_id += 1
            staff[f"N{nurse_id}"] = Staff(
                id=f"N{nurse_id}",
                role="nurse",
                specialty="nursing",
                shift_hours_remaining=8.0,
                current_patient_load=random.randint(1, 4),
                max_patient_load=6,
            )

        return staff

    def _initialize_equipment(self) -> Dict[str, Equipment]:
        """Initialize hospital equipment"""
        equipment = {}
        vent_id = 0
        for i in range(self.config["equipment"]["ventilators"]):
            vent_id += 1
            equipment[f"VENT-{vent_id}"] = Equipment(
                id=f"VENT-{vent_id}",
                equipment_type="ventilator",
                status="available",
            )

        monitor_id = 0
        for i in range(self.config["equipment"]["monitors"]):
            monitor_id += 1
            equipment[f"MON-{monitor_id}"] = Equipment(
                id=f"MON-{monitor_id}",
                equipment_type="monitor",
                status="available",
            )

        return equipment

    def state(self) -> Dict[str, Any]:
        """Return current hospital state"""
        return {
            "step": self.step_count,
            "time": self.time,
            "beds": {
                ward_type.value: {
                    "total": sum(
                        1 for b in self.beds.values() if b.ward_type == ward_type
                    ),
                    "occupied": sum(
                        1
                        for b in self.beds.values()
                        if b.ward_type == ward_type and b.status == "occupied"
                    ),
                    "details": [
                        b.to_dict()
                        for b in self.beds.values()
                        if b.ward_type == ward_type
                    ],
                }
                for ward_type in WardType
            },
            "staff": {
                "doctors": [
                    s.to_dict()
                    for s in self.staff.values()
                    if s.role == "doctor"
                ],
                "nurses": [
                    s.to_dict()
                    for s in self.staff.values()
                    if s.role == "nurse"
                ],
            },
            "equipment": [e.to_dict() for e in self.equipment.values()],
            "pending_patients": [p.to_dict() for p in self.pending_patients],
            "admitted_patients": {
                pid: p.to_dict() for pid, p in self.admitted_patients.items()
            },
            "escalations": self.escalations,
        }

    def step(self, action: Dict[str, Any]) -> Tuple[Dict[str, Any], float, bool, Dict]:
        """Execute one step in the environment"""
        self.step_count += 1
        self.time += 1.0
        reward = 0.0
        info = {"action": action, "step": self.step_count}

        try:
            action_type = ActionType(action.get("type"))

            if action_type == ActionType.ASSIGN_BED:
                reward, action_info = self._handle_assign_bed(action)
            elif action_type == ActionType.ALLOCATE_STAFF:
                reward, action_info = self._handle_allocate_staff(action)
            elif action_type == ActionType.DISCHARGE_PATIENT:
                reward, action_info = self._handle_discharge_patient(action)
            elif action_type == ActionType.TRANSFER_PATIENT:
                reward, action_info = self._handle_transfer_patient(action)
            elif action_type == ActionType.REQUEST_EQUIPMENT:
                reward, action_info = self._handle_request_equipment(action)
            elif action_type == ActionType.ESCALATE_SHORTAGE:
                reward, action_info = self._handle_escalate_shortage(action)
            elif action_type == ActionType.SKIP:
                reward, action_info = 0.0, {"status": "skipped"}
            else:
                reward, action_info = -0.1, {"status": "invalid_action"}

            info.update(action_info)

        except Exception as e:
            reward = -0.2
            info["error"] = str(e)

        # Process environment dynamics
        self._update_patient_states()
        self._check_critical_patient_timeouts()
        
        # DYNAMIC: Simulate world changes each step
        self._simulate_step_dynamics()

        done = self.step_count >= self.config["max_steps"]
        state = self.state()

        return state, reward, done, info

    def _handle_assign_bed(self, action: Dict) -> Tuple[float, Dict]:
        """Handle bed assignment action"""
        reward = 0.0
        info = {"status": "bed_assignment"}

        patient_id = action.get("patient_id")
        bed_id = action.get("bed_id")

        if patient_id not in [p.id for p in self.pending_patients]:
            return -0.3, {**info, "error": "Patient not found"}

        patient = next(p for p in self.pending_patients if p.id == patient_id)

        if bed_id not in self.beds:
            return -0.3, {**info, "error": "Bed not found"}

        bed = self.beds[bed_id]

        if bed.status == "occupied":
            return -0.3, {**info, "error": "Bed already occupied"}

        # Check if bed type matches acuity
        required_ward = self._get_required_ward(patient.acuity)
        if bed.ward_type != required_ward:
            reward -= 0.2  # Penalty for wrong bed type
            info["warning"] = f"Suboptimal bed type: {bed.ward_type} for {patient.acuity}"

        # Assign bed
        bed.status = "occupied"
        bed.patient_id = patient_id
        patient.assigned_bed = bed_id
        patient.status = PatientStatus.ADMITTED
        patient.admitted_at = self.time

        self.pending_patients.remove(patient)
        self.admitted_patients[patient_id] = patient

        # Reward for correct priority order (critical patients first)
        reward += 0.25
        info["success"] = True

        self.action_history.append(
            {
                "type": "assign_bed",
                "patient_id": patient_id,
                "bed_id": bed_id,
                "reward": reward,
                "step": self.step_count,
            }
        )

        return reward, info

    def _handle_allocate_staff(self, action: Dict) -> Tuple[float, Dict]:
        """Handle staff allocation action"""
        reward = 0.0
        info = {"status": "staff_allocation"}

        staff_id = action.get("staff_id")
        patient_id = action.get("patient_id")

        if staff_id not in self.staff:
            return -0.2, {**info, "error": "Staff not found"}

        staff_member = self.staff[staff_id]

        if patient_id not in self.admitted_patients:
            return -0.2, {**info, "error": "Patient not admitted"}

        if staff_member.current_patient_load >= staff_member.max_patient_load:
            return -0.2, {**info, "error": "Staff overloaded"}

        staff_member.current_patient_load += 1
        reward += 0.2
        info["success"] = True

        self.action_history.append(
            {
                "type": "allocate_staff",
                "staff_id": staff_id,
                "patient_id": patient_id,
                "reward": reward,
                "step": self.step_count,
            }
        )

        return reward, info

    def _handle_discharge_patient(self, action: Dict) -> Tuple[float, Dict]:
        """Handle patient discharge action"""
        reward = 0.0
        info = {"status": "discharge"}

        patient_id = action.get("patient_id")

        if patient_id not in self.admitted_patients:
            return -0.3, {**info, "error": "Patient not admitted"}

        patient = self.admitted_patients[patient_id]

        # Safety check: don't discharge critical patients
        if patient.acuity == Acuity.CRITICAL and self.time - patient.admitted_at < 2.0:
            return -0.4, {**info, "error": "Cannot discharge critical patient too early"}

        # Free bed
        if patient.assigned_bed:
            bed = self.beds[patient.assigned_bed]
            bed.status = "free"
            bed.patient_id = None

        # Remove from admitted
        del self.admitted_patients[patient_id]
        patient.status = PatientStatus.DISCHARGED
        self.discharged_patients.append(patient)

        reward += 0.15
        info["success"] = True

        self.action_history.append(
            {
                "type": "discharge",
                "patient_id": patient_id,
                "reward": reward,
                "step": self.step_count,
            }
        )

        return reward, info

    def _handle_transfer_patient(self, action: Dict) -> Tuple[float, Dict]:
        """Handle patient transfer to different ward"""
        reward = 0.0
        info = {"status": "transfer"}

        patient_id = action.get("patient_id")
        new_bed_id = action.get("new_bed_id")

        if patient_id not in self.admitted_patients:
            return -0.3, {**info, "error": "Patient not admitted"}

        patient = self.admitted_patients[patient_id]

        if new_bed_id not in self.beds:
            return -0.3, {**info, "error": "New bed not found"}

        new_bed = self.beds[new_bed_id]

        if new_bed.status == "occupied":
            return -0.3, {**info, "error": "New bed already occupied"}

        # Free old bed
        if patient.assigned_bed:
            old_bed = self.beds[patient.assigned_bed]
            old_bed.status = "free"
            old_bed.patient_id = None

        # Assign new bed
        new_bed.status = "occupied"
        new_bed.patient_id = patient_id
        patient.assigned_bed = new_bed_id

        reward += 0.2
        info["success"] = True

        self.action_history.append(
            {
                "type": "transfer",
                "patient_id": patient_id,
                "old_bed": patient.assigned_bed,
                "new_bed": new_bed_id,
                "reward": reward,
                "step": self.step_count,
            }
        )

        return reward, info

    def _handle_request_equipment(self, action: Dict) -> Tuple[float, Dict]:
        """Handle equipment request"""
        reward = 0.0
        info = {"status": "equipment_request"}

        equipment_type = action.get("equipment_type")
        patient_id = action.get("patient_id")

        if patient_id not in self.admitted_patients:
            return -0.2, {**info, "error": "Patient not admitted"}

        # Find available equipment
        available_equipment = [
            e for e in self.equipment.values()
            if e.equipment_type == equipment_type and e.status == "available"
        ]

        if not available_equipment:
            return -0.1, {**info, "error": f"No {equipment_type} available"}

        equipment = available_equipment[0]
        equipment.status = "in_use"
        equipment.patient_id = patient_id

        reward += 0.15
        info["success"] = True
        info["equipment_id"] = equipment.id

        self.action_history.append(
            {
                "type": "request_equipment",
                "equipment_id": equipment.id,
                "patient_id": patient_id,
                "reward": reward,
                "step": self.step_count,
            }
        )

        return reward, info

    def _handle_escalate_shortage(self, action: Dict) -> Tuple[float, Dict]:
        """Handle escalation for resource shortage"""
        reward = 0.0
        info = {"status": "escalation"}

        shortage_type = action.get("shortage_type")  # "staff" or "beds"
        target = action.get("target")  # "admin" or "external"

        escalation_msg = f"Escalating {shortage_type} shortage to {target}"
        self.escalations.append(escalation_msg)

        reward += 0.1
        info["success"] = True
        info["escalation"] = escalation_msg

        self.action_history.append(
            {
                "type": "escalate",
                "shortage_type": shortage_type,
                "target": target,
                "reward": reward,
                "step": self.step_count,
            }
        )

        return reward, info

    def _get_required_ward(self, acuity: Acuity) -> WardType:
        """Determine required ward type for patient acuity"""
        if acuity == Acuity.CRITICAL:
            return WardType.ICU
        elif acuity == Acuity.SEVERE:
            return WardType.GENERAL
        elif acuity == Acuity.MODERATE:
            return WardType.GENERAL
        else:
            return WardType.GENERAL

    def _update_patient_states(self):
        """Update patient states based on time and care"""
        for patient_id, patient in list(self.admitted_patients.items()):
            # Simulate recovery
            time_admitted = self.time - patient.admitted_at
            if patient.acuity == Acuity.MINOR and time_admitted > 3:
                patient.status = PatientStatus.IN_RECOVERY
            elif patient.acuity == Acuity.MODERATE and time_admitted > 5:
                patient.status = PatientStatus.IN_RECOVERY
            elif patient.acuity == Acuity.SEVERE and time_admitted > 8:
                patient.status = PatientStatus.IN_RECOVERY

    def _check_critical_patient_timeouts(self):
        """Check if critical patients are waiting too long"""
        for patient in self.pending_patients:
            if patient.acuity == Acuity.CRITICAL:
                patient.critical_condition_time += 1.0

    def add_patient(self, condition: str, acuity: Acuity, requires_isolation: bool = False) -> Patient:
        """Add new patient to waiting list"""
        patient = Patient(
            id=f"P{len(self.pending_patients) + len(self.admitted_patients) + 1}",
            condition=condition,
            acuity=acuity,
            status=PatientStatus.WAITING,
            requires_isolation=requires_isolation,
            requires_ventilator=(acuity == Acuity.CRITICAL),
        )
        self.pending_patients.append(patient)
        return patient

    def _setup_dynamic_scenario(self, task: str):
        """Setup dynamic scenario based on task difficulty"""
        if task == "easy":
            self._setup_easy_scenario()
        elif task == "medium":
            self._setup_medium_scenario()
        elif task == "hard":
            self._setup_hard_scenario()
    
    def _setup_easy_scenario(self):
        """Setup easy task with 2-4 random patients"""
        num_patients = random.randint(2, 4)
        
        for i in range(num_patients):
            # Weighted randomization: more likely to be critical/severe in easy
            roll = random.random()
            if roll < 0.3:
                acuity = Acuity.CRITICAL
            elif roll < 0.7:
                acuity = Acuity.SEVERE
            else:
                acuity = Acuity.MODERATE
            
            condition = self._random_condition(acuity)
            self.add_patient(condition, acuity)
    
    def _setup_medium_scenario(self):
        """Setup medium task with resource conflicts"""
        # Pre-fill ICU with stable patients (60-95% full)
        icu_beds = [b for b in self.beds.values() if b.ward_type == WardType.ICU]
        icu_fill_ratio = random.uniform(0.6, 0.95)
        num_to_fill = int(len(icu_beds) * icu_fill_ratio)
        
        for i in range(num_to_fill):
            patient = self.add_patient(f"Post-surgery recovery {i}", Acuity.MODERATE)
            bed = icu_beds[i]
            bed.status = "occupied"
            bed.patient_id = patient.id
            patient.assigned_bed = bed.id
            patient.status = PatientStatus.ADMITTED
            patient.admitted_at = self.time
            self.pending_patients.remove(patient)
            self.admitted_patients[patient.id] = patient
        
        # Add 1-3 critical patients
        num_critical = random.randint(1, 3)
        for i in range(num_critical):
            condition = random.choice(["Myocardial Infarction", "Severe Trauma", "Stroke"])
            self.add_patient(condition, Acuity.CRITICAL)
        
        # Randomly break some equipment
        if random.random() < 0.3:
            ventilators = [e for e in self.equipment.values() if e.equipment_type == "ventilator"]
            for vent in ventilators[:random.randint(1, 2)]:
                vent.status = "broken"
    
    def _setup_hard_scenario(self):
        """Setup hard task with mass casualty event"""
        # Generate 10-20 random patients
        num_patients = random.randint(10, 20)
        
        # Ensure at least 2-3 critical patients
        critical_count = random.randint(2, 3)
        severe_count = random.randint(3, 5)
        minor_count = num_patients - critical_count - severe_count
        
        # Add critical patients
        for i in range(critical_count):
            condition = random.choice(["Severe Trauma", "Massive Hemorrhage", "Crush Injury"])
            self.add_patient(f"{condition} {i+1}", Acuity.CRITICAL)
        
        # Add severe patients
        for i in range(severe_count):
            condition = random.choice(["Pneumothorax", "Fracture", "Internal Bleeding"])
            self.add_patient(f"{condition} {i+1}", Acuity.SEVERE)
        
        # Add minor patients
        for i in range(minor_count):
            condition = random.choice(["Laceration", "Bruising", "Sprain"])
            self.add_patient(f"{condition} {i+1}", Acuity.MINOR)
        
        # Simulate staff shortage (remove 50% of staff)
        staff_list = list(self.staff.keys())
        for staff_id in staff_list[:len(staff_list)//2]:
            del self.staff[staff_id]
        
        # Break 1-3 ventilators
        ventilators = [e for e in self.equipment.values() if e.equipment_type == "ventilator"]
        num_break = random.randint(1, min(3, len(ventilators)))
        for vent in ventilators[:num_break]:
            vent.status = "broken"
    
    def _random_condition(self, acuity: Acuity) -> str:
        """Return random condition for acuity level"""
        conditions = {
            Acuity.CRITICAL: [
                "Sepsis", "Myocardial Infarction", "Severe Trauma",
                "Stroke", "Acute Respiratory Failure", "Hemorrhagic Shock"
            ],
            Acuity.SEVERE: [
                "Pneumonia", "Appendicitis", "Acute Pancreatitis",
                "Perforated Ulcer", "Meningitis", "Acute MI"
            ],
            Acuity.MODERATE: [
                "Broken Leg", "Laceration", "Gastroenteritis",
                "Kidney Stones", "Asthma Attack", "Migraine"
            ],
            Acuity.MINOR: [
                "Sprain", "Minor Cut", "Headache",
                "Common Cold", "Indigestion", "Minor Burn"
            ]
        }
        return random.choice(conditions[acuity])
    
    def _simulate_step_dynamics(self):
        """Simulate dynamic changes each step"""
        if self.current_task == "easy":
            # Low dynamics in easy task
            if random.random() < 0.1 and len(self.pending_patients) < 5:
                condition = self._random_condition(random.choice([Acuity.SEVERE, Acuity.MODERATE]))
                self.add_patient(condition, random.choice([Acuity.SEVERE, Acuity.MODERATE]))
        
        elif self.current_task == "medium":
            # Medium dynamics
            if random.random() < 0.15 and len(self.pending_patients) < 8:
                acuity = random.choice([Acuity.CRITICAL, Acuity.SEVERE, Acuity.MODERATE])
                condition = self._random_condition(acuity)
                self.add_patient(condition, acuity)
            
            # Random staff becoming unavailable
            if random.random() < 0.08 and len(self.staff) > 6:
                staff_id = random.choice(list(self.staff.keys()))
                self.staff[staff_id].shift_hours_remaining -= random.uniform(1, 2)
                if self.staff[staff_id].shift_hours_remaining <= 0:
                    del self.staff[staff_id]
        
        elif self.current_task == "hard":
            # High dynamics in hard task
            if random.random() < 0.25 and len(self.pending_patients) < 15:
                acuity = random.choice([Acuity.CRITICAL, Acuity.SEVERE, Acuity.MODERATE, Acuity.MINOR])
                condition = self._random_condition(acuity)
                self.add_patient(condition, acuity)
            
            # Random staff changes
            if random.random() < 0.12 and len(self.staff) > 4:
                staff_id = random.choice(list(self.staff.keys()))
                self.staff[staff_id].shift_hours_remaining -= random.uniform(0.5, 1.5)
                if self.staff[staff_id].shift_hours_remaining <= 0:
                    del self.staff[staff_id]
            
            # Random equipment failure
            if random.random() < 0.05:
                available_equipment = [e for e in self.equipment.values() if e.status == "available"]
                if available_equipment:
                    equipment = random.choice(available_equipment)
                    equipment.status = "broken"

    def get_stats(self) -> Dict[str, Any]:
        """Get environment statistics"""
        total_beds = len(self.beds)
        occupied_beds = sum(1 for b in self.beds.values() if b.status == "occupied")
        icu_beds = sum(1 for b in self.beds.values() if b.ward_type == WardType.ICU)
        icu_occupied = sum(
            1 for b in self.beds.values() if b.ward_type == WardType.ICU and b.status == "occupied"
        )

        return {
            "total_beds": total_beds,
            "occupied_beds": occupied_beds,
            "available_beds": total_beds - occupied_beds,
            "icu_beds": icu_beds,
            "icu_occupied": icu_occupied,
            "icu_available": icu_beds - icu_occupied,
            "pending_patients": len(self.pending_patients),
            "admitted_patients": len(self.admitted_patients),
            "discharged_patients": len(self.discharged_patients),
            "deceased_patients": len(self.deceased_patients),
            "critical_wait_time": max(
                [p.critical_condition_time for p in self.pending_patients]
                if self.pending_patients
                else [0]
            ),
        }
