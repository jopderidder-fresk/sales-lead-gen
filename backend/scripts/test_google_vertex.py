#!/usr/bin/env python3
"""Quick smoke test for Google Vertex AI LLM integration.

Standalone — requires pydantic-ai[google] and google-auth packages (no database needed).

Run from the backend directory:
    python3 scripts/test_google_vertex.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_ai import Agent

# Load .env from project root
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "")
KEY_PATH = os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY_PATH", "")
KEY_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY_JSON", "")
PROJECT_ID = os.getenv("GOOGLE_VERTEX_PROJECT_ID", "")
LOCATION = os.getenv("GOOGLE_VERTEX_LOCATION", "europe-west1")
FAST_MODEL = os.getenv("GOOGLE_VERTEX_FAST_MODEL", "gemini-2.5-flash")
STRONG_MODEL = os.getenv("GOOGLE_VERTEX_STRONG_MODEL", FAST_MODEL)


# --- Output models ---

class SignalClassification(BaseModel):
    signal_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class ExtractedCompany(BaseModel):
    name: str
    domain: str | None = None
    industry: str | None = None
    description: str | None = None


class CompaniesResult(BaseModel):
    companies: list[ExtractedCompany] = Field(default_factory=list)


def build_model(model_name: str):
    from google.oauth2.service_account import Credentials as ServiceAccountCredentials
    from pydantic_ai.models.google import GoogleModel
    from pydantic_ai.providers.google import GoogleProvider

    scopes = ["https://www.googleapis.com/auth/cloud-platform"]

    if KEY_JSON:
        info = json.loads(KEY_JSON)
        credentials = ServiceAccountCredentials.from_service_account_info(info, scopes=scopes)
    elif KEY_PATH:
        # Resolve relative to project root
        resolved = os.path.join(os.path.dirname(__file__), "..", "..", KEY_PATH)
        credentials = ServiceAccountCredentials.from_service_account_file(resolved, scopes=scopes)
    else:
        print("ERROR: GOOGLE_SERVICE_ACCOUNT_KEY_PATH or GOOGLE_SERVICE_ACCOUNT_KEY_JSON must be set")
        sys.exit(1)

    # Auto-detect project ID from credentials if not explicitly set
    project_id = PROJECT_ID or credentials.project_id

    provider = GoogleProvider(
        credentials=credentials,
        project=project_id or None,
        location=LOCATION,
    )
    return GoogleModel(model_name, provider=provider)


async def test_classify_signal(model) -> bool:
    print("=" * 60)
    print("TEST 1: classify_signal (fast model)")
    print("=" * 60)

    system_prompt = (
        "You are a B2B sales intelligence analyst. Classify web content as a buying signal type. "
        "Signal types: hiring_surge, technology_adoption, digital_transformation, "
        "workforce_challenge, funding_round, leadership_change, "
        "expansion, partnership, product_launch, no_signal."
    )
    agent = Agent(model, output_type=SignalClassification, instructions=system_prompt)

    content = (
        "Company context: Acme Corp — B2B SaaS, 50-200 employees\n\n"
        "Content to classify:\n"
        "We're growing fast! We have 15 open engineering positions "
        "including Senior Engineers, DevOps, and Data Scientists.\n\n"
        "Classify this content."
    )

    try:
        result = await agent.run(content)
        r = result.output
        print(f"  signal_type:  {r.signal_type}")
        print(f"  confidence:   {r.confidence}")
        print(f"  reasoning:    {r.reasoning}")
        print(f"  tokens:       {result.usage()}")
        print("  PASS")
        return True
    except Exception as exc:
        print(f"  FAIL: {exc}")
        import traceback
        traceback.print_exc()
        return False


async def test_extract_companies(model) -> bool:
    print("=" * 60)
    print("TEST 2: extract_companies (fast model)")
    print("=" * 60)

    system_prompt = (
        "You are a B2B data extraction specialist. Extract company names and domains "
        "from search result text. Return a companies array."
    )
    agent = Agent(model, output_type=CompaniesResult, instructions=system_prompt)

    content = (
        "Extract all companies from the following:\n\n"
        "TechFlow BV (techflow.io) provides cloud monitoring for DevOps teams. "
        "ScaleSoft offers HR software for SMBs at scalesoft.com. "
        "DataPulse raised €5M Series A (datapulse.io) — analytics for e-commerce."
    )

    try:
        result = await agent.run(content)
        companies = result.output.companies
        print(f"  found {len(companies)} companies:")
        for c in companies:
            print(f"    - {c.name} ({c.domain}) [{c.industry}]")
        print(f"  tokens:       {result.usage()}")
        print("  PASS")
        return True
    except Exception as exc:
        print(f"  FAIL: {exc}")
        import traceback
        traceback.print_exc()
        return False


async def main() -> None:
    print(f"Provider:     google_vertex")
    print(f"Location:     {LOCATION}")
    print(f"Fast model:   {FAST_MODEL}")
    print(f"Strong model: {STRONG_MODEL}")
    print(f"Key file:     {KEY_PATH or '(from JSON env var)'}")
    print()

    fast_model = build_model(FAST_MODEL)

    results = []
    results.append(await test_classify_signal(fast_model))
    print()
    results.append(await test_extract_companies(fast_model))
    print()

    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} passed")

    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
