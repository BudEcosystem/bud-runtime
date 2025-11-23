"""Node information collection module.

This module provides Python-based node information collection
to replace the Ansible-based approach, reducing memory usage
and improving performance.
"""

from .node_info_service import get_node_info_python


__all__ = [
    "get_node_info_python",
]
