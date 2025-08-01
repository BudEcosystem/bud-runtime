import os

import requests


API_KEY = os.getenv("PERPLEXITY_API_KEY")


# Function to call Perplexity's chat completion API to extract leaderboard data
def fetch_data_from_perplexity(api_key, website_url):
    """Fetch data from Perplexity API."""
    api_endpoint = "https://api.perplexity.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # Prompt for Perplexity AI
    prompt = f"Please extract and provide the LLM  leaderboard table contents as an array of JSON objects from the following URL: {website_url}. Focus on each model's information, including metrics, ranks, and names etc in the table."

    data = {
        "messages": [{"role": "user", "content": prompt}],
        "model": "llama-3.1-sonar-huge-128k-online",
        "temperature": 0.0,
        "max_tokens": 500,
    }

    try:
        response = requests.post(api_endpoint, headers=headers, json=data, timeout=30)
        print(response)
        response.raise_for_status()
        leaderboard_data = response.json().get("choices")[0]["message"]["content"]
        print("response.json()", response.json())
        print(response)
        return leaderboard_data

    except requests.RequestException as e:
        print(f"Error fetching data from {website_url}: {e}")
        return None
    except (KeyError, IndexError):
        print(f"Unexpected response format for {website_url}")
        return None


# Main function to get leaderboard data from multiple URLs
def get_leaderboard_data(api_key):
    """Get leaderboard data from multiple URLs."""
    websites = [
        "https://huggingface.co/spaces/mteb/leaderboard",
        # "https://huggingface.co/spaces/lmsys/chatbot-arena-leaderboard",
        # "https://huggingface.co/spaces/opencompass/open_vlm_leaderboard",
        # "https://huggingface.co/spaces/DontPlanToEnd/UGI-Leaderboard",
        # "https://huggingface.co/spaces/gorilla-llm/berkeley-function-calling-leaderboard",
        # "https://tatsu-lab.github.io/alpaca_eval/",
        # "https://livecodebench.github.io/leaderboard.html"
    ]

    all_leaderboard_data = {}

    for website in websites:
        leaderboard_data = fetch_data_from_perplexity(api_key, website)
        if leaderboard_data:
            all_leaderboard_data[website] = leaderboard_data
            print(f"Successfully retrieved data for {website}")
        else:
            print(f"Failed to retrieve data for {website}")

    return all_leaderboard_data


# Usage example
# api_key = API_KEY  # Replace with your actual API key
# leaderboard_data = get_leaderboard_data(api_key)
# print(json.dumps(leaderboard_data, indent=2))


# import requests
#
# url = "https://api.perplexity.ai/chat/completions"
#
# payload = {
#     "model": "llama-3.1-sonar-small-128k-online",
#     "messages": [
#         {
#             "content": "Please browse web and wait for the data load in the website  extract and provide the LLM  leaderboard table contents as an array of JSON objects from the following URL: https://huggingface.co/spaces/mteb/leaderboard. Focus on each model's information, including all the metric in the tables ., respond only with the JSON without andy help text or descriptive answer , please dont add any hypothetical answers ",
#             "role": "user"
#         }
#     ]
# }
# headers = {
#     "Authorization": "Bearer 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",
#     "Content-Type": "application/json"
# }
#
# response = requests.request("POST", url, json=payload, headers=headers)
#
# print(response.json().get("choices")[0]["message"]["content"])
