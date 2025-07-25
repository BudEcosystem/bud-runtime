import json
import os
import re
from datetime import datetime

import requests

from budapp.commons import logging
from budapp.commons.config import app_settings


logger = logging.get_logger(__name__)

CURRENT_FILE_PATH = os.path.dirname(os.path.abspath(__file__))


class Grafana:
    def __init__(self):
        """Initialize the Grafana client."""
        self.url = f"{app_settings.grafana_scheme}://{app_settings.grafana_username}:{app_settings.grafana_password}@{app_settings.grafana_url}"
        self.fixed_input_path = os.path.join(CURRENT_FILE_PATH, "templates", "grafana_dashboard.json")

    def replace_template_vars(self, obj, cluster, datasource_uid):
        """Recursively replace template variables in strings within a JSON object."""
        if isinstance(obj, dict):
            return {k: self.replace_template_vars(v, cluster, datasource_uid) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.replace_template_vars(v, cluster, datasource_uid) for v in obj]
        elif isinstance(obj, str):
            obj = re.sub(r"\$\{cluster\}", cluster, obj)
            obj = re.sub(r"\$cluster", cluster, obj)
            obj = re.sub(r"\$\{datasource\}", datasource_uid, obj)
            obj = re.sub(r"\$datasource", datasource_uid, obj)
            return obj
        return obj

    def sanitize_dashboard(self, dashboard, cluster, datasource_uid):
        """Sanitize dashboard JSON by removing template vars and lists."""
        if "templating" in dashboard:
            dashboard["templating"]["list"] = []
        return self.replace_template_vars(dashboard, cluster, datasource_uid)

    def load_dashboard_json(self, file_path):
        """Load dashboard JSON from a file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading dashboard JSON file {file_path}: {e}")
            raise e

    def save_dashboard_json(self, file_path, data):
        """Save sanitized dashboard JSON to a file."""
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def publish_dashboard(self, dashboard_json, uid, new_title=None, folder_id=None, overwrite=False):
        """Publish a dashboard to Grafana."""
        headers = {"Content-Type": "application/json"}

        dashboard = dashboard_json.copy()
        if new_title:
            dashboard["title"] = new_title

        dashboard["uid"] = uid
        dashboard.pop("id", None)

        payload = {
            "dashboard": dashboard,
            "overwrite": overwrite,
            "message": f"Dashboard created programmatically on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        }

        try:
            response = requests.post(f"{self.url}/api/dashboards/import", headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error publishing dashboard: {e}")
            if e.response is not None:
                logger.error(f"Response content: {e.response.text}")
            return None

    def make_dashboard_public(self, dashboard_uid):
        """Make a Grafana dashboard publicly accessible."""
        headers = {"Content-Type": "application/json"}

        payload = {"share": "public", "isEnabled": True}

        try:
            response = requests.post(
                f"{self.url}/api/dashboards/uid/{dashboard_uid}/public-dashboards",
                headers=headers,
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error making dashboard public: {e}")
            if e.response is not None:
                logger.error(f"Response content: {e.response.text}")
            return None

    def get_public_dashboard_url_by_uid(self, cluster_id: str):
        """Get the public URL of a Grafana dashboard by its UID."""
        headers = {"Content-Type": "application/json"}

        response = requests.get(
            f"{self.url}/api/dashboards/uid/{cluster_id}/public-dashboards", headers=headers, timeout=30
        )
        if response.status_code == 200:
            data = response.json()
            logger.debug(f"Public dashboard: {data}")
            url = f"{app_settings.grafana_scheme}://{app_settings.grafana_url}/public-dashboards/{data['accessToken']}"
            logger.debug(f"Public dashboard URL: {url}")
            return url
        else:
            logger.error(f"Failed to get access token: {response.text}")
            raise Exception(f"Failed to get access token: {response.text}")

    def create_dashboard_from_file(self, cluster, datasource_uid, cluster_name):
        """Create a dashboard from a file."""
        logger.debug(f"Creating dashboard from file: {self.fixed_input_path}")
        dashboard_json = self.load_dashboard_json(self.fixed_input_path)
        dashboard = dashboard_json.get("dashboard", dashboard_json)

        # update title
        dashboard["title"] = f"{cluster_name}"
        sanitized = self.sanitize_dashboard(dashboard, cluster, datasource_uid)

        logger.debug("Dashboard Sanitized")

        title = f"{sanitized.get('title', 'Dashboard')}"

        logger.debug(f"Publishing dashboard with title: {title}")

        result = self.publish_dashboard(sanitized, uid=cluster, new_title=title)

        logger.debug("Dashboard Published")

        if result:
            logger.debug("Dashboard Published Successfully")
            logger.debug(f"  Title: {title}")
            logger.debug(f"  URL: {self.url}/d/{result['uid']}")
            logger.debug(f"  UID: {result['uid']}")

            public = self.make_dashboard_public(result["uid"])
            if public:
                logger.debug("Dashboard Made Public")
                logger.debug(f"  Public URL: {self.url}/public-dashboards/{public['accessToken']}")


# Example usage (if calling from a script)
# if __name__ == "__main__":
#     grafana = Grafana()
#     grafana.create_dashboard_from_file("60d5a04c-cebc-4d2d-a106-9f4fcc5cabe7", "prometheus")
