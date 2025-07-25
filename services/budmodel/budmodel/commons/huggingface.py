import requests


def get_files_huggingface_space(space_url, pattern_start, pattern_end):
    # Construct the API URL by appending '/tree/main' to the base space_url
    api_url = f"{space_url.rstrip('/')}/tree/main"

    # Make the request to the constructed API URL
    response = requests.get(api_url)

    if response.status_code == 200:
        files = response.json()
        leaderboard_files = [
            file["path"]
            for file in files
            if file["path"].startswith(pattern_start) and file["path"].endswith(pattern_end)
        ]
        return leaderboard_files
    else:
        print(f"Failed to fetch files. Status code: {response.status_code}")
        return []
