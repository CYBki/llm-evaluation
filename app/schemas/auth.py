from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RegisterResponse(BaseModel):
    user_id: str
    email: EmailStr
    api_key: str
    api_key_prefix: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    user_id: str
    email: EmailStr
    api_key_prefix: str
    message: str = "Login successful. Use your existing API key to authenticate."
