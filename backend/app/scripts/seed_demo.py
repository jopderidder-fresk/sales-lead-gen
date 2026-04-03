"""Seed the database with demo companies for user testing.

Usage:
    python -m app.scripts.seed_demo
"""

import asyncio
from typing import Any

from sqlalchemy import select, update

from app.core.database import async_session_factory
from app.models.company import Company
from app.models.contact import Contact
from app.models.enums import (
    CompanyStatus,
    EmailStatus,
    SignalAction,
    SignalType,
)
from app.models.icp_profile import ICPProfile
from app.models.signal import Signal

DEMO_COMPANIES: list[dict[str, Any]] = [
    {
        "company": {
            "name": "Hertek",
            "domain": "hertek.nl",
            "industry": "Fire Protection & Industrial Safety",
            "size": "200-500",
            "location": "Ridderkerk, Netherlands",
            "icp_score": 82.0,
            "status": CompanyStatus.ENRICHED,
        },
        "contacts": [
            {
                "name": "Mark de Vries",
                "title": "Chief Technology Officer",
                "email": "m.devries@hertek.nl",
                "email_status": EmailStatus.VERIFIED,
                "linkedin_url": "https://linkedin.com/in/markdevries-hertek",
                "source": "apollo",
                "confidence_score": 0.92,
            },
            {
                "name": "Sandra Jansen",
                "title": "Head of Digital Transformation",
                "email": "s.jansen@hertek.nl",
                "email_status": EmailStatus.CATCH_ALL,
                "linkedin_url": "https://linkedin.com/in/sandrajansen",
                "source": "linkedin",
                "confidence_score": 0.85,
            },
        ],
        "signals": [
            {
                "source_url": "https://hertek.nl/nieuws/uitbreiding-smart-monitoring",
                "signal_type": SignalType.TECHNOLOGY_ADOPTION,
                "relevance_score": 0.88,
                "llm_summary": (
                    "Hertek is investing in IoT-based smart monitoring for fire "
                    "suppression systems across industrial sites. They announced a "
                    "partnership with a sensor platform vendor, signalling openness "
                    "to new technology integrations."
                ),
                "action_taken": SignalAction.NOTIFY_IMMEDIATE,
                "is_processed": True,
            },
            {
                "source_url": "https://hertek.nl/nieuws/hertek-groeit-verder",
                "signal_type": SignalType.EXPANSION,
                "relevance_score": 0.72,
                "llm_summary": (
                    "Hertek opened a new branch in Eindhoven to serve the Brainport "
                    "region. Headcount grew 15% year-over-year, indicating active "
                    "scaling and potential budget for new tooling."
                ),
                "action_taken": SignalAction.NOTIFY_DIGEST,
                "is_processed": True,
            },
        ],
    },
    {
        "company": {
            "name": "Rocsys",
            "domain": "rocsys.com",
            "industry": "Robotics & Autonomous Charging",
            "size": "50-100",
            "location": "Rijswijk, Netherlands",
            "icp_score": 91.0,
            "status": CompanyStatus.QUALIFIED,
        },
        "contacts": [
            {
                "name": "Crijn Bouman",
                "title": "CEO & Co-founder",
                "email": "crijn@rocsys.com",
                "email_status": EmailStatus.VERIFIED,
                "linkedin_url": "https://linkedin.com/in/crijnbouman",
                "source": "apollo",
                "confidence_score": 0.97,
            },
            {
                "name": "Lisa van der Berg",
                "title": "VP of Engineering",
                "email": "lisa@rocsys.com",
                "email_status": EmailStatus.VERIFIED,
                "linkedin_url": "https://linkedin.com/in/lisavdberg-rocsys",
                "source": "linkedin",
                "confidence_score": 0.90,
            },
        ],
        "signals": [
            {
                "source_url": "https://rocsys.com/news/series-b-funding",
                "signal_type": SignalType.FUNDING_ROUND,
                "relevance_score": 0.95,
                "llm_summary": (
                    "Rocsys closed a Series B round, raising capital to scale "
                    "autonomous robotic charging for electric vehicle fleets. "
                    "The funding will accelerate R&D and commercial deployment, "
                    "creating demand for supporting software and integrations."
                ),
                "action_taken": SignalAction.NOTIFY_IMMEDIATE,
                "is_processed": True,
            },
            {
                "source_url": "https://rocsys.com/news/hiring-engineering",
                "signal_type": SignalType.HIRING_SURGE,
                "relevance_score": 0.80,
                "llm_summary": (
                    "Rocsys posted 12 new engineering roles in the past month, "
                    "including software engineers and DevOps positions. Rapid "
                    "hiring suggests scaling their tech stack and potential need "
                    "for developer tooling."
                ),
                "action_taken": SignalAction.ENRICH_FURTHER,
                "is_processed": True,
            },
        ],
    },
    {
        "company": {
            "name": "Wasco",
            "domain": "wasco.nl",
            "industry": "Industrial Distribution",
            "size": "500-1000",
            "location": "Netherlands",
            "icp_score": 72.0,
            "status": CompanyStatus.ENRICHED,
        },
        "contacts": [
            {
                "name": "Wasco",
                "title": "General Contact",
                "phone": "+31880995000",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "BDR Thermea Group",
            "domain": "bdrthermeagroup.com",
            "industry": "HVAC & Heating Equipment",
            "size": "1000+",
            "location": "Apeldoorn, Netherlands",
            "icp_score": 78.0,
            "status": CompanyStatus.ENRICHED,
        },
        "contacts": [
            {
                "name": "BDR Thermea Group",
                "title": "General Contact",
                "phone": "+31555496969",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Archello",
            "domain": "archello.com",
            "industry": "Architecture & Design Platform",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 65.0,
            "status": CompanyStatus.ENRICHED,
        },
        "contacts": [
            {
                "name": "Archello",
                "title": "General Contact",
                "phone": "+31356993055",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Stork",
            "domain": "stork.com",
            "industry": "Industrial Services & Maintenance",
            "size": "500-1000",
            "location": "Netherlands",
            "icp_score": 74.0,
            "status": CompanyStatus.ENRICHED,
        },
        "contacts": [
            {
                "name": "Stork",
                "title": "General Contact",
                "phone": "+31880891000",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Climate for life",
            "domain": "climateforlife.nl",
            "industry": "HVAC & Climate Solutions",
            "size": "200-500",
            "location": "Netherlands",
            "icp_score": 80.0,
            "status": CompanyStatus.ENRICHED,
        },
        "contacts": [
            {
                "name": "Climate for life",
                "title": "General Contact",
                "phone": "+31884275300",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Cooll",
            "domain": "cooll.com",
            "industry": "Heat Pump Technology",
            "size": "100-200",
            "location": "Netherlands",
            "icp_score": 70.0,
            "status": CompanyStatus.ENRICHED,
        },
        "contacts": [
            {
                "name": "Cooll",
                "title": "General Contact",
                "phone": "+18005517788",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Nijman/Zeetank International Logistic Group",
            "domain": "nijman-zeetank.com",
            "industry": "Freight & Tank Transport",
            "size": "50-100",
            "location": "Netherlands",
            "icp_score": 62.0,
            "status": CompanyStatus.ENRICHED,
        },
        "contacts": [
            {
                "name": "Nijman/Zeetank International Logistic Group",
                "title": "General Contact",
                "phone": "+31181691900",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "BlueHeart Energy",
            "domain": "blueheartenergy.com",
            "industry": "Energy Technology",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 68.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "BlueHeart Energy",
                "title": "General Contact",
                "phone": "+31851302380",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "School Terminals",
            "domain": "koole.com",
            "industry": "Tank Terminals & Storage",
            "size": "100-200",
            "location": "Zaandam, Netherlands",
            "icp_score": 60.0,
            "status": CompanyStatus.ENRICHED,
        },
        "contacts": [
            {
                "name": "School Terminals",
                "title": "General Contact",
                "phone": "+31756812812",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Techniek College Rotterdam",
            "domain": "techniekcollegerotterdam.nl",
            "industry": "Technical Education",
            "size": "100-200",
            "location": "Rotterdam, Netherlands",
            "icp_score": 55.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Techniek College Rotterdam",
                "title": "General Contact",
                "phone": "+31889454500",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Aalberts N.V.",
            "domain": "aalberts.com",
            "industry": "Industrial Technology",
            "size": "1000+",
            "location": "Utrecht, Netherlands",
            "icp_score": 75.0,
            "status": CompanyStatus.ENRICHED,
        },
        "contacts": [
            {
                "name": "Aalberts N.V.",
                "title": "General Contact",
                "phone": "+31303079300",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Deerns",
            "domain": "deerns.com",
            "industry": "Engineering Consultancy",
            "size": "100-200",
            "location": "Netherlands",
            "icp_score": 76.0,
            "status": CompanyStatus.ENRICHED,
        },
        "contacts": [
            {
                "name": "Deerns",
                "title": "General Contact",
                "phone": "+31883740000",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Quatt",
            "domain": "quatt.io",
            "industry": "Heat Pump Technology",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 85.0,
            "status": CompanyStatus.ENRICHED,
        },
        "contacts": [
            {
                "name": "Quatt",
                "title": "General Contact",
                "phone": "+31851300622",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Regionaal Energieloket",
            "domain": "regionaalenergieloket.nl",
            "industry": "Energy Advisory",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 58.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Regionaal Energieloket",
                "title": "General Contact",
                "phone": "+31885254110",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Chapter",
            "domain": "chapter.works",
            "industry": "Industrial Technology",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 72.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [],
        "signals": [],
    },
    {
        "company": {
            "name": "Tarnoc",
            "domain": "tarnoc.nl",
            "industry": "Industrial Technology",
            "size": "10-50",
            "location": "Delft, Netherlands",
            "icp_score": 65.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Tarnoc",
                "title": "General Contact",
                "phone": "+31152024110",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Ventinova Medical",
            "domain": "ventinovamedical.com",
            "industry": "Medical Technology",
            "size": "10-50",
            "location": "Eindhoven, Netherlands",
            "icp_score": 58.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Ventinova Medical",
                "title": "General Contact",
                "phone": "+31407516020",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "HeatLeap",
            "domain": "heatleap.nl",
            "industry": "Heat Pump Technology",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 78.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [],
        "signals": [],
    },
    {
        "company": {
            "name": "Incooling",
            "domain": "incooling.com",
            "industry": "Cooling Technology",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 70.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Incooling",
                "title": "General Contact",
                "phone": "+31623462039",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "SUPER LOGISTICS SYSTEM BV",
            "domain": "superlogisticsystem.com",
            "industry": "International Logistics",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 48.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "SUPER LOGISTICS SYSTEM BV",
                "title": "General Contact",
                "phone": "+19293995882",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "ITC Holland Transport B.V.",
            "domain": "itchollandtransport.nl",
            "industry": "Transport & Logistics",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 55.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "ITC Holland Transport B.V.",
                "title": "General Contact",
                "phone": "+31412664230",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "BUILDING technology",
            "domain": "buildingtechnology.nl",
            "industry": "Building Technology & Installations",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 62.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "BUILDING technology",
                "title": "General Contact",
                "phone": "+31571262728",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "PCV Group",
            "domain": "pcvgroup.com",
            "industry": "Industrial Measurement & Control",
            "size": "10-50",
            "location": "Almelo, Netherlands",
            "icp_score": 66.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "PCV Group",
                "title": "General Contact",
                "phone": "+31534342624",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Cegelec Fire Solutions",
            "domain": "cegelec.nl",
            "industry": "Fire Safety Solutions",
            "size": "50-100",
            "location": "Netherlands",
            "icp_score": 68.0,
            "status": CompanyStatus.ENRICHED,
        },
        "contacts": [
            {
                "name": "Cegelec Fire Solutions",
                "title": "General Contact",
                "phone": "+31888319696",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Zantingh BV",
            "domain": "zantingh.com",
            "industry": "Industrial Equipment",
            "size": "10-50",
            "location": "Purmerend, Netherlands",
            "icp_score": 60.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Zantingh BV",
                "title": "General Contact",
                "phone": "+31297219100",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "ROVC Technische Opleidingen",
            "domain": "rovc.nl",
            "industry": "Technical Training",
            "size": "50-100",
            "location": "Netherlands",
            "icp_score": 52.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "ROVC Technische Opleidingen",
                "title": "General Contact",
                "phone": "+31318698698",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Mupa Schakeltechniek",
            "domain": "mupa.nl",
            "industry": "Electrical Switching Technology",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 64.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Mupa Schakeltechniek",
                "title": "General Contact",
                "phone": "+31497514496",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Van Gooi",
            "domain": "vangooi.com",
            "industry": "Electrical Installations",
            "size": "10-50",
            "location": "Hilversum, Netherlands",
            "icp_score": 63.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Van Gooi",
                "title": "General Contact",
                "phone": "+31353031900",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Frans de Wit International B.V.",
            "domain": "fransdewit.nl",
            "industry": "International Bulk Logistics",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 55.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Frans de Wit International B.V.",
                "title": "General Contact",
                "phone": "+31168387070",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Energiebespaarders",
            "domain": "energiebespaarders.nl",
            "industry": "Energy Savings",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 60.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Energiebespaarders",
                "title": "General Contact",
                "phone": "+31852103977",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    # --- New companies below ---
    {
        "company": {
            "name": "GIGA Storage",
            "domain": "giga-storage.com",
            "industry": "Energy Services",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 75.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "GIGA Storage",
                "title": "General Contact",
                "phone": "+31202157787",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Hotraco Agri",
            "domain": "hotraco-agri.com",
            "industry": "Industrial Measurement & Control",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 70.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Hotraco Agri",
                "title": "General Contact",
                "phone": "+31773275020",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Mark Climate Technology",
            "domain": "markclimate.com",
            "industry": "HVAC & Refrigeration",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 75.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Mark Climate Technology",
                "title": "General Contact",
                "phone": "+31598656612",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "IJskoud BV",
            "domain": "ijskoud.nl",
            "industry": "HVAC & Refrigeration",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 72.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [],
        "signals": [],
    },
    {
        "company": {
            "name": "PCT Refrigeration",
            "domain": "pct.nl",
            "industry": "HVAC & Refrigeration",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 73.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "PCT Refrigeration",
                "title": "General Contact",
                "phone": "+31493319217",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Climanova",
            "domain": "climanova.com",
            "industry": "Electrical Installations",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 65.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Climanova",
                "title": "General Contact",
                "phone": "+31117492442",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Magneto",
            "domain": "magneto.systems",
            "industry": "Industrial Equipment",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 65.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [],
        "signals": [],
    },
    {
        "company": {
            "name": "Manuel",
            "domain": "manuel.chat",
            "industry": "AI & Software",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 58.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Manuel",
                "title": "General Contact",
                "phone": "+31543227272",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Equans Nederland",
            "domain": "equans.nl",
            "industry": "Electrical Installations",
            "size": "1000+",
            "location": "Netherlands",
            "icp_score": 70.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Equans Nederland",
                "title": "General Contact",
                "phone": "+31617366509",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Bonarius Bedrijven",
            "domain": "bonarius.com",
            "industry": "HVAC & Refrigeration",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 70.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Bonarius Bedrijven",
                "title": "General Contact",
                "phone": "+31204074900",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Inatherm",
            "domain": "inatherm.nl",
            "industry": "HVAC & Refrigeration",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 72.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Inatherm",
                "title": "General Contact",
                "phone": "+31416317830",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "HC KP | Klimaatplafonds",
            "domain": "hckp.nl",
            "industry": "Electrical Installations",
            "size": "100-200",
            "location": "Netherlands",
            "icp_score": 72.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "HC KP | Klimaatplafonds",
                "title": "General Contact",
                "phone": "+31416650075",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Berko Kompressoren",
            "domain": "berko.eu",
            "industry": "Industrial Equipment",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 68.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Berko Kompressoren",
                "title": "General Contact",
                "phone": "+31246411111",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "USP Marketing Consultancy",
            "domain": "usp-research.com",
            "industry": "Market Research",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 48.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "USP Marketing Consultancy",
                "title": "General Contact",
                "phone": "+31102066900",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Coolmark B.V.",
            "domain": "coolmark.nl",
            "industry": "HVAC Distribution",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 70.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Coolmark B.V.",
                "title": "General Contact",
                "phone": "+31888830300",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Royal Imtech N.V",
            "domain": "imtech.com",
            "industry": "Electrical Installations",
            "size": "1000+",
            "location": "Netherlands",
            "icp_score": 72.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Royal Imtech N.V",
                "title": "General Contact",
                "phone": "+31182543543",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Aqualectra B.V.",
            "domain": "aqualectra.nl",
            "industry": "Electrical Equipment",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 65.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [],
        "signals": [],
    },
    {
        "company": {
            "name": "Martinair",
            "domain": "martinair.com",
            "industry": "Aviation & Transport",
            "size": "100-200",
            "location": "Netherlands",
            "icp_score": 48.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Martinair",
                "title": "General Contact",
                "phone": "+13057049800",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Van Halteren Technologies",
            "domain": "vanhalteren.com",
            "industry": "Industrial Equipment",
            "size": "100-200",
            "location": "Netherlands",
            "icp_score": 72.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Van Halteren Technologies",
                "title": "General Contact",
                "phone": "+31332992300",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Saman Groep",
            "domain": "samangroep.nl",
            "industry": "Electrical Installations",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 66.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Saman Groep",
                "title": "General Contact",
                "phone": "+31436080377",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "TBK",
            "domain": "t-b-k.nl",
            "industry": "Electrical Installations",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 65.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "TBK",
                "title": "General Contact",
                "phone": "+318000817",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Tameson",
            "domain": "tameson.com",
            "industry": "Industrial Distribution",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 62.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Tameson",
                "title": "General Contact",
                "phone": "+31407505795",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Technisch buro Pola B.V.",
            "domain": "pola.nl",
            "industry": "Electrical Installations",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 65.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Technisch buro Pola B.V.",
                "title": "General Contact",
                "phone": "+31316524351",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Y-con B.V.",
            "domain": "y-con.nl",
            "industry": "HVAC & Refrigeration",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 70.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Y-con B.V.",
                "title": "General Contact",
                "phone": "+31135784320",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Royal Brinkman",
            "domain": "royalbrinkman.nl",
            "industry": "Agricultural Supplies",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 58.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Royal Brinkman",
                "title": "General Contact",
                "phone": "+31174446100",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "MedicomZes",
            "domain": "medicomzes.nl",
            "industry": "Engineering Consultancy",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 68.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "MedicomZes",
                "title": "General Contact",
                "phone": "+31206966886",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Verkerk",
            "domain": "verkerk.com",
            "industry": "Electrical Installations",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 64.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Verkerk",
                "title": "General Contact",
                "phone": "+31786107700",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "VDK Groep",
            "domain": "vdkgroep.com",
            "industry": "Electrical Installations",
            "size": "1000+",
            "location": "Netherlands",
            "icp_score": 70.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "VDK Groep",
                "title": "General Contact",
                "phone": "+31384223253",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "GCE-GROUP B.V.",
            "domain": "gce-group.nl",
            "industry": "Electrical Installations",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 64.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "GCE-GROUP B.V.",
                "title": "General Contact",
                "phone": "+31655108700",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Dophou",
            "domain": "dophou.nl",
            "industry": "Electrical Installations",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 64.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Dophou",
                "title": "General Contact",
                "phone": "+31102064000",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Altena Group",
            "domain": "altena.com",
            "industry": "Industrial Equipment",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 65.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Altena Group",
                "title": "General Contact",
                "phone": "+31416670700",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "ThermoNoord",
            "domain": "thermonoord.nl",
            "industry": "HVAC Distribution",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 68.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [],
        "signals": [],
    },
    {
        "company": {
            "name": "Delta Electronics EMEA",
            "domain": "delta-emea.com",
            "industry": "Electrical Equipment",
            "size": "500-1000",
            "location": "Netherlands",
            "icp_score": 72.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Delta Electronics EMEA",
                "title": "General Contact",
                "phone": "+31208003900",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Omexom NL",
            "domain": "omexom.nl",
            "industry": "Energy Services",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 72.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Omexom NL",
                "title": "General Contact",
                "phone": "+31888319625",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Arkitech",
            "domain": "arkitech.eu",
            "industry": "Maritime Engineering",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 62.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [],
        "signals": [],
    },
    {
        "company": {
            "name": "TIBN Groep",
            "domain": "tibn.nl",
            "industry": "Electrical Installations",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 65.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "TIBN Groep",
                "title": "General Contact",
                "phone": "+31343431644",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Dynobend",
            "domain": "dynobend.com",
            "industry": "Industrial Tools",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 65.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Dynobend",
                "title": "General Contact",
                "phone": "+31538507730",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "SpeedComfort",
            "domain": "speedcomfort.com",
            "industry": "Consumer Products",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 62.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [],
        "signals": [],
    },
    {
        "company": {
            "name": "Celsias BV",
            "domain": "celsias.nl",
            "industry": "Industrial Equipment",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 70.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Celsias BV",
                "title": "General Contact",
                "phone": "+31886068500",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Bookabus",
            "domain": "bookabus.eu",
            "industry": "Transportation",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 45.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Bookabus",
                "title": "General Contact",
                "phone": "+31858883875",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "QwikSense",
            "domain": "qwiksense.com",
            "industry": "HVAC Installations",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 72.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "QwikSense",
                "title": "General Contact",
                "phone": "+31621280192",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "IM Efficiency",
            "domain": "imefficiency.com",
            "industry": "Automotive Technology",
            "size": "50-100",
            "location": "Netherlands",
            "icp_score": 60.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "IM Efficiency",
                "title": "General Contact",
                "phone": "+31850861355",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "SoundEnergy",
            "domain": "soundenergy.nl",
            "industry": "Electrical Equipment",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 70.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "SoundEnergy",
                "title": "General Contact",
                "phone": "+31621885489",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "JB Besturingstechniek",
            "domain": "jbbesturingstechniek.nl",
            "industry": "Control Systems Engineering",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 72.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "JB Besturingstechniek",
                "title": "General Contact",
                "phone": "+31492747500",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "PT Operations BV",
            "domain": "pt-o.nl",
            "industry": "HVAC & Refrigeration",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 70.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "PT Operations BV",
                "title": "General Contact",
                "phone": "+31234567890",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "PPD Invest",
            "domain": "ppd-invest.com",
            "industry": "Business Services",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 48.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [],
        "signals": [],
    },
    {
        "company": {
            "name": "LIMO'S EXCLUSIVE DRIVING",
            "domain": "limos.nl",
            "industry": "Vehicle Rental",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 42.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [],
        "signals": [],
    },
    {
        "company": {
            "name": "Verduurzaam met gemak",
            "domain": "verduurzaammetgemak.nl",
            "industry": "Electrical Installations",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 65.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Verduurzaam met gemak",
                "title": "General Contact",
                "phone": "+31610808089",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Microfan",
            "domain": "microfan.com",
            "industry": "Industrial Measurement & Control",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 68.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Microfan",
                "title": "General Contact",
                "phone": "+31495632926",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Green Heating Solutions",
            "domain": "greenheatingsolutions.nl",
            "industry": "HVAC & Refrigeration",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 74.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Green Heating Solutions",
                "title": "General Contact",
                "phone": "+31725729794",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "deBusSpecialist",
            "domain": "debusspecialist.nl",
            "industry": "Transportation",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 45.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "deBusSpecialist",
                "title": "General Contact",
                "phone": "+31886557788",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Jouwopleiding",
            "domain": "jouwopleiding.nl",
            "industry": "Electrical Installations",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 58.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Jouwopleiding",
                "title": "General Contact",
                "phone": "+31854011328",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Sterk Technisch Adviesbureau B.V.",
            "domain": "sterk.com",
            "industry": "Industrial Equipment",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 66.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Sterk Technisch Adviesbureau B.V.",
                "title": "General Contact",
                "phone": "+31183624118",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Klimaat Techniek Industrie",
            "domain": "klimaattechniekindustrie.nl",
            "industry": "HVAC & Refrigeration",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 72.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [],
        "signals": [],
    },
    {
        "company": {
            "name": "Technical Education Centre (T.E.C.)",
            "domain": "tecopleidingen.nl",
            "industry": "Research & Development",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 55.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [],
        "signals": [],
    },
    {
        "company": {
            "name": "Jonker Travel B.V.",
            "domain": "jonkertravel.nl",
            "industry": "Transportation",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 45.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [],
        "signals": [],
    },
    {
        "company": {
            "name": "Florijn Chauffeurs B.V.",
            "domain": "florijntours.nl",
            "industry": "Transportation",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 45.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Florijn Chauffeurs B.V.",
                "title": "General Contact",
                "phone": "+31852738233",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "DG Luxury Tours",
            "domain": "dglt.nl",
            "industry": "Vehicle Rental",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 42.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "DG Luxury Tours",
                "title": "General Contact",
                "phone": "+31657980213",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "DKI Group",
            "domain": "dki-group.nl",
            "industry": "Industrial Distribution",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 62.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [],
        "signals": [],
    },
    {
        "company": {
            "name": "MSC European Truck & Trailer Care Coevorden",
            "domain": "msc-bv.com",
            "industry": "Vehicle Services",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 48.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "MSC European Truck & Trailer Care Coevorden",
                "title": "General Contact",
                "phone": "+31524596584",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Verkeersschool Lei Wolters",
            "domain": "leiwolters.nl",
            "industry": "Vehicle Rental",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 42.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Verkeersschool Lei Wolters",
                "title": "General Contact",
                "phone": "+31475531787",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Prestige Taxicentrale",
            "domain": "rataxutrecht.nl",
            "industry": "Transportation",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 45.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Prestige Taxicentrale",
                "title": "General Contact",
                "phone": "+31302875050",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Roadservice de Kempen BV",
            "domain": "roadservicedekempen.nl",
            "industry": "Vehicle Services",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 48.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Roadservice de Kempen BV",
                "title": "General Contact",
                "phone": "+31497382160",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "GBSO",
            "domain": "gbso.nl",
            "industry": "Industrial Equipment",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 65.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "GBSO",
                "title": "General Contact",
                "phone": "+31183634744",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Blockchain Realisten",
            "domain": "blockchainrealisten.nl",
            "industry": "IT Services",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 55.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [],
        "signals": [],
    },
    {
        "company": {
            "name": "Stubbe Logistiek",
            "domain": "stubbelogistiek.nl",
            "industry": "Logistics",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 48.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Stubbe Logistiek",
                "title": "General Contact",
                "phone": "+31638184174",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Autobusbedrijf Doornbos",
            "domain": "doornbus.nl",
            "industry": "Transportation",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 45.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Autobusbedrijf Doornbos",
                "title": "General Contact",
                "phone": "+31503129412",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "CaTeC bv",
            "domain": "catec.nl",
            "industry": "Industrial Measurement & Control",
            "size": "50-100",
            "location": "Netherlands",
            "icp_score": 70.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "CaTeC bv",
                "title": "General Contact",
                "phone": "+31174792739",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Top Installatiegroep",
            "domain": "topinstallatiegroep.nl",
            "industry": "Electrical Installations",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 65.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Top Installatiegroep",
                "title": "General Contact",
                "phone": "+31528220555",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Interland Techniek BV",
            "domain": "interlandtechniek.nl",
            "industry": "HVAC & Refrigeration",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 70.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Interland Techniek BV",
                "title": "General Contact",
                "phone": "+31416317830",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Airvek Airconditioning",
            "domain": "airvek.nl",
            "industry": "HVAC & Refrigeration",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 72.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Airvek Airconditioning",
                "title": "General Contact",
                "phone": "+31104376766",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "CMK Luchttechniek b.v.",
            "domain": "cmk-luchttechniek.nl",
            "industry": "HVAC & Refrigeration",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 72.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "CMK Luchttechniek b.v.",
                "title": "General Contact",
                "phone": "+31355249000",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Blinkr.eu",
            "domain": "blinkr.eu",
            "industry": "Management Consultancy",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 50.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Blinkr.eu",
                "title": "General Contact",
                "phone": "+31852463888",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Boels Rental",
            "domain": "boels.com",
            "industry": "Equipment Rental",
            "size": "1000+",
            "location": "Netherlands",
            "icp_score": 55.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [],
        "signals": [],
    },
    {
        "company": {
            "name": "Schoonmaakbedrijf Prinsen B.V.",
            "domain": "schoonmaakbedrijfprinsen.nl",
            "industry": "Facility Services",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 48.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Schoonmaakbedrijf Prinsen B.V.",
                "title": "General Contact",
                "phone": "+31653982394",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Ergin Birinci Studio",
            "domain": "erginbirinci.com",
            "industry": "Architecture",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 45.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [],
        "signals": [],
    },
    {
        "company": {
            "name": "Dryfast",
            "domain": "dryfast.eu",
            "industry": "HVAC & Refrigeration",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 70.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Dryfast",
                "title": "General Contact",
                "phone": "+31104261410",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Xibeo B.V.",
            "domain": "xibeo.nl",
            "industry": "Electrical Installations",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 65.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Xibeo B.V.",
                "title": "General Contact",
                "phone": "+31880242000",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Chainless B.V.",
            "domain": "chainless.nl",
            "industry": "IT Services",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 58.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Chainless B.V.",
                "title": "General Contact",
                "phone": "+31878709448",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Quantum MC",
            "domain": "fitzgeraldsgroup.com",
            "industry": "Electrical Installations",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 62.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [],
        "signals": [],
    },
    {
        "company": {
            "name": "IT Building B.V.",
            "domain": "itbuilding.nl",
            "industry": "IT Services",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 58.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "IT Building B.V.",
                "title": "General Contact",
                "phone": "+31202441797",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "SCM Group Nederland B.V.",
            "domain": "scmgroup-webshop.nl",
            "industry": "Industrial Equipment",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 65.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "SCM Group Nederland B.V.",
                "title": "General Contact",
                "phone": "+31756478478",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "VBoptimum",
            "domain": "vboptimum.com",
            "industry": "Engineering Consultancy",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 68.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [],
        "signals": [],
    },
    {
        "company": {
            "name": "Bettink Regeltechniek B.V.",
            "domain": "bettinkregeltechniek.nl",
            "industry": "Electrical Installations",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 68.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Bettink Regeltechniek B.V.",
                "title": "General Contact",
                "phone": "+31342701064",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "VaComTec",
            "domain": "vacomtec.nl",
            "industry": "Electrical Installations",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 65.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [],
        "signals": [],
    },
    {
        "company": {
            "name": "ETIM INTERNATIONAL",
            "domain": "etim-international.com",
            "industry": "Engineering Consultancy",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 65.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "ETIM INTERNATIONAL",
                "title": "General Contact",
                "phone": "+13852400444",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "C&R Hospitality Services",
            "domain": "crhs.nl",
            "industry": "Engineering Consultancy",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 65.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "C&R Hospitality Services",
                "title": "General Contact",
                "phone": "+31651661682",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "InstaCon B.V.",
            "domain": "instacon.nl",
            "industry": "Engineering Consultancy",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 66.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [],
        "signals": [],
    },
    {
        "company": {
            "name": "RemoteControlroom.com",
            "domain": "remotecontrolroom.com",
            "industry": "Research & Development",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 60.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [],
        "signals": [],
    },
    {
        "company": {
            "name": "HORNBACH Bouwmarkt",
            "domain": "hornbach.nl",
            "industry": "Retail & Distribution",
            "size": "50-100",
            "location": "Netherlands",
            "icp_score": 45.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [],
        "signals": [],
    },
    {
        "company": {
            "name": "Bommelweg B.V.",
            "domain": "bommelweg.com",
            "industry": "Construction Services",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 52.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Bommelweg B.V.",
                "title": "General Contact",
                "phone": "+31857430065",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Aarts Koeltechniek B.V.",
            "domain": "aartskoeltechniek.nl",
            "industry": "HVAC & Refrigeration",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 72.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [],
        "signals": [],
    },
    {
        "company": {
            "name": "VD grootkeuken advies & ontwerp",
            "domain": "vd-grootkeuken-advies.nl",
            "industry": "Electrical Installations",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 60.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "VD grootkeuken advies & ontwerp",
                "title": "General Contact",
                "phone": "+31615187103",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Pure Partners",
            "domain": "purepartners.co",
            "industry": "Engineering Consultancy",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 65.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [],
        "signals": [],
    },
    {
        "company": {
            "name": "Totaal Gebouwbeheer BV",
            "domain": "totaalgebouwbeheer.nl",
            "industry": "Electrical Installations",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 64.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Totaal Gebouwbeheer BV",
                "title": "General Contact",
                "phone": "+31723034000",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Interface FM Europe",
            "domain": "interfacefm.com",
            "industry": "Business Services",
            "size": "50-100",
            "location": "Italy",
            "icp_score": 48.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Interface FM Europe",
                "title": "General Contact",
                "phone": "+390278624488",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Kristal Real Estate",
            "domain": "kristalrealestate.nl",
            "industry": "Real Estate",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 42.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Kristal Real Estate",
                "title": "General Contact",
                "phone": "+31306362268",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Installatie.nl",
            "domain": "installatie.nl",
            "industry": "Construction Services",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 58.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Installatie.nl",
                "title": "General Contact",
                "phone": "+31857991272",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Bosch the Netherlands",
            "domain": "bosch.nl",
            "industry": "Electrical Equipment",
            "size": "1000+",
            "location": "Netherlands",
            "icp_score": 75.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Bosch the Netherlands",
                "title": "General Contact",
                "phone": "+31332479160",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "VEVATEC",
            "domain": "vevatec.nl",
            "industry": "Electrical Installations",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 65.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "VEVATEC",
                "title": "General Contact",
                "phone": "+31854011938",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Next Real Estate B.V.",
            "domain": "nextrealestate.nl",
            "industry": "Real Estate",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 42.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [],
        "signals": [],
    },
    {
        "company": {
            "name": "Vedotec B.V.",
            "domain": "vedotec.nl",
            "industry": "HVAC & Refrigeration",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 70.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Vedotec B.V.",
                "title": "General Contact",
                "phone": "+31888336800",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Delta Digital",
            "domain": "deltadigital.nl",
            "industry": "IT Solutions",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 58.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [],
        "signals": [],
    },
    {
        "company": {
            "name": "C&R Group B.V.",
            "domain": "cleaning-renovatie.com",
            "industry": "Construction Services",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 52.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "C&R Group B.V.",
                "title": "General Contact",
                "phone": "+31416690116",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "KE GrowAir",
            "domain": "ke-growair.nl",
            "industry": "HVAC & Refrigeration",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 72.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [],
        "signals": [],
    },
    {
        "company": {
            "name": "Prophysics",
            "domain": "prophysics.nl",
            "industry": "IT Services",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 58.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [],
        "signals": [],
    },
    {
        "company": {
            "name": "Werken bij VABI Software BV",
            "domain": "werkenbijvabi.nl",
            "industry": "IT Services",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 60.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Werken bij VABI Software BV",
                "title": "General Contact",
                "phone": "+31152574420",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "King Environmental Services",
            "domain": "kesgroup.ie",
            "industry": "Engineering Consultancy",
            "size": "10-50",
            "location": "Ireland",
            "icp_score": 62.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "King Environmental Services",
                "title": "General Contact",
                "phone": "+35318418955",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Bergstrom Koeltechniek",
            "domain": "bergstromkoeltechniek.nl",
            "industry": "HVAC Distribution",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 70.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Bergstrom Koeltechniek",
                "title": "General Contact",
                "phone": "+31570613001",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "insmart",
            "domain": "insmart.nl",
            "industry": "Electrical Equipment",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 65.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "insmart",
                "title": "General Contact",
                "phone": "+31307116545",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "AYF B.V",
            "domain": "allyourfacilities.nl",
            "industry": "Business Services",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 48.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "AYF B.V",
                "title": "General Contact",
                "phone": "+31850606754",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Techniekwerkt.nl",
            "domain": "techniekwerkt.nl",
            "industry": "IT Services",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 58.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Techniekwerkt.nl",
                "title": "General Contact",
                "phone": "+31320293800",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "TA Control Systems BV",
            "domain": "tacontrol.nl",
            "industry": "Industrial Equipment",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 68.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "TA Control Systems BV",
                "title": "General Contact",
                "phone": "+31850601188",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
    {
        "company": {
            "name": "Energiedamwand Nederland",
            "domain": "energie-damwanden.nl",
            "industry": "Infrastructure Construction",
            "size": "10-50",
            "location": "Netherlands",
            "icp_score": 62.0,
            "status": CompanyStatus.DISCOVERED,
        },
        "contacts": [
            {
                "name": "Energiedamwand Nederland",
                "title": "General Contact",
                "phone": "+31365370333",
                "source": "apollo",
                "confidence_score": 0.60,
            },
        ],
        "signals": [],
    },
]


DEMO_ICP_PROFILE: dict[str, Any] = {
    "name": "fresk.digital ICP - Field Service & Frontline Workers NL",
    "industry_filter": [
        "Technical Maintenance & Service",
        "Installation & Building Technology",
        "HVAC & Climate Technology",
        "Fire Protection & Industrial Safety",
        "Elevator & Escalator Services",
        "Testing, Inspection & Certification",
        "Industrial Services & Field Engineering",
        "Insurance & Claims Processing",
        "Agricultural Supply Chain & Trading",
        "Cooling & Refrigeration Technology",
        "Heat Pump Technology",
        "Electrical Installations",
        "Facility Management",
    ],
    "size_filter": {"min_employees": 100, "max_employees": 5000},
    "geo_filter": {"countries": ["Netherlands"], "regions": ["Western Europe"]},
    "tech_filter": [
        "ERP",
        "CRM",
        "FSM",
        "IoT",
        "SAP",
        "Salesforce",
        "Microsoft Dynamics",
        "ServiceNow",
    ],
    "negative_filters": {
        "excluded_industries": [
            "Education",
            "Retail",
            "Hospitality",
            "Media & Entertainment",
        ],
    },
    "is_active": True,
}


async def seed_demo_companies() -> None:
    async with async_session_factory() as session:
        # Seed ICP profile
        existing_icp = await session.execute(
            select(ICPProfile).where(
                ICPProfile.name == DEMO_ICP_PROFILE["name"]
            )
        )
        if existing_icp.scalar_one_or_none() is None:
            # Deactivate any existing active profile before inserting the new one
            # (the unique index ix_icp_profiles_single_active allows only one active row)
            await session.execute(
                update(ICPProfile)
                .where(ICPProfile.is_active == True)  # noqa: E712
                .values(is_active=False)
            )
            session.add(ICPProfile(**DEMO_ICP_PROFILE))
            print(f"Seeded ICP profile: '{DEMO_ICP_PROFILE['name']}'")
        else:
            print(f"ICP profile '{DEMO_ICP_PROFILE['name']}' exists — skipping.")

        # Seed companies
        for entry in DEMO_COMPANIES:
            company_data: dict[str, Any] = entry["company"]

            # Skip if company already exists (same name + domain)
            result = await session.execute(
                select(Company).where(
                    Company.name == company_data["name"],
                    Company.domain == company_data["domain"],
                )
            )
            if result.scalar_one_or_none() is not None:
                name = company_data["name"]
                print(f"Company '{name}' already exists — skipping.")
                continue

            company = Company(**company_data)
            session.add(company)
            await session.flush()  # get company.id

            for contact_data in entry["contacts"]:
                session.add(Contact(company_id=company.id, **contact_data))

            for signal_data in entry["signals"]:
                session.add(Signal(company_id=company.id, **signal_data))

            n_contacts = len(entry["contacts"])
            n_signals = len(entry["signals"])
            name = company_data["name"]
            print(
                f"Seeded '{name}' "
                f"with {n_contacts} contacts and {n_signals} signals."
            )

        await session.commit()
    print("Done.")


def main() -> None:
    asyncio.run(seed_demo_companies())


if __name__ == "__main__":
    main()
