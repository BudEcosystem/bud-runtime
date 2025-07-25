import glob
import os
import shutil

from git import Repo


def clone_and_check_repo(repo_url, repo_dir):
    # Delete the folder if it exists to clone afresh
    if os.path.exists(repo_dir):
        print(f"Removing existing repository folder: {repo_dir}")
        shutil.rmtree(repo_dir)

    # Clone the repository
    print(f"Cloning repository {repo_url}...")
    Repo.clone_from(repo_url, repo_dir)

    # Change directory to the cloned repository
    os.chdir(repo_dir)

    # Find all leaderboard_table CSV files
    leaderboard_table_files = glob.glob("leaderboard_table_*.csv")

    # Sort leaderboard files by the date in the filename
    leaderboard_table_files.sort(key=lambda x: int(x[18:-4]))

    # Get the latest leaderboard file
    leaderboard_table_file = leaderboard_table_files[-1]
    print(f"Latest leaderboard file after cloning: {leaderboard_table_file}")
