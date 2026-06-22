from fastapi import APIRouter, HTTPException
from app.models import SignupRequest, LoginRequest, AuthResponse
from app.database import create_user, get_user_by_email
from app.auth import hash_password, verify_password, create_token
import uuid

router = APIRouter()


@router.post("/signup", response_model=AuthResponse)
async def signup(body: SignupRequest):
    existing = get_user_by_email(body.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    user_id = str(uuid.uuid4())
    pw_hash = hash_password(body.password)
    create_user(user_id, body.email, body.name, pw_hash, role="user")
    token = create_token(user_id, body.email, role="user")
    return AuthResponse(token=token, userId=user_id, name=body.name, email=body.email, role="user")


@router.post("/login", response_model=AuthResponse)
async def login(body: LoginRequest):
    user = get_user_by_email(body.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not verify_password(body.password, user["passwordHash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    role = user.get("role", "user")
    token = create_token(user["PK"].replace("USER#", ""), user["email"], role=role)
    return AuthResponse(
        token=token,
        userId=user["PK"].replace("USER#", ""),
        name=user["name"],
        email=user["email"],
        role=role,
    )
