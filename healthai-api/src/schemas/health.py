from pydantic import BaseModel
from typing import Union, Dict, Any

class InternalHealthResponse(BaseModel):
    gateway: str
    vision_service: Union[Dict[str, Any], str]
    workout_service: Union[Dict[str, Any], str]

class StatusResponse(BaseModel):
    status: str
    message: str