#!/usr/bin/env python3
"""Quick smoke test for the LLM service via OpenRouter.

Standalone — only requires pydantic-ai and openai packages (no database needed).

Run from the backend directory:
    python3 scripts/test_llm.py
"""

from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

# Load .env from project root
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "minimax/minimax-m2.5:free")

if not OPENROUTER_API_KEY:
    print("ERROR: OPENROUTER_API_KEY not set in .env")
    sys.exit(1)


# --- Output models (same as app/services/llm/base.py) ---

class SignalClassification(BaseModel):
    signal_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str

class ScoreAndRecommendation(BaseModel):
    relevance_score: int = Field(ge=0, le=100)
    action: str
    reasoning: str
    key_factors: list[str] = Field(default_factory=list)

class ExtractedCompany(BaseModel):
    name: str
    domain: str | None = None
    industry: str | None = None
    description: str | None = None

class CompaniesResult(BaseModel):
    companies: list[ExtractedCompany] = Field(default_factory=list)

class ExtractedContact(BaseModel):
    name: str
    title: str | None = None
    email: str | None = None
    linkedin_url: str | None = None

class ContactsResult(BaseModel):
    contacts: list[ExtractedContact] = Field(default_factory=list)


def build_model():
    return OpenAIChatModel(
        OPENROUTER_MODEL,
        provider=OpenAIProvider(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
        ),
    )


async def test_classify_signal(model) -> bool:
    print("=" * 60)
    print("TEST 1: classify_signal")
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
        return False


async def test_score_and_recommend(model) -> bool:
    print("=" * 60)
    print("TEST 2: score_and_recommend")
    print("=" * 60)

    system_prompt = (
        "You are a B2B sales intelligence analyst. Score signal relevance (0-100) "
        "and recommend an action: notify_immediate (75+), notify_digest (50-74), "
        "enrich_further (25-49), ignore (<25). List up to 5 key factors."
    )
    agent = Agent(model, output_type=ScoreAndRecommendation, instructions=system_prompt)

    content = (
        "Signal type: hiring_surge\n"
        "Company: Acme Corp — B2B SaaS, 50-200 employees, Amsterdam\n"
        "ICP: SaaS companies, 50-500 employees, Netherlands/Germany, cloud-native stack\n\n"
        "Signal content:\n"
        "We just posted 20 new engineering roles including Platform Engineers and SREs.\n\n"
        "Score this signal and recommend an action."
    )

    try:
        result = await agent.run(content)
        r = result.output
        print(f"  score:        {r.relevance_score}")
        print(f"  action:       {r.action}")
        print(f"  reasoning:    {r.reasoning}")
        print(f"  key_factors:  {r.key_factors}")
        print(f"  tokens:       {result.usage()}")
        print("  PASS")
        return True
    except Exception as exc:
        print(f"  FAIL: {exc}")
        return False


async def test_extract_companies(model) -> bool:
    print("=" * 60)
    print("TEST 3: extract_companies")
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
        return False


async def test_extract_contacts(model) -> bool:
    print("=" * 60)
    print("TEST 4: extract_contacts")
    print("=" * 60)

    system_prompt = (
        "You are a B2B data extraction specialist. Extract people and their contact "
        "information from company team or about pages. Return a contacts array."
    )
    agent = Agent(model, output_type=ContactsResult, instructions=system_prompt)

    content = (
        "Extract all people from the following page:\n\n"
        "Meet our leadership team:\n"
        "Jane Doe — CTO, jane@acme.com\n"
        "John Smith — VP Engineering, https://linkedin.com/in/johnsmith\n"
        "Sarah Connor — Head of Product"
    )

    try:
        result = await agent.run(content)
        contacts = result.output.contacts
        print(f"  found {len(contacts)} contacts:")
        for c in contacts:
            print(f"    - {c.name} ({c.title}) email={c.email} linkedin={c.linkedin_url}")
        print(f"  tokens:       {result.usage()}")
        print("  PASS")
        return True
    except Exception as exc:
        print(f"  FAIL: {exc}")
        return False


async def main() -> None:
    print(f"Provider: OpenRouter")
    print(f"Model:    {OPENROUTER_MODEL}")
    print(f"API Key:  {OPENROUTER_API_KEY[:12]}...{OPENROUTER_API_KEY[-4:]}")
    print()

    model = build_model()
    results = []

    results.append(await test_classify_signal(model))
    print()
    results.append(await test_score_and_recommend(model))
    print()
    results.append(await test_extract_companies(model))
    print()
    results.append(await test_extract_contacts(model))
    print()

    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} passed")

    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
