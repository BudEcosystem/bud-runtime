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

"""The constants used in the budmodel module."""

from enum import Enum, StrEnum, auto
from typing import Literal


# Minimum file size to keep in local storage
LOCAL_MIN_SIZE_GB = 1


class ModelDownloadStatus(StrEnum):
    RUNNING = auto()
    COMPLETED = auto()


# Crawler Type
class CrawlerType(Enum):
    """Crawler type.

    Crawl4AI: Crawl4AI crawler
    """

    CRAWL4AI = "crawl4ai"


class SourceType(Enum):
    """Leaderboard type.

    Name of the leaderboard will be used as value.

    ChatbotArena: Chatbot Arena leaderboard
    """

    CHATBOT_ARENA = "Chatbot arena Leaderboard"
    BERKELEY = "Berkeley Leaderboard"
    LIVE_CODEBENCH = "Live codebench Leaderboard"
    METB = "Mteb Leaderboard"
    VLLM = "VLLM Leaderboard"
    ALPACA = "APAC Eval Leaderboard"
    UGI = "UGI Leaderboard"
    LLM_STATS = "LLM Stats Leaderboard"


class ModelExtractionStatus(StrEnum):
    """Model extraction status."""

    COMPLETED = auto()
    PARTIAL = auto()


class LeaderboardDataOrigin(StrEnum):
    """Source of leaderboard data."""

    SCRAPED = auto()
    README_LLM = auto()


LEADERBOARD_FIELDS = Literal[
    "lc_win_rate",
    "bcfl",
    "live_code_bench",
    "classification",
    "clustering",
    "pair_classification",
    "reranking",
    "retrieval",
    "semantic",
    "summarization",
    "ugi_score",
    "mmbench",
    "mmstar",
    "mmmu",
    "math_vista",
    "ocr_bench",
    "ai2d",
    "hallucination_bench",
    "mmvet",
    "lmsys_areana",
]

MODEL_ANALYSIS_PROMPT = """
Your goal is to go through the given model description (MODEL DESCRIPTION) carefully and thoroughly to clearly define the description and advantages of the given model. Ensure that your assessment is easy to understand, factual & thorough. Follow the instructions given below carefully to create the final JSON.

description (key - description - String, Max 3-4 Sentences): Read the source document carefully and extract factual details about the model. Identify the model’s name, developer, purpose, and key technical specifications (e.g., parameters, architecture, context length). List special features, target tasks, and any explicitly stated limitations. Only include language support, benchmarks, or performance claims if directly mentioned. Keep the description accurate, avoiding assumptions, and summarize the essential information in 2-5 sentences.
advantages (key - advantages [List of strings]): Read the model description and evals carefully to identify explicitly stated strengths and capabilities. Look for phrases like ‘excels at,’ ‘strong in,’ or specific improvements (e.g., larger context window). List each advantage as a complete statement with supporting details, using only facts from the source. For evals, note benchmarks, scores, and what they measure (e.g., GSM8K → math reasoning). Translate results into real-world skills, mentioning limitations where stated. Avoid assumptions, comparisons, or unsupported claims — rely strictly on the provided data.
disadvantages (key - disadvantages [List of strings]): Carefully read the model description and evals to identify explicitly stated limitations or weaknesses. Look for words like ‘limitation,’ ‘drawback,’ or ‘weakness’ and categorize them (e.g., technical limits, performance issues, safety concerns). In evals, flag low scores: As an example: GSM8K < 50 means poor math skills, MMLU < 60 suggests weak factual reasoning. List each disadvantage as a clear, standalone point with exact wording or paraphrased text — no assumptions or exaggerations. Only document what’s directly provided, and avoid conclusions beyond the source data.
usecases (key: usecases [List of strings]): Read the model description and evals to find suitable use cases. Look for features, architecture details, and benchmark results. For example, a high score on HellaSwag (70) suggests strong natural language understanding for creative writing or content generation. A moderate MMLU score (50) indicates potential for general knowledge tasks, while a GSM8K score of 40 suggests some mathematical reasoning ability. List practical applications directly based on these strengths, without making assumptions beyond the data provided.
evals: (key evals (List of dictionaries)): Find any evals available in the description and extract them with their values. For example: MMLU: 50, GSM8K: 40, HellaSwag: 70, etc. format - {"name": "MMLU", "score": 50}. Ensure that score is a number and also ensure that the value is extracted appropriately for the given model based on the table structure.

Sample JSON Structure for one model is given below:
{
  "description": "Qwen-72B is a 72B-parameter large language model developed by Alibaba Cloud, based on the Transformer architecture. It is trained on over 3 trillion tokens of diverse data, including multilingual, code, and mathematical content. Key features include a 151,851-token vocabulary optimized for multiple languages, support for 32,768-token context length, and advanced techniques like RoPE position encoding. It outperforms other open-source models on benchmarks such as MMLU (77.4), GSM8K (78.9), and C-Eval (83.3), demonstrating strong knowledge, reasoning, and multilingual capabilities.",
  "advantages": [
    "Supports 32,768 token context length, enabling handling of long documents and complex tasks requiring extensive context.",
    "Achieves state-of-the-art performance on benchmarks like MMLU (77.4), GSM8K (78.9), and C-Eval (83.3), demonstrating strong knowledge, reasoning, and multilingual capabilities.",
    "Uses a 151,851 token vocabulary optimized for multiple languages, including Chinese, English, and technical domains like code and mathematics.",
    "Employs advanced techniques such as RoPE relative position encoding, SwiGLU activation, and RMSNorm for efficient training and inference."
  ],
  "disadvantages": [
    "Requires significant computational resources, needing at least 144GB GPU memory for BF16/FP16 precision (e.g., 2xA100-80G GPUs) or 48GB for Int4 precision."
  ],
  "usecases": [
    "Multilingual content generation and translation due to its extensive vocabulary and cross-lingual capabilities.",
    "Complex reasoning tasks such as mathematical problem-solving (GSM8K score of 78.9) and code generation (HumanEval score of 35.4).",
    "Handling long documents or conversations requiring up to 32k token context length.",
    "Educational applications like answering exam-style questions (GaokaoBench score of 87.6)."
  ],
  "evals": [
    {
      "name": "Avg",
      "score": 66.4
    },
    {
      "name": "MMLU",
      "score": 77.4
    },
    {
      "name": "C-Eval",
      "score": 83.3
    },
    {
      "name": "GSM8K",
      "score": 78.9
    },
    {
      "name": "MATH",
      "score": 35.2
    },
    {
      "name": "HumanEval",
      "score": 35.4
    },
    {
      "name": "MBPP",
      "score": 52.2
    },
    {
      "name": "BBH",
      "score": 67.7
    },
    {
      "name": "AGIEval",
      "score": 62.5
    },
    {
      "name": "GaokaoBench",
      "score": 87.6
    },
    {
      "name": "CMMLU",
      "score": 83.6
    }
  ]
}

Ensure that the final JSON provided is valid, syntactically correct and follows the instructions provided above thoroughly.If the model description is not available or says there was some error fetching the details, leave all the keys empty. Also, Make sure that only ENGLISH language is used for the final response even if there are other languages in the MODEL DESCRIPTION given. Let us take a deep breathe and think step by step to come up with the final JSON carefully following the instructions provided above.

"""

LICENSE_ANALYSIS_PROMPT = """
Act as an expert License reviewer. Your goal is to carefully analyse the given software/model license agreement and answer the questions given below in the form of a JSON. Ensure that all the answers for the questions are only based on the license given below, do not assume anything - ONLY USE THE DETAILS GIVEN. Don't infer on anything outside from what is given on the provided license. Also, Ensure that the JSON created is written inside the tags <json> </json>

The JSON should be structurally correct and exact without any error, comments, code etc.

Name of the license (key: name) - Name of the license as provided on the license.
Type of the license (key: type) - Type of the license, Pick from the list given here - [Permissive Open Source, Copyleft Open Source, Weak Copyleft Open Source, Open Source but Restrictive, Open Source but No Redistribution, Non-Commercial License, Fully Proprietary, Proprietary with API Access, Proprietary with Limited Customization, Closed Source but Free to Use]
Following questions with a dictionary for each questions (key: Q1, Q2 etc):
For example: {question: Question under consideration, answer: YES or NO, reason: List[String] : List of strings}

Q1. Can you modify the software, model, or framework? : Analyse if the software, model etc are opensource and can be modified for building a derivative software (Yes or No) and reasons.

Q2. Are there any restrictions on modifying core components? : Analyse if the software/model source code and all the components could be modified with out any restrictions (Yes or No) and reasons.

Q3. Can you distribute the modified version of the software/model? : Analyse if the model could be finetuned/trained/modified and distributed or if the software could be modified and distributed without any restrictions (Yes or No) and reasons.

Q4. Are there limitations on how you share derivative works? : Analyse if there are any limitations in sharing the derivate model or software, like attributions, following the same license type, etc. (Yes or No) and reasons.

Q5. Must you open-source your modifications (Copyleft vs. Permissive)? :  (Yes or No) and reasons

Q6. Are you allowed to monetize the tool you build on top of it? : (Yes or No) and reasons.

Q7. Does the license restrict commercial applications (e.g., Non-Commercial License)? (Yes or no) and reasons

Q8. Are there royalty requirements or revenue-sharing clauses? (Yes or No) and reasons

Q9. Are you required to credit the original software, model, or tool? (Yes or No) and reasons

Q10. 	Must you include license texts, disclaimers, or notices in your product? (Yes or No) and reasons

Q11. Does the license require you to make your changes public? (Yes or No) and reasons

Q12. If the tool provides API access, what are the usage limits? (Yes or No) and reasons

Q13. Are you allowed to build commercial applications using the API? (Yes or No) and reasons

Q14. Are there rate limits or paywalls for extended use? (Yes or No) and reasons.

Q15. Does the license provide any patent grants or protections? (Yes or No) and reasons.

Q16. Could you face legal risks if your tool extends the licensed software? (Yes or No) and reasons.

Q17. Are there restrictions on filing patents for derivative works? (Yes or No) and reasons.

Q18. If it’s an AI model, does the license restrict how you can use the training data? (Yes or No) and reasons

Q19. Are there privacy constraints that affect how user data is handled? (Yes or No) and reasons.

Q20. Can the licensor revoke your usage rights at any time? (Yes or No) and reasons.

Q21. Is there a clause that limits their liability in case of legal issues? (Yes or No) and reasons.

Q22. Are there terms that prevent the use of the tool for specific purposes (e.g., ethical AI clauses)? (Yes or No) and reasons.

Create a JSON with the keys and answers to the questions given above and follow the JSON structure as described. An example JSON for 2 questions are given below:

<json>
{
  "name": "Attribution-NonCommercial-ShareAlike 4.0 International",
  "type": "Non-Commercial License",
  "Q1": {
    "question": "Can you modify the software, model, or framework?",
    "answer": "YES",
    "reason": [
      "Section 2(a)(1)(b) allows producing, reproducing, and sharing Adapted Material for NonCommercial purposes only.",
      "Section 2(a)(4) permits technical modifications necessary to exercise the Licensed Rights."
    ]
  },
  "Q2": {
    "question": "Are there any restrictions on modifying core components?",
    "answer": "NO",
    "reason": [
      "The license does not specify restrictions on modifying core components; Section 2(a)(4) allows technical modifications without limitation on specific components."
    ]
  }
}
</json>

LICENSE:

"""

# License Minio Object Names
LICENSE_MINIO_OBJECT_NAME = "licenses"
COMMON_LICENSE_MINIO_OBJECT_NAME = f"{LICENSE_MINIO_OBJECT_NAME}/common_licenses"
