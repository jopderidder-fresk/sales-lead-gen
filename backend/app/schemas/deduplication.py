from pydantic import BaseModel, Field


class DuplicateCheckRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    domain: str = Field(min_length=1, max_length=255)


class SimilarCompanyMatch(BaseModel):
    company_id: int
    name: str
    domain: str
    domain_match: bool
    name_similarity: float


class SimilarCompaniesResponse(BaseModel):
    matches: list[SimilarCompanyMatch]


class DuplicateGroupMember(BaseModel):
    company_id: int
    name: str
    domain: str
    domain_match: bool | None = None
    name_similarity: float | None = None


class DuplicateGroup(BaseModel):
    companies: list[DuplicateGroupMember]


class DuplicateScanResponse(BaseModel):
    groups: list[DuplicateGroup]
    total_groups: int


class MergeRequest(BaseModel):
    primary_id: int
    duplicate_id: int
