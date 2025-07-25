import json
import os
import sys

import clamd
from budmicroframe.commons import logging
from modelscan.issues import IssueCode
from modelscan.modelscan import ModelScan

from ..commons.config import app_settings
from .exceptions import ModelScanException
from .schemas import ModelIssue


logger = logging.get_logger(__name__)


def scan_model(model_dir):
    """Scan a model directory for static issues using ModelScan."""
    if not model_dir or not os.path.exists(model_dir):
        logger.error("Invalid model directory: %s", model_dir)
        raise ModelScanException(f"Invalid model directory: {model_dir}")

    try:
        scan_ins = ModelScan()
        scan_results = scan_ins.scan(model_dir)
        model_issues = []
        grouped_issues = scan_ins._issues.group_by_severity()

        if grouped_issues:
            issue_titles = {
                IssueCode.UNSAFE_OPERATOR.value: "Unsafe operator",
                IssueCode.FORMAT_MISMATCH.value: "Format Mismatch",
                IssueCode.INVALID_HEADER.value: "Invalid Header",
                IssueCode.JSON_PARSING_FAILED.value: "Json Parsing Failed",
                IssueCode.SUSPICIOUS_PATTERN.value: "Suspicious pattern",
                IssueCode.INVALID_ENCODING.value: "Invalid Encoding",
            }

            for issues in grouped_issues.values():
                for issue in issues:
                    issue_title = issue_titles.get(issue.code.value)
                    if issue_title:
                        issue_info = issue.details.output_json()
                        model_issues.append(
                            ModelIssue(
                                title=f"{issue_title} found:",
                                severity=issue_info["severity"],
                                description=issue_info["description"],
                                source=issue_info["source"],
                            ).model_dump()
                        )
                    else:
                        logger.error("No issue description for issue code %s", issue.code)

        scan_results["model_issues"] = model_issues

        return format_scan_result(scan_results, model_dir)

    except Exception as e:
        logger.exception("Unexpected error during model scan: %s", e)
        raise ModelScanException(f"Error during model scan: {e}") from e


def format_scan_result(result: dict, model_absolute_path: str):
    """Format the raw scan result into a clean summary for reporting."""
    if not result or "summary" not in result:
        logger.error("Invalid scan result format: %s", result)
        raise ModelScanException(f"Invalid scan result format: {result}")

    summary = result.get("summary", {})
    total_issues = summary.get("total_issues", 0)
    total_scanned = summary.get("scanned", {}).get("total_scanned", 0)
    issues_by_severity = summary.get("total_issues_by_severity", {})
    scanned_files = summary.get("scanned", {}).get("scanned_files", [])
    skipped_files = summary.get("skipped", {}).get("total_skipped", 0)
    model_issues = result.get("model_issues", [])

    for model_issue in model_issues:
        # Clean up the source path by removing local_path prefix
        source = model_issue["source"]
        if source.startswith(model_absolute_path):
            model_issue["source"] = source[len(model_absolute_path) :].lstrip("/")

    formatted_result = {
        "total_issues": total_issues,
        "total_scanned": total_scanned,
        "total_issues_by_severity": issues_by_severity,
        "scanned_files": scanned_files,
        "total_skipped_files": skipped_files,
        "model_issues": model_issues,
    }

    return formatted_result


class ClamAVScanner:
    def __init__(self, host=app_settings.clamd_host, port=app_settings.clamd_port):
        """Initialize the ClamAV scanner with a Unix socket path."""
        try:
            self.client = clamd.ClamdNetworkSocket(host=host, port=port)
            logger.debug(f"Successfully connected to ClamAV using *TCP socket* at {host}:{port}")
        except Exception as e:
            logger.exception(f"Failed to connect to ClamAV using *TCP socket* at {host}:{port}. Exception: {e}")
            raise

    def scan_dir(self, directory):
        """Scan all files in the specified directory using ClamAV."""
        results = {"FOUND": [], "ERROR": []}

        for root, _, files in os.walk(directory):
            for file in files:
                file_path = os.path.realpath(os.path.join(root, file))
                if not os.path.isfile(file_path):
                    continue

                logger.info(f"Scanning {file_path} via instream")
                try:
                    with open(file_path, "rb") as f:
                        scan_response = self.client.instream(f)

                    for _, (status, detail) in scan_response.items():
                        if status == "FOUND":
                            results["FOUND"].append((file_path, detail))
                        elif status == "ERROR":
                            results["ERROR"].append((file_path, detail))
                except Exception as e:
                    results["ERROR"].append((file_path, str(e)))

        return results


def main():
    """Entry point for the security script.

    Parses command-line arguments and initiates security processing.
    Expects a single argument specifying the path to the model.

    """
    try:
        assert len(sys.argv) > 1, "Usage: python security.py <path_to_model>"
        model_path = sys.argv[1]
        clamav_client = ClamAVScanner()

        scan_result = {
            "total_issues": 0,
            "total_scanned": 0,
            "total_issues_by_severity": {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0},
            "scanned_files": [],
            "total_skipped_files": 0,
            "model_issues": [],
        }

        try:
            scan_result = scan_model(model_path)
        except ModelScanException as e:
            logger.error("Security scan failed: %s", e)
            raise
        except Exception as e:
            logger.exception("Unexpected error during the model security scan: %s", e)
            raise ModelScanException("Unexpected error occurred during the model security scan.") from e

        try:
            logger.info("Starting Clamav Scanning in directory %s", model_path)

            clamav_result = clamav_client.scan_dir(model_path)
            clamav_issues = clamav_result["FOUND"]

            if clamav_issues:
                logger.info("Clamav found issues: %s", clamav_issues)

                for issue in clamav_issues:
                    scan_result["total_issues"] += 1
                    scan_result["total_issues_by_severity"]["CRITICAL"] += 1
                    scan_result["model_issues"].append(
                        {
                            "title": "Virus Signature Found",
                            "severity": "CRITICAL",
                            "description": issue[1],
                            "source": issue[0].split("/")[-1],
                        }
                    )
        except Exception as e:
            logger.exception("Unexpected error during the clamav antivirus scan: %s", e)
            raise ModelScanException("Unexpected error occurred during the clamav antivirus scan.") from e

        print(json.dumps(scan_result))
        return scan_result

    except ModelScanException as e:
        logger.exception("Unable to scan the directory: %s", e)

    except Exception as e:
        logger.exception("Unknown Error occurred during the model security scan: %s", e)


if __name__ == "__main__":
    main()
