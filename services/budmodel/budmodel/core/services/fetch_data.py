from budmodel.core.services.metrics_collector import (
    alpaca,
    berkeley,
    chatbot_arena,
    live_codebench,
    mteb_leaderboard,
)


def fetch_data():
    try:
        print("")
    except Exception as e:
        print("error", e)
