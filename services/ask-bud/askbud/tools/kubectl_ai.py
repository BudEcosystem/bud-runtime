import asyncio
import os
import re
from typing import Dict, List

from agents import RunContextWrapper, function_tool

from ..agent.schemas import SessionContext
from ..commons.config import app_settings


_FORBIDDEN = re.compile(r"^(delete|scale|apply|patch|replace|edit)\b", re.I)


@function_tool
async def kubectl_ai_query(
    run_ctx: RunContextWrapper[SessionContext],
    question: str,
    terse: bool = False,
) -> Dict[str, str]:
    """Tool to query kubectl and fetch live data from the cluster."""
    ctx = run_ctx.context
    if ctx.active_cluster is None:
        raise RuntimeError("No active cluster selected. Use set_active_cluster first.")
    cmd: List[str] = ["kubectl-ai", "--llm-provider", "openai", "--model", app_settings.inference_model, "--quiet"]
    kubeconfig = await ctx.registry.get_cluster_config(ctx.active_cluster)
    env = os.environ.copy()
    env["KUBECTL_INSECURE_SKIP_TLS_VERIFY"] = "true"  # Set environment variable to skip TLS verification
    if kubeconfig:
        # env["KUBECONFIG"] = kubeconfig
        cmd += ["--kubeconfig", kubeconfig]
    cmd += ["--skip-verify-ssl"]
    # else:
    #     cmd += ["--context", ctx.active_cluster]

    cmd.append(question)
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env
    )
    out, err = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(err.decode() or "kubectl-ai failed")
    out_str = out.decode()
    # out = out_str
    first_nl = out_str.find("\n")
    kubectl_cmd = out_str[:first_nl].strip() if first_nl != -1 else out_str.strip()
    if _FORBIDDEN.match(kubectl_cmd):
        raise RuntimeError("Destructive kubectl command refused: " + kubectl_cmd)
    kubectl_stdout = out[first_nl + 1 :].lstrip() if first_nl != -1 else ""
    return {
        "nl_question": question,
        "kubectl_cmd": kubectl_cmd,
        "stdout": kubectl_stdout.decode() if isinstance(kubectl_stdout, bytes) else str(kubectl_stdout),
    }
