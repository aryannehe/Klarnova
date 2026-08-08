
from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None
    role: str | None = None

class User(BaseModel):
    username: str
    role: str # Admin, Engineer, Viewer
    
class UserInDB(User):
    hashed_password: str
