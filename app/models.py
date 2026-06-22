import re
from pydantic import BaseModel, field_validator
from typing import Optional, List, Dict


class SignupRequest(BaseModel):
    email: str
    password: str
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if not re.match(r'^[a-zA-Z\s]+$', v):
            raise ValueError("Name must only contain letters and spaces")
        return v.strip()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        if not re.search(r'[A-Z]', v):
            raise ValueError("Password must contain at least 1 uppercase letter")
        if not re.search(r'\d', v):
            raise ValueError("Password must contain at least 1 number")
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{};:\'\"\\|,.<>\/?]', v):
            raise ValueError("Password must contain at least 1 special character")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    token: str
    userId: str
    name: str
    email: str
    role: str


class MedicationCreate(BaseModel):
    name: str
    dosage: str


class MedicationResponse(BaseModel):
    medicationId: str
    name: str
    dosage: str
    createdAt: str


class EntryCreate(BaseModel):
    type: str
    value: float
    unit: str
    notes: Optional[str] = None
    timestamp: Optional[str] = None
    medicationId: Optional[str] = None


class EntryResponse(BaseModel):
    entryId: str
    userId: str
    type: str
    value: float
    unit: str
    notes: Optional[str] = None
    medicationId: Optional[str] = None
    medicationName: Optional[str] = None
    timestamp: str
    createdAt: str


class DashboardResponse(BaseModel):
    todayEntries: List[EntryResponse]
    todayCounts: Dict[str, int]
    latestGlucose: Optional[float] = None
    latestGlucoseUnit: Optional[str] = None
    latestGlucoseTime: Optional[str] = None


class UserResponse(BaseModel):
    userId: str
    name: str
    email: str
    role: str
    createdAt: str


class ResourceResponse(BaseModel):
    resourceId: str
    name: str
    fileType: str
    fileSize: int
    uploadedBy: str
    uploadedAt: str
    downloadCount: int
    description: str
