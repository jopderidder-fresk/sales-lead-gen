from pydantic import BaseModel


class JobInfo(BaseModel):
    name: str
    enabled: bool
    schedule: str
    description: str


class JobsResponse(BaseModel):
    jobs: list[JobInfo]


class JobToggle(BaseModel):
    enabled: bool
