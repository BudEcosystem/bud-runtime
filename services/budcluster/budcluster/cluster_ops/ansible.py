import os
from typing import Dict, List, Optional

import ansible_runner

from ..commons.config import app_settings
from ..playbooks import get_playbook_path


class AnsibleExecutor:
    def run_playbook(
        self,
        playbook: str,
        inventory: Optional[str] = "localhost,",
        extra_vars: Optional[Dict] = None,
        limit: Optional[str] = None,
        verbosity: int = 0,
    ) -> Dict:
        """Execute an Ansible playbook.

        Args:
            playbook (str): Name of the playbook file (e.g., 'site.yml').
            inventory (str, optional): Path to the inventory file or string of hosts.
            extra_vars (dict, optional): Dictionary of extra variables to pass to Ansible.
            limit (str, optional): Limit the execution to a subset of hosts.
            verbosity (int, optional): Verbosity level (0-4).

        Returns:
            dict: A dictionary containing the result of the Ansible run.
        """
        playbook_path = get_playbook_path(playbook)
        extra_vars = extra_vars or {}
        extra_vars["charts_dir"] = os.path.join(os.path.dirname(__file__), "../charts")
        extra_vars["validate_certs"] = app_settings.validate_certs

        if not os.path.exists(playbook_path):
            raise FileNotFoundError(f"Playbook not found: {playbook_path}")

        run_options = {
            "playbook": playbook_path,
            "verbosity": verbosity,
        }

        if inventory:
            run_options["inventory"] = inventory
        if extra_vars:
            run_options["extravars"] = extra_vars
        if limit:
            run_options["limit"] = limit

        runner = ansible_runner.run(**run_options)

        return {
            "status": runner.status,
            "rc": runner.rc,
            "events": self._process_events(runner.events),
            "stats": runner.stats,
        }

    def _process_events(self, events: List[Dict]) -> List[Dict]:
        """Process and filter Ansible events.

        Args:
            events (List[Dict]): List of Ansible event dictionaries.

        Returns:
            List[Dict]: Filtered and processed list of events.
        """
        processed_events = []
        for event in events:
            if event["event"] in ["runner_on_ok", "runner_on_failed", "runner_on_unreachable", "runner_on_skipped"]:
                processed_events.append(
                    {
                        "host": event["event_data"].get("host"),
                        "task": event["event_data"].get("task"),
                        "status": event["event"],
                        "event_data": event["event_data"],
                    }
                )
        return processed_events
