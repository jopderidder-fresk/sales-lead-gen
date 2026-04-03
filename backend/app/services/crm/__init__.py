"""CRM provider factory — builds the configured CRM provider from settings."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.api.clickup import ClickUpClient
from app.services.crm.clickup_provider import PERSON_FIELD_KEYS, ClickUpCRMProvider
from app.services.crm.protocol import CRMProvider


def build_crm_provider(
    *,
    provider_name: str | None = None,
    clickup_api_key: str | None = None,
    clickup_list_id: str | None = None,
    clickup_domain_field_id: str | None = None,
    clickup_person_fields: dict[str, str] | None = None,
) -> CRMProvider | None:
    """Build the configured CRM provider.

    When called without arguments, reads from the in-memory ``settings``
    singleton.  Callers that need DB-persisted values (e.g. Celery tasks)
    should use :func:`build_crm_provider_from_db` instead.
    """
    provider = provider_name if provider_name is not None else settings.crm_provider
    if provider == "clickup":
        api_key = clickup_api_key or settings.clickup_api_key
        list_id = clickup_list_id or settings.clickup_list_id
        if not api_key or not list_id:
            return None
        client = ClickUpClient(api_key=api_key, list_id=list_id)
        domain_fid = clickup_domain_field_id if clickup_domain_field_id is not None else settings.clickup_domain_field_id
        pf = clickup_person_fields or {}
        person_fields = {
            k: pf.get(k) or getattr(settings, f"clickup_{k}", "")
            for k in PERSON_FIELD_KEYS
        }
        return ClickUpCRMProvider(
            client=client,
            domain_field_id=domain_fid,
            person_fields=person_fields,
        )

    # Future providers go here as elif branches.
    return None


async def build_crm_provider_from_db(session: AsyncSession) -> CRMProvider | None:
    """Build the CRM provider using DB-persisted settings with env var fallback.

    Use this in Celery tasks so workers pick up admin changes without a restart.
    """
    from app.core.app_settings_store import get_encrypted_setting, get_setting

    provider_name = await get_setting(session, "crm.provider") or settings.crm_provider
    if provider_name == "clickup":
        api_key = await get_encrypted_setting(session, "crm.clickup.api_key") or settings.clickup_api_key
        list_id = await get_setting(session, "crm.clickup.list_id") or settings.clickup_list_id
        domain_field_id = await get_setting(session, "crm.clickup.domain_field_id") or settings.clickup_domain_field_id

        person_fields: dict[str, str] = {}
        for k in PERSON_FIELD_KEYS:
            person_fields[k] = str(
                await get_setting(session, f"crm.clickup.{k}")
                or getattr(settings, f"clickup_{k}", "")
            )

        return build_crm_provider(
            provider_name="clickup",
            clickup_api_key=api_key,
            clickup_list_id=list_id,
            clickup_domain_field_id=domain_field_id,
            clickup_person_fields=person_fields,
        )

    return None
