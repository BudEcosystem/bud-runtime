from agents import (
    Agent,
    ModelSettings,
    set_default_openai_api,
    set_default_openai_client,
    set_tracing_disabled,
)
from openai import AsyncOpenAI

from ..commons.config import app_settings
from ..tools.cluster import list_clusters, set_active_cluster
from ..tools.kubectl_ai import kubectl_ai_query
from .performance import PerformanceAgent


SYSTEM = """
You are Bud. A assistant for the bud stack. It also allows the user to interact with the kubernetes cluster.

## Instructions
1. Use requiered tools to interact with the cluster.
2. Give the response in markdown format.
3. The list of resources in kubectl should be in tabular format.


"""


class ClusterAgent(Agent):
    def __init__(self) -> None:
        """Initialize the ClusterAgent with OpenAI client configuration.

        Sets up the AsyncOpenAI client with the appropriate base URL and API key
        from application settings.
        """
        client = AsyncOpenAI(
            base_url=app_settings.inference_url,
            api_key=app_settings.inference_api_key,
        )
        set_default_openai_client(client=client, use_for_tracing=False)
        set_default_openai_api("chat_completions")
        set_tracing_disabled(disabled=True)

        super().__init__(
            name="K8sClusterAgent",
            instructions=SYSTEM,
            model=f"openai/{app_settings.inference_model}",
            model_settings=ModelSettings(
                temperature=0.2,
                tool_choice="auto",
            ),
            tools=[
                list_clusters,
                set_active_cluster,
                kubectl_ai_query,
                PerformanceAgent().as_tool(
                    tool_name="SLO prediction",
                    tool_description="Tool to get the optimized SLO for llm inference",
                ),
            ],
        )
