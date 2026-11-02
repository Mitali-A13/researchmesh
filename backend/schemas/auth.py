from pydantic import BaseModel, Field, EmailStr


class SignupRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    success: bool
    access_token: str
    token_type: str


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=6, max_length=100)
    new_password: str = Field(..., min_length=6, max_length=100)


class UserProfile(BaseModel):
    id: int
    name: str
    email: str


class MeResponse(BaseModel):
    success: bool
    user: UserProfile
