from pydantic import BaseModel

from app.classes.models import LlmSettings, PostData


class WritePostRequest(BaseModel):
    userId: int
    llmSettings: LlmSettings
    keyword: str
    jobId: str


class UploadPostRequest(BaseModel):
    userId: int
    post: PostData
