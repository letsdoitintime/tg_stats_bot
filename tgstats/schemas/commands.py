"""Command argument schemas for validation."""

from pydantic import BaseModel, Field, validator


class SetTextCommand(BaseModel):
    """Schema for /set_text command."""

    enabled: bool = Field(..., description="Enable or disable text storage")

    @validator("enabled", pre=True)
    def validate_enabled(cls, v):
        """Convert string input to boolean."""
        if isinstance(v, str):
            v_lower = v.lower()
            if v_lower in ("on", "true", "1", "yes", "enabled"):
                return True
            elif v_lower in ("off", "false", "0", "no", "disabled"):
                return False
            else:
                raise ValueError("Must be 'on' or 'off'")
        return v


class SetReactionsCommand(BaseModel):
    """Schema for /set_reactions command."""

    enabled: bool = Field(..., description="Enable or disable reaction capture")

    @validator("enabled", pre=True)
    def validate_enabled(cls, v):
        """Convert string input to boolean."""
        if isinstance(v, str):
            v_lower = v.lower()
            if v_lower in ("on", "true", "1", "yes", "enabled"):
                return True
            elif v_lower in ("off", "false", "0", "no", "disabled"):
                return False
            else:
                raise ValueError("Must be 'on' or 'off'")
        return v
