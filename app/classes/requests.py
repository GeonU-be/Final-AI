from dataclasses import dataclass
from app.classes.models import LlmSettings, PostData


@dataclass
class WritePostRequest:
    userId: int
    llmSettings: LlmSettings
    keywords: list[str]
    jobId: str


@dataclass
class UploadPostRequest:
    userId: int
    post: PostData
