from core.llm.tools.decorators import tool, trace_tool
from core.main_context import GLOBAL_PROFILE_ID
import pandas as pd


@tool(
    schema={
        "name": "get_profile_metadata",
        "description": "Returns the information about the prosumer's profile. Describe this information in natural language that a non-expert prosumer can understand",
        "parameters": {
            "data": "Pipeline job data dictionary (optional)",
            "profile_id": "Optional profile_id to override data['profile_id']"
        }
    }
)
@trace_tool
def get_profile_metadata(data: dict = None, profile_id: int = None):
    """
    Tool that returns the metadata of the current prosumer profile.
    Falls back to GLOBAL_PROFILE_ID if data['profile_id'] is not provided.
    """
    # pid = profile_id or (data or {}).get("profile_id") or GLOBAL_PROFILE_ID
    pid = GLOBAL_PROFILE_ID
    if pid is None:
        raise ValueError("No profile_id available")

    profiles_df = pd.read_csv("data/profile_data/profiles_usecases10.csv", index_col=0)
    profiles_df.columns = profiles_df.columns.str.strip()  # remove tab characters

    profiles_df = profiles_df.set_index("profile_id")

    # Ensure unique
    if not profiles_df.index.is_unique:
        raise ValueError("profile_id is not unique in CSV!")
    return profiles_df.loc[pid].to_dict()

