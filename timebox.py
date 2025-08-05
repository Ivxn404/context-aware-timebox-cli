import subprocess
from datetime import datetime, timedelta

def get_commit_count(days=7):
    # Get the date 'days' ago in ISO format
    since_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    try:
        # Run git log to count commits since that date
        result = subprocess.run(
            ["git", "log", f"--since={since_date}", "--pretty=format:%H"],
            capture_output=True, text=True, check=True
        )
        commits = result.stdout.strip().split('\n')
        # Filter empty strings (in case no commits)
        commits = [c for c in commits if c]
        return len(commits)
    except subprocess.CalledProcessError:
        print("Error: This folder is not a Git repository or Git is not installed.")
        return None

def suggest_timebox(commit_count):
    # Simple heuristic:
    # High commits → shorter Pomodoro (stay fresh)
    # Low commits → longer flow window (deep work)
    if commit_count is None:
        return "Cannot suggest a timebox without Git data."
    
    if commit_count >= 20:
        return "High activity detected. Suggested timebox: 25 min work + 5 min break (Pomodoro)."
    elif commit_count >= 5:
        return "Moderate activity. Suggested timebox: 50 min work + 10 min break."
    else:
        return "Low activity. Suggested timebox: 90 min deep work + 15 min break."

def main():
    print("Context-Aware Timebox CLI")
    commit_count = get_commit_count()
    if commit_count is not None:
        print(f"Commits in last 7 days: {commit_count}")
    suggestion = suggest_timebox(commit_count)
    print(suggestion)

if __name__ == "__main__":
    main()
