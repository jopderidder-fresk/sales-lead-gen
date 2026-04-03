from fastapi import APIRouter

from app.api.v1.analytics import router as analytics_router
from app.api.v1.api_keys import router as api_keys_router
from app.api.v1.audit_log import router as audit_log_router
from app.api.v1.auth import router as auth_router
from app.api.v1.clickup import router as clickup_router
from app.api.v1.companies import router as companies_router
from app.api.v1.contacts import router as contacts_router
from app.api.v1.crm import router as crm_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.discovery import router as discovery_router
from app.api.v1.icp_profiles import router as icp_profiles_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.lead_scores import router as lead_scores_router
from app.api.v1.linkedin import router as linkedin_router
from app.api.v1.prompt_config import router as prompt_config_router
from app.api.v1.signals import router as signals_router
from app.api.v1.slack import router as slack_router
from app.api.v1.usage_limits import router as usage_limits_router

router = APIRouter(prefix="/api/v1")

router.include_router(analytics_router)
router.include_router(api_keys_router)
router.include_router(audit_log_router)
router.include_router(auth_router)
router.include_router(clickup_router)
router.include_router(companies_router)
router.include_router(contacts_router)
router.include_router(crm_router)
router.include_router(dashboard_router)
router.include_router(lead_scores_router)
router.include_router(discovery_router)
router.include_router(icp_profiles_router)
router.include_router(jobs_router)
router.include_router(linkedin_router)
router.include_router(prompt_config_router)
router.include_router(signals_router)
router.include_router(slack_router)
router.include_router(usage_limits_router)
