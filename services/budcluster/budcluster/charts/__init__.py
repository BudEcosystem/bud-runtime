"""This package provides functionality to handle chart paths."""

import os


def get_chart_path(chart_name: str) -> str:
    """Get the full path of the specified chart.

    Args:
        chart_name (str): The name of the chart.

    Returns:
        str: The full path to the chart.
    """
    return f"{os.path.dirname(os.path.abspath(__file__))}/{chart_name}"
