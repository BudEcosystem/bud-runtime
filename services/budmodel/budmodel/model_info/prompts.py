GIT_URL_PROMPT = """
                    You will be given a list of URLs and a model name. Your task is to extract the Git repository URL for the given model from this list. Follow these steps carefully:

                    1. First, you will be provided with a list of URLs:
                    - List of Git URLs: {git_url_list}

                    2. You will also be given a model name:
                    - {model_name}

                    3. To identify the Git repository URL for the model, follow these guidelines:
                    - First, check for any GitHub URL that directly corresponds to the model's name. These URLs typically resemble 'https://github.com/organization/repository' where the repository name closely matches the model's name.
                    - If no exact match is found, look for URLs that correspond to close variants of the model. Ensure the URL points to the model's source code repository or a close variant.
                    - Avoid URLs that link to general profiles, unrelated repositories, or documentation pages.
                    - If multiple potential URLs are found, choose the one that best matches the model's name or a close variant.
                    - If no valid Git repository URL is found, return an empty string.

                    ### Output Format:
                    - **Git Repository URL**: [<Git repository URL>](<Git repository URL>)

                    """

WEB_URL_PROMPT = """
                You will be given a list of URLs and a model name. Your task is to extract the most relevant website URL for the given model from this list. Follow these steps carefully:

                1. First, you will be provided with a list of URLs:
                - List of other URLs: {web_url_list}

                2. You will also be given a model name:
                - {model_name}

                3. To identify the website URL for the model, follow these guidelines:
                - Look for URLs that seem to point to a project page or documentation.Most of the times url might contain organization name.
                - The website URL should contain terms like "Documentation," "Official Site," or "Model Page."
                - If multiple URLs match, choose the one that appears most relevant or comprehensive.
                - If no valid website URL is found, return an empty string.

                ### Output Format:
                - **Website URL**: [<Website URL>](<Website URL>)

                """

USECASE_INFO_PROMPT = """
                        You are an AI assistant tasked with extracting information from a Hugging Face model card. Follow the reasoning steps below to extract and structure the information accurately.

                        **Output Format:**
                        {{
                            "usecases": [
                                // List of identified use cases here
                            ],
                            "strengths": [
                                // List of model strengths here
                            ],
                            "limitations": [
                                // List of model limitations here
                            ]
                        }}

                        **Reasoning Process (Chain of Thought):**
                        1. Carefully read the provided model card.
                        2. Identify short, specific terms that describe use cases (e.g., chat, summarization, RAG).
                        3. For strengths:
                        - Look for phrases or points that describe what the model does well (e.g., high accuracy, fast performance, domain expertise).
                        - List all strengths identified.
                        4. For limitations:
                        - Look for phrases or points that describe challenges or areas where the model underperforms (e.g., bias, inability to handle complex queries).
                        - List all limitations identified.
                        5. If no use cases, strengths, or limitations are found, return an empty list for that field.

                        **Model card text:**
                        {model_card}

                        **Output:** Provide only the JSON object based on the steps above.
                        """


LICENSE_QA_PROMPT = """
                    You are an AI assistant tasked with answering questions based on a provided license. You will be given the license content and a question related to it. Your goal is to analyze the license thoroughly, reason through the details, and accurately answer the question based only on the information in the license.

                    ### License Content:
                    {LICENSE_CONTENT}

                    ### Question:
                    {QUESTION}

                    ### Instructions:
                    1. **Read the provided license content carefully** to ensure you understand the terms.
                    2. **Reason through the content** to logically deduce the answer to the question.
                    3. **Answer the question** with either "YES" or "NO", depending on whether the license terms allow or disallow the condition.
                    4. **Provide a clear explanation (1-2 sentences)** justifying your answer.
                        - If you answer "YES", explain why the action or condition is allowed.
                        - If you answer "NO", explain why the action or condition is restricted or prohibited.

                    ### Output Format:
                    Your response should be structured as follows in Markdown:

                    **Answer**: YES/NO
                    **Description**: Explaination for the answer

                    ### Important Notes:
                    - Your answer should be based **solely** on the license content provided.
                    - Do not assume anything beyond the information in the license.
                    - Ensure that your reasoning is clear and your explanation justifies the answer accurately.

                    Please provide your response following the specified format, ensuring it is based only on the content of the license.
                    """
