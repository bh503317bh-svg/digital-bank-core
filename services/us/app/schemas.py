from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    mobile: str = Field(min_length=11, max_length=20)
    password: str = Field(min_length=6, max_length=64)
    display_name: str = ""
    role: str = "customer"
    pay_password: str = Field(default="123456", min_length=4, max_length=12)


class LoginRequest(BaseModel):
    mobile: str
    password: str


class PayPasswordVerify(BaseModel):
    pay_password: str = Field(min_length=4, max_length=12)


class PayPasswordSet(BaseModel):
    login_password: str = Field(min_length=6, max_length=64)
    new_pay_password: str = Field(min_length=4, max_length=12)


class TokenData(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int
    mobile: str
    display_name: str


class UserOut(BaseModel):
    id: int
    mobile: str
    role: str
    display_name: str

    class Config:
        from_attributes = True
