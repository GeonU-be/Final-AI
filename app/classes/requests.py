from pydantic import BaseModel

from app.classes.models import LlmSettings, UploadChannelSettings


class WritePostRequest(BaseModel):
    userId: int
    llmSettings: LlmSettings
    uploadChannels: UploadChannelSettings
    keyword: str
    jobId: str


class UploadPostRequest(BaseModel):
    userId: int
    jobId: str
    title: str
    body: str
    keyword: str
    channelName: str
