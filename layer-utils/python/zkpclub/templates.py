import json

from enum import Enum
from typing import Dict, Optional
from dataclasses import dataclass, field, asdict


#@dataclass
#class ApplicationStatus(Enum):
#    idle = 'idle'
#    processing = 'processing'
#    accepted = 'accepted'
#    rejected = 'rejected'


@dataclass
class TelegramUser:
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None
    avatar_url: Optional[str] = None # Аватарка из телеграма, ссылка вида talagram_<id>.<extension>


@dataclass
class UserData:
    avatar_url: str  # Аватарка, загруженная пользвоателем, ссыдка вида <id>.<extension>
    full_name: str
    phone: str
    sites_links: str
    social_links: str
    achievements: str
    bio: Optional[str] = None


@dataclass
class Application:
    status: str = "idle"  # processing, accepted, rejected
    message_id: Optional[int] = None  # Message in group chat, with vote buttons
    message_timestamp: Optional[int] = None  # Message timestamp (we can't edit message older than 24 hours)
    data: Optional[UserData] = None
    positive_reviews: Dict[int, str] = field(default_factory=dict)
    negative_reviews: Dict[int, str] = field(default_factory=dict)


@dataclass
class DatabaseUser:
    user_id: int
    telegram_user: TelegramUser
    application: Application = Application()

def from_json(database_user: json) -> DatabaseUser:
    return DatabaseUser(
        user_id=database_user["user_id"],
        telegram_user=TelegramUser(**database_user["telegram_user"]),
        application=Application(**database_user["application"]),
    )

def to_json(database_user: DatabaseUser) -> json:
    return asdict(database_user)
