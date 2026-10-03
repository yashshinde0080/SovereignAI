from fastapi import APIRouter, HTTPException, Query, Request
from .schemas import (
    GeneralSettings,
    AgentConfig,
    PersonalizationSettings,
    DataControlsSettings,
    SecuritySettings,
    ParentalControlsSettings,
    ProjectSettings,
    SettingsUpdateResponse,
)

from .service import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])

service = SettingsService()


async def _broadcast_settings_changed(section: str):
    """Poke existing /ws/metrics clients so the UI refetches settings.

    Reuses the metrics socket — no second WebSocket endpoint.
    """
    try:
        from app.websocket.metrics import clients, broadcast_metrics
        await broadcast_metrics({"type": "settings_changed", "section": section})
        _ = clients  # imported for parity; broadcast_metrics owns delivery
    except Exception:
        pass  # settings save must not fail because no UI is listening


# ──────────────────────────────────────────────
# FULL SETTINGS
# ──────────────────────────────────────────────

@router.get("/")
async def get_all_settings():
    """Get all settings including agents."""
    return service.get_full_settings()


@router.post("/reset", response_model=SettingsUpdateResponse)
async def reset_all_settings(request: Request):
    """Reset all settings to defaults."""
    success = service.reset_all_settings()
    if success:
        await _broadcast_settings_changed("all")
    return SettingsUpdateResponse(
        success=success,
        message="All settings reset to defaults" if success else "Reset failed",
        updated_section="all"
    )


# ──────────────────────────────────────────────
# GENERAL
# ──────────────────────────────────────────────

@router.get("/general")
async def get_general_settings():
    return service.get_general()


@router.put("/general", response_model=SettingsUpdateResponse)
async def update_general_settings(request: Request, settings: GeneralSettings):
    success = service.update_general(settings)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save general settings")

    # Engine-affecting: if the configured startup model/mode now differs from
    # what's loaded, reload. Refuse while a generation is in flight.
    if request.app.state.active_model is not None:
        target = settings.startup_model
        if target and (
            target != request.app.state.active_model
            or settings.default_mode != request.app.state.active_mode
        ):
            if getattr(request.app.state.active_engine, "is_generating", False):
                raise HTTPException(
                    status_code=409,
                    detail="Model reload blocked: generation in progress. Try again when idle.",
                )
            try:
                await request.app.state.model_manager.load_model(
                    target, mode=settings.default_mode
                )
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Settings saved but startup model reload failed: {e}",
                )

    await _broadcast_settings_changed("general")
    return SettingsUpdateResponse(
        success=True,
        message="General settings updated",
        updated_section="general"
    )


# ──────────────────────────────────────────────
# PERSONALIZATION
# ──────────────────────────────────────────────

@router.get("/personalization")
async def get_personalization_settings():
    return service.get_personalization()


@router.put("/personalization", response_model=SettingsUpdateResponse)
async def update_personalization_settings(settings: PersonalizationSettings):
    success = service.update_personalization(settings)
    if success:
        await _broadcast_settings_changed("personalization")
    return SettingsUpdateResponse(
        success=success,
        message="Personalization settings updated" if success else "Update failed",
        updated_section="personalization"
    )


@router.get("/system-prompt")
async def get_system_prompt():
    """Get the constructed system prompt from personalization + active agent."""
    prompt = service.get_system_prompt()
    return {"system_prompt": prompt}


# ──────────────────────────────────────────────
# DATA CONTROLS
# ──────────────────────────────────────────────

@router.get("/data-controls")
async def get_data_controls():
    return service.get_data_controls()


@router.put("/data-controls", response_model=SettingsUpdateResponse)
async def update_data_controls(settings: DataControlsSettings):
    success = service.update_data_controls(settings)
    if success:
        await _broadcast_settings_changed("data_controls")
    return SettingsUpdateResponse(
        success=success,
        message="Data controls updated" if success else "Update failed",
        updated_section="data_controls"
    )


# ──────────────────────────────────────────────
# SECURITY
# ──────────────────────────────────────────────

@router.get("/security")
async def get_security_settings():
    data = service.get_security()
    # Never return password hash to frontend
    data.pop("password_hash", None)
    return data


@router.put("/security", response_model=SettingsUpdateResponse)
async def update_security_settings(request: Request, settings: SecuritySettings):
    success = service.update_security(settings)
    if success:
        await _broadcast_settings_changed("security")
    return SettingsUpdateResponse(
        success=success,
        message="Security settings updated (port/binding changes need a server restart)" if success else "Update failed",
        updated_section="security"
    )


@router.post("/security/set-password", response_model=SettingsUpdateResponse)
async def set_password(password: str):
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    success = service.set_password(password)
    return SettingsUpdateResponse(
        success=success,
        message="Password set" if success else "Failed to set password",
        updated_section="security"
    )


@router.post("/security/verify-password")
async def verify_password(password: str):
    valid = service.verify_password(password)
    return {"valid": valid}


# ──────────────────────────────────────────────
# PARENTAL CONTROLS
# ──────────────────────────────────────────────

@router.get("/parental-controls")
async def get_parental_controls():
    data = service.get_parental_controls()
    data.pop("pin_hash", None)
    return data


@router.put("/parental-controls", response_model=SettingsUpdateResponse)
async def update_parental_controls(settings: ParentalControlsSettings):
    success = service.update_parental_controls(settings)
    return SettingsUpdateResponse(
        success=success,
        message="Parental controls updated" if success else "Update failed",
        updated_section="parental_controls"
    )


@router.post("/parental-controls/set-pin", response_model=SettingsUpdateResponse)
async def set_parental_pin(pin: str):
    if len(pin) < 4:
        raise HTTPException(status_code=400, detail="PIN must be at least 4 digits")
    success = service.set_parental_pin(pin)
    return SettingsUpdateResponse(
        success=success,
        message="Parental PIN set" if success else "Failed to set PIN",
        updated_section="parental_controls"
    )


@router.post("/parental-controls/verify-pin")
async def verify_parental_pin(pin: str):
    valid = service.verify_parental_pin(pin)
    return {"valid": valid}


# ──────────────────────────────────────────────
# PROJECT
# ──────────────────────────────────────────────

@router.get("/project")
async def get_project_settings():
    return service.get_project()


@router.put("/project", response_model=SettingsUpdateResponse)
async def update_project_settings(settings: ProjectSettings):
    success = service.update_project(settings)
    return SettingsUpdateResponse(
        success=success,
        message="Project settings updated" if success else "Update failed",
        updated_section="project"
    )



# ──────────────────────────────────────────────
# AGENTS
# ──────────────────────────────────────────────

@router.get("/agents")
async def get_all_agents():
    return service.get_all_agents()


@router.get("/agents/active")
async def get_active_agent():
    agent = service.get_active_agent()
    return agent if agent else {"active": False}


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    agent = service.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.post("/agents", response_model=SettingsUpdateResponse)
async def create_agent(agent: AgentConfig):
    success = service.create_agent(agent)
    if not success:
        raise HTTPException(status_code=409, detail="Agent with this ID already exists")
    return SettingsUpdateResponse(
        success=True,
        message=f"Agent '{agent.name}' created",
        updated_section="agents"
    )


@router.put("/agents/{agent_id}", response_model=SettingsUpdateResponse)
async def update_agent(agent_id: str, agent: AgentConfig):
    success = service.update_agent(agent_id, agent)
    return SettingsUpdateResponse(
        success=success,
        message="Agent updated" if success else "Update failed",
        updated_section="agents"
    )


@router.delete("/agents/{agent_id}", response_model=SettingsUpdateResponse)
async def delete_agent(agent_id: str):
    success = service.delete_agent(agent_id)
    return SettingsUpdateResponse(
        success=success,
        message="Agent deleted" if success else "Delete failed",
        updated_section="agents"
    )


@router.post("/agents/{agent_id}/activate", response_model=SettingsUpdateResponse)
async def activate_agent(agent_id: str):
    agent = service.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    success = service.activate_agent(agent_id)
    return SettingsUpdateResponse(
        success=success,
        message=f"Agent '{agent['name']}' activated" if success else "Activation failed",
        updated_section="agents"
    )


@router.post("/agents/deactivate", response_model=SettingsUpdateResponse)
async def deactivate_all_agents():
    success = service.deactivate_agents()
    return SettingsUpdateResponse(
        success=success,
        message="All agents deactivated" if success else "Deactivation failed",
        updated_section="agents"
    )


# ──────────────────────────────────────────────
# AUDIT LOG
# ──────────────────────────────────────────────

@router.get("/audit-log")
async def get_audit_log(limit: int = Query(default=100, ge=1, le=1000)):
    return service.get_audit_log(limit)