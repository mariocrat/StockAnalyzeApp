"""Default-OFF paired generation gate; display capability is not execution identity."""
from core.env import env_value

PAIRED_GENERATION_SETTING = "ALPHAMATE_REVIEW_DISPLAY_V2_ENABLED"


def paired_generation_enabled():
    """Only an explicit true setting opts in. No config or environment is written."""
    return env_value(PAIRED_GENERATION_SETTING) == "true"
