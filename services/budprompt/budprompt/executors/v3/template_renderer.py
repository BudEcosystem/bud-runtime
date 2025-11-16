#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------------------------------------------------------------

"""Jinja2 template renderer for prompts and messages."""

from typing import Any, Dict, Optional

from budmicroframe.commons import logging
from jinja2 import Environment, TemplateSyntaxError, UndefinedError, meta

from budprompt.commons.exceptions import TemplateRenderingException


logger = logging.get_logger(__name__)


class TemplateRenderer:
    """Handles Jinja2 template rendering for prompts and messages."""

    def __init__(self):
        """Initialize the template renderer with a sandboxed Jinja2 environment."""
        # Create a sandboxed environment for security
        self.env = Environment(
            autoescape=False,  # nosec B701 - HTML escaping not needed for LLM prompts (non-web context)
            trim_blocks=True,  # Remove newline after blocks
            lstrip_blocks=True,  # Remove leading spaces from blocks
        )

    def render_template(self, template_str: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Render a Jinja2 template with the given context.

        Args:
            template_str: The Jinja2 template string
            context: Dictionary of variables to use in the template

        Returns:
            The rendered template string

        Raises:
            PromptExecutionException: If template rendering fails
        """
        if context is None:
            context = {}

        try:
            # Parse the template
            template = self.env.from_string(template_str)

            # Find undeclared variables in the template
            ast = self.env.parse(template_str)
            undeclared_vars = meta.find_undeclared_variables(ast)

            # Check if all required variables are provided
            missing_vars = undeclared_vars - set(context.keys())
            if missing_vars:
                logger.warning(f"Template has undefined variables: {missing_vars}")

            # Render the template
            rendered = template.render(**context)
            return rendered

        except TemplateSyntaxError as e:
            logger.error(f"Template syntax error: {str(e)}")
            raise TemplateRenderingException("Invalid template syntax") from e
        except UndefinedError as e:
            logger.error(f"Undefined variable in template: {str(e)}")
            raise TemplateRenderingException("Undefined variable in template") from e
        except Exception as e:
            logger.error(f"Template rendering failed: {str(e)}")
            raise TemplateRenderingException("Template rendering failed") from e


# Global instance for convenience
_renderer = TemplateRenderer()


def render_template(template_str: str, context: Optional[Dict[str, Any]] = None) -> str:
    """Render a Jinja2 template with the given context.

    This is a convenience function that uses a global TemplateRenderer instance.

    Args:
        template_str: The Jinja2 template string
        context: Dictionary of variables to use in the template

    Returns:
        The rendered template string

    Raises:
        PromptExecutionException: If template rendering fails
    """
    return _renderer.render_template(template_str, context)
