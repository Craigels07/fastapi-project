from pydantic import BaseModel, validator
from typing import Dict, Any, Optional


class WhatsAppMessageBase(BaseModel):
    From: str
    To: str
    Body: str
    MessageSid: str
    ProfileName: Optional[str] = None
    WaId: Optional[str] = None
    NumMedia: Optional[int] = 0
    SmsMessageSid: Optional[str] = None
    MessageType: Optional[str] = None
    SmsSid: Optional[str] = None
    SmsStatus: Optional[str] = None
    NumSegments: Optional[int] = None
    ReferralNumMedia: Optional[int] = None
    AccountSid: Optional[str] = None
    ApiVersion: Optional[str] = None

    @validator("NumMedia", "NumSegments", "ReferralNumMedia", pre=True)
    def convert_str_to_int(cls, v):
        try:
            return int(v)
        except (ValueError, TypeError):
            return 0
