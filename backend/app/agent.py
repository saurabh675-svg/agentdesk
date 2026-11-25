"""AgentDesk agent facade (0.5 split, step 2).

The loop itself lives in ``app.agent_runner``; this module keeps the old
import paths (``from app.agent import AgentRunner, TOOL_SCHEMAS, SYSTEM_PROMPT``)
working and stays under 900 LOC.
"""

from .agent_runner import AgentRunner, _social_reply, build_system_prompt, Send  # noqa: F401
from .agent_prompts import SYSTEM_PROMPT  # noqa: F401
from .agent_schemas import TOOL_SCHEMAS  # noqa: F401

# Keep the greeting regexes importable through the old path.
from .agent_runner import _ACK_RE, _CONTINUE_RE, _GREETING_RE  # noqa: F401

__all__ = ["AgentRunner", "TOOL_SCHEMAS", "SYSTEM_PROMPT", "build_system_prompt", "_social_reply", "Send"]
