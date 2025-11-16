import concurrent.futures
import json
import logging
import re
import tempfile
import urllib.request
from json.decoder import JSONDecodeError
from typing import Any, Dict, List, Optional, Tuple

import requests  # type: ignore
from huggingface_hub import ModelCard, hf_hub_download
from json_repair import repair_json
from requests.exceptions import RequestException

from ..commons.config import app_settings, secrets_settings
from ..commons.constants import LICENSE_ANALYSIS_PROMPT, MODEL_ANALYSIS_PROMPT
from ..commons.exceptions import InferenceClientException
from ..commons.helpers import extract_json_from_string
from ..commons.inference import InferenceClient
from .helper import (
    extract_answer_and_description,
    extract_json_from_response,
    extract_urls_from_markdown,
    extract_urls_from_modelcard,
    get_license_content,
    mapped_licenses,
)
from .models import LicenseInfoCRUD
from .prompts import GIT_URL_PROMPT, LICENSE_QA_PROMPT, USECASE_INFO_PROMPT, WEB_URL_PROMPT


logger = logging.getLogger(__name__)


def fetch_response_from_perplexity(model: str, prompt: str, system_prompt: str = None) -> str:
    """Send a request to the Perplexity API chat completions endpoint and retrieves the response."""
    url = "https://api.perplexity.ai/chat/completions"
    token = secrets_settings.perplexity_api_key
    if not token or token.strip() == "":
        raise ValueError("Perplex API key must not be None or empty.")
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1024,
        "temperature": 0.0,
    }
    if system_prompt:
        payload["messages"].append({"role": "system", "content": system_prompt})

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        response_data = response.json()
        return str(response_data["choices"][0]["message"]["content"])
    except RequestException as e:
        raise RuntimeError(f"Failed to fetch response from Perplexity API: {e}") from e
    except JSONDecodeError as e:
        raise ValueError(f"Failed to decode JSON from API response: {e}") from e


def extract_model_card_details(model_card: str, model: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract model card details from the model card object."""
    if not isinstance(model, str) or not model.strip():
        raise ValueError("Model name must be a non-empty string.")

    if not model_card:
        return None, None

    urls = extract_urls_from_modelcard(model_card)
    git_urls = urls.get("git_urls", [])

    other_urls = urls.get("other_urls", [])

    git_url, web_url = None, None

    if git_urls:
        git_prompt = GIT_URL_PROMPT.format(git_url_list=git_urls, model_name=model)
        try:
            if secrets_settings.perplexity_api_key:
                git_response = fetch_response_from_perplexity(app_settings.model, git_prompt)
            else:
                inference_client = InferenceClient()
                git_response = inference_client.chat_completions(git_prompt, temperature=0.1)
                git_response = json.loads(repair_json(git_response))

            git_url = extract_urls_from_markdown(git_response).get("git_repo_url")
        except Exception as e:
            raise RuntimeError(f"Failed to extract Git URL: {e}") from e

    if other_urls:
        web_prompt = WEB_URL_PROMPT.format(web_url_list=other_urls, model_name=model)
        try:
            if secrets_settings.perplexity_api_key:
                web_response = fetch_response_from_perplexity(app_settings.model, web_prompt)
            else:
                inference_client = InferenceClient()
                web_response = inference_client.chat_completions(web_prompt, temperature=0.1)
                web_response = json.loads(repair_json(web_response))

            web_url = extract_urls_from_markdown(web_response).get("website_url")
        except Exception as e:
            raise RuntimeError(f"Failed to extract website URL: {e}") from e

    return git_url, web_url


def extract_model_card_usecase_info(model_card: str) -> Dict[str, Any]:
    """Extract strengths and limitations from a Hugging Face model card and returns them in JSON format."""
    if not model_card:
        logger.error("Model card is None or empty")
        return {"usecases": [], "limitations": [], "strengths": []}

    prompt = USECASE_INFO_PROMPT.format(model_card=model_card)

    try:
        details_response = fetch_response_from_perplexity(app_settings.model, prompt)
        return extract_json_from_response(details_response)
    except Exception as e:
        raise RuntimeError(f"Failed to extract model card use case information: {e}") from e


def get_license_details(model_card: ModelCard, model_name: str) -> Dict[str, Any]:
    """Get license details from model card, check database, and handle insertion and returns license information including FAQs."""
    if not model_card.content:
        logger.error("Model card is None or empty")
        return {
            "license_name": None,
            "license_identifier": None,
            "license_url": None,
            "license_faqs": [],
            "type": None,
            "description": None,
            "suitability": None,
        }

    license_id = model_card.data.get("license", "")
    license_name = model_card.data.get("license_name", "")
    if isinstance(license_id, str):
        license_id = license_id.lower()
    elif isinstance(license_id, list) and len(license_id) > 0:
        license_id = license_id[0].lower()
    if not license_id:
        return {
            "license_name": None,
            "license_identifier": None,
            "license_url": None,
            "license_faqs": [],
            "type": None,
            "description": None,
            "suitability": None,
        }

    try:
        with LicenseInfoCRUD() as license_crud:
            if license_id == "other" or license_id == "unknown":
                if not license_name:
                    logger.warning(f"License ID is 'other' or 'unknown' but no license name provided for {model_name}")
                    license_name = f"Unknown License-{model_name}"

                existing_license = license_crud.fetch_one(conditions={"name": license_name}, raise_on_error=False)
            else:
                existing_license = license_crud.fetch_one(conditions={"id": license_id}, raise_on_error=False)

        if existing_license:
            logger.debug("License data Already Exists")
            return {
                "license_name": existing_license.name,
                "license_identifier": existing_license.id,
                "license_url": existing_license.url,
                "license_faqs": existing_license.faqs,
                "type": existing_license.type,
                "description": existing_license.description,
                "suitability": existing_license.suitability,
            }
    except Exception as db_error:
        logger.exception(f"Error checking existing license in database: {db_error}")

    def url_exists(url: str) -> bool:
        """Check if a URL exists by attempting to open it."""
        try:
            urllib.request.urlopen(url, timeout=30)
            return True
        except urllib.error.URLError:
            return False

    try:
        license_identifiers = mapped_licenses()
        if not isinstance(license_identifiers, list) or not all(
            isinstance(entry, dict) for entry in license_identifiers
        ):
            raise ValueError("license_identifiers must be a list of dictionaries.")
        license_dict = {entry["license_id"]: entry for entry in license_identifiers}

        license_url = None
        license_faqs = []

        if license_id in license_dict:
            license_name = license_dict[license_id]["license_name"]
            license_url = license_dict[license_id]["license_url"]
        else:
            potential_urls = [
                f"https://huggingface.co/{model_name}/blob/main/LICENSE",
                f"https://huggingface.co/{model_name}/blob/main/LICENSE.txt",
                f"https://huggingface.co/{model_name}/blob/main/LICENSE.md",
            ]
            try:
                license_url = next((url for url in potential_urls if url_exists(url)), None)
            except Exception as url_error:
                logger.error(f"Error checking potential license files: {url_error}")
                license_url = None

            if license_name:
                license_id = license_name

        # Set default values
        license_type = None
        license_description = None
        license_suitability = None
        if license_url:
            try:
                # license_faqs = license_QA(license_url)
                license_details = generate_license_details(license_url)
                license_faqs = license_details.get("faqs", [])
                license_type = license_details.get("type", "")
                license_description = license_details.get("type_description", "")
                license_suitability = license_details.get("type_suitability", "")
            except Exception as qa_error:
                logger.exception(f"Error fetching license FAQs from {license_url}: {qa_error}")
                license_faqs = []

        license_info = {
            "license_name": license_name,
            "license_identifier": license_id,
            "license_url": license_url,
            "license_faqs": license_faqs,
            "type": license_type,
            "description": license_description,
            "suitability": license_suitability,
        }
        if license_name and license_id:
            try:
                license_data = {
                    "id": license_id,
                    "name": license_name,
                    "url": license_url,
                    "faqs": license_faqs,
                    "type": license_type,
                    "description": license_description,
                    "suitability": license_suitability,
                }
                with LicenseInfoCRUD() as license_crud:
                    logger.info(
                        "Inserting the License data into LicenseInfo table: License Name: %s, License ID: %s",
                        license_name,
                        license_id,
                    )
                    license_crud.insert(license_data, raise_on_error=False)
            except Exception as insert_error:
                logger.exception(f"Error inserting license into database: {insert_error}")

        return license_info

    except Exception as e:
        logger.exception(f"Error loading model card for {model_name}: {e}")
        return {
            "license_name": None,
            "license_identifier": None,
            "license_url": None,
            "license_faqs": [],
            "type": None,
            "description": None,
            "suitability": None,
        }


# TODO: Remove this function if not used
def license_QA(license_source: str) -> List[Dict[str, Any]]:
    """Analyze the license content from a given source and answers predefined questions about the licensing terms.

    Args:
        license_source (str): The source of the license content.
            This can be:
            - A URL starting with "http://" or "https://".
            - A local file path to a text, markdown, or PDF file.

    Returns:
        List[Dict]: A list of dictionaries, where each dictionary contains:
            - "question" (str): The licensing question.
            - "answer" (str): The answer to the question.
            - "description" (str): Additional explanation or details.
    """
    if not license_source:
        logger.error("License source is None or empty.")
        return []

    Questions = [
        "Are the weights of the model truly open source?",
        "Can I use it in production for my customers without any payments?",
        "Can I use it for development, research or testing?",
        "Is it free for ever?",
        "Do I have to explicitly mention the name of the model that is being used?",
        "Can I change the model weights & claim to be mine?",
        "Are there any liabilities on me?",
        "Do I own the derivative model and its IP?",
        "Can I build on top of this for a client and transfer it to them?",
        "Are there any royalties or payments?",
        "Can I redistribute the model without any conditions?",
    ]

    try:
        try:
            LICENSE_CONTENT = get_license_content(license_source)
        except Exception as e:
            logger.error(f"Error fetching license content from the license source: {str(e)}")
            return []

        try:
            prompts = [
                LICENSE_QA_PROMPT.format(LICENSE_CONTENT=LICENSE_CONTENT, QUESTION=question) for question in Questions
            ]
        except KeyError as e:
            logger.error(f"Error formatting LICENSE_QA_PROMPT: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Error generating prompts: {str(e)}")
            return []

        question_to_prompt = dict(zip(Questions, prompts, strict=True))

        responses = {}
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(fetch_response_from_perplexity, app_settings.model, prompt): question
                for question, prompt in question_to_prompt.items()
            }

            for future in concurrent.futures.as_completed(futures):
                question = futures[future]
                try:
                    response = future.result()
                    responses[question] = extract_answer_and_description(response)
                except Exception as e:
                    logger.error(f"Error processing response for question '{question}': {str(e)}")
                    responses[question] = {"answer": "", "description": ""}

        formatted_responses = [
            {"question": key, **value} for key, value in responses.items() if isinstance(value, dict)
        ]

        return formatted_responses

    except Exception as e:
        logger.exception(f"Unexpected error in license QA: {str(e)}")
        return []


def get_hf_repo_readme(repo_id: str, token: str = None) -> str:
    """Get README content from a Hugging Face repository using a temporary directory.

    Args:
        repo_id (str): Repository ID (e.g., 'facebook/opt-125m')
        token (str, optional): HuggingFace token for private repos

    Returns:
        str: README content or empty string if not found
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Try README.md first
            try:
                readme_path = hf_hub_download(
                    repo_id=repo_id,
                    filename="README.md",
                    token=token,
                    local_dir=temp_dir,
                    local_dir_use_symlinks=False,
                )
                with open(readme_path, "r", encoding="utf-8") as f:
                    return f.read()

            except Exception:
                # Try README.txt if README.md not found
                try:
                    readme_path = hf_hub_download(
                        repo_id=repo_id,
                        filename="README.txt",
                        token=token,
                        local_dir=temp_dir,
                        local_dir_use_symlinks=False,
                    )
                    with open(readme_path, "r", encoding="utf-8") as f:
                        return f.read()

                except Exception as e:
                    logger.warning("No README found for %s: %s", repo_id, e)
                    return ""

        except Exception as e:
            logger.error("Error fetching README for %s: %s", repo_id, e)
            return ""


def get_model_analysis(model_readme: str) -> Dict[str, Any]:
    """Get model analysis from the model README."""
    prompt = f"MODEL DESCRIPTION: {model_readme}"
    if secrets_settings.perplexity_api_key:
        try:
            response = fetch_response_from_perplexity(app_settings.model, prompt, MODEL_ANALYSIS_PROMPT)
            model_analysis = json.loads(repair_json(response))
            return model_analysis
        except Exception as e:
            logger.warning("LLM model analysis failed: %s. Continuing without LLM-generated fields.", str(e))
            return {}
    else:
        try:
            inference_client = InferenceClient()
            response = inference_client.chat_completions(prompt, system_prompt=MODEL_ANALYSIS_PROMPT, temperature=0.1)
            model_analysis = json.loads(repair_json(response))
            return model_analysis
        except (InferenceClientException, JSONDecodeError) as e:
            logger.warning("LLM model analysis failed: %s. Continuing without LLM-generated fields.", str(e))
            return {}
        except Exception as e:
            logger.warning("LLM model analysis failed: %s. Continuing without LLM-generated fields.", str(e))
            return {}


def generate_license_details(license_source: str) -> List[Dict[str, Any]]:
    """Generate license details from the license source."""
    license_text = get_license_content(license_source)

    if not license_text:
        logger.error("License content is None or empty.")
        return {}

    LICENSE_QUESTIONS = {
        "Q1": {"question": "Can you modify the software, model, or framework?", "impact": "POSITIVE"},
        "Q2": {"question": "Are there any restrictions on modifying core components?", "impact": "NEGATIVE"},
        "Q3": {"question": "Can you distribute the modified version of the software/model?", "impact": "POSITIVE"},
        "Q4": {"question": "Are there limitations on how you share derivative works?", "impact": "NEGATIVE"},
        "Q5": {"question": "Must you open-source your modifications (Copyleft vs. Permissive)?", "impact": "NEGATIVE"},
        "Q6": {"question": "Are you allowed to monetize the tool you build on top of it?", "impact": "POSITIVE"},
        "Q7": {
            "question": "Does the license restrict commercial applications (e.g., Non-Commercial License)?",
            "impact": "NEGATIVE",
        },
        "Q8": {"question": "Are there royalty requirements or revenue-sharing clauses?", "impact": "NEGATIVE"},
        "Q9": {"question": "Are you required to credit the original software, model, or tool?", "impact": "NEGATIVE"},
        "Q10": {
            "question": "Must you include license texts, disclaimers, or notices in your product?",
            "impact": "NEGATIVE",
        },
        "Q11": {"question": "Does the license require you to make your changes public?", "impact": "NEGATIVE"},
        "Q12": {"question": "If the tool provides API access, what are the usage limits?", "impact": "NEGATIVE"},
        "Q13": {"question": "Are you allowed to build commercial applications using the API?", "impact": "POSITIVE"},
        "Q14": {"question": "Are there rate limits or paywalls for extended use?", "impact": "NEGATIVE"},
        "Q15": {"question": "Does the license provide any patent grants or protections?", "impact": "POSITIVE"},
        "Q16": {
            "question": "Could you face legal risks if your tool extends the licensed software?",
            "impact": "NEGATIVE",
        },
        "Q17": {"question": "Are there restrictions on filing patents for derivative works?", "impact": "NEGATIVE"},
        "Q18": {
            "question": "If it’s an AI model, does the license restrict how you can use the training data?",
            "impact": "NEGATIVE",
        },
        "Q19": {
            "question": "Are there privacy constraints that affect how user data is handled?",
            "impact": "NEGATIVE",
        },
        "Q20": {"question": "Can the licensor revoke your usage rights at any time?", "impact": "NEGATIVE"},
        "Q21": {
            "question": "Is there a clause that limits their liability in case of legal issues?",
            "impact": "NEGATIVE",
        },
        "Q22": {
            "question": "Are there terms that prevent the use of the tool for specific purposes (e.g., ethical AI clauses)?",
            "impact": "NEGATIVE",
        },
    }

    LICENSE_TYPES = [
        {
            "type": "Permissive Open Source",
            "description": "Allows modification and redistribution with minimal restrictions, usually requiring only attribution.",
            "suitability": "MOST",
        },
        {
            "type": "Copyleft Open Source",
            "description": "Requires any modifications or derivative works to be shared under the same license terms.",
            "suitability": "GOOD",
        },
        {
            "type": "Weak Copyleft Open Source",
            "description": "Allows linking with proprietary software, but modifications to the open-source parts must remain open.",
            "suitability": "GOOD",
        },
        {
            "type": "Open Source but Restrictive",
            "description": "Allows modification but places restrictions such as non-commercial use or additional compliance requirements.",
            "suitability": "LOW",
        },
        {
            "type": "Open Source but No Redistribution",
            "description": "Allows modifications for personal use but prohibits sharing or distributing modified versions.",
            "suitability": "LOW",
        },
        {
            "type": "Non-Commercial License",
            "description": "The software can be modified and shared, but only for personal or educational use. Commercial distribution is prohibited.",
            "suitability": "LOW",
        },
        {
            "type": "Fully Proprietary",
            "description": "Users cannot modify, distribute, or access the source code; typically requires a paid license.",
            "suitability": "WORST",
        },
        {
            "type": "Proprietary with API Access",
            "description": "Source code remains closed, but users can integrate with the software via an API.",
            "suitability": "WORST",
        },
        {
            "type": "Proprietary with Limited Customization",
            "description": "Some modifications are allowed but only within defined boundaries set by the licensor.",
            "suitability": "LOW",
        },
        {
            "type": "Closed Source but Free to Use",
            "description": "Users can access and use the software without cost but cannot modify or distribute it.",
            "suitability": "WORST",
        },
    ]

    try:
        if secrets_settings.perplexity_api_key:
            llm_response = fetch_response_from_perplexity(app_settings.model, license_text, LICENSE_ANALYSIS_PROMPT)
        else:
            inference_client = InferenceClient()
            llm_response = inference_client.chat_completions(
                license_text, system_prompt=LICENSE_ANALYSIS_PROMPT, temperature=0.1
            )

        if isinstance(llm_response, str):
            llm_response = extract_json_from_string(llm_response)
            llm_response = json.loads(repair_json(llm_response))

        answers = {}
        answers["name"] = llm_response["name"]
        answers["type"] = llm_response["type"]
        answers["type_description"] = ""
        answers["type_suitability"] = ""
        answers["faqs"] = {}

        for license in LICENSE_TYPES:
            if license["type"].lower() == answers["type"].lower():
                answers["type_description"] = license["description"]
                answers["type_suitability"] = license["suitability"]
                break

        for k, v in llm_response.items():
            if k.upper() in LICENSE_QUESTIONS:
                # Initialize the dictionary for this question if it doesn't exist
                answers["faqs"][k] = {}

                # Set default impact as NEUTRAL
                impact = "NEUTRAL"

                # Get the expected impact from license questions
                expected_impact = LICENSE_QUESTIONS[k.upper()]["impact"]

                # Determine actual impact based on answer
                if v.get("answer", "").lower() == "yes":
                    impact = expected_impact
                elif v.get("answer", "").lower() == "no":
                    impact = "POSITIVE" if expected_impact == "NEGATIVE" else "NEGATIVE"

                # Safely assign values using get() to avoid KeyError
                answers["faqs"][k]["impact"] = impact
                answers["faqs"][k]["answer"] = v.get("answer", "")
                answers["faqs"][k]["question"] = v.get("question", "")
                answers["faqs"][k]["reason"] = v.get("reason", "")

        # Convert answers to a list of dictionaries (For compatibility with the existing implementation)
        # NOTE: Doing this as an extra loop incase to revert back to the default format
        reformatted_faqs = []
        for _k, v in answers["faqs"].items():
            reformatted_faqs.append(v)
        answers["faqs"] = reformatted_faqs

        return answers
    except Exception as e:
        logger.exception(f"Error generating licence FAQ: {e}")
        return {}


def normalize_license_identifier(text: str) -> str:
    """Normalize the license identifier."""
    text = text.lower()
    text = re.sub(r"[^a-z\s]", "", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()
