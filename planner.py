import subprocess
import platform
from datetime import datetime

def get_commit_count():
    try:
        result = subprocess.run(
            ['git', 'rev-list', '--count', '--since=7.days', 'HEAD'],
            capture_output=True, text=True, check=True
        )
        return int(result.stdout.strip())
    except Exception as e:
        print("Error getting commit count:", e)
        return 0

def suggest_timebox(commit_count):
    if commit_count >= 20:
        return "High activity: 45 min sprint + 5 min break"
    elif commit_count >= 10:
        return "Moderate activity: 60 min deep work + 10 min break"
    elif commit_count > 0:
        return "Low activity: 90 min deep work + 15 min break"
    else:
        return "No recent commits: Start with a 25 min Pomodoro + 5 min break"

def main():
    print("⏳ Context-Aware Timebox Planner")
    print("-" * 40)
    
    count = get_commit_count()
    print(f"Commits in last 7 days: {count}")
    
    suggestion = suggest_timebox(count)
    print(f"Suggested session: {suggestion}")
    
    now = datetime.now().strftime("%A, %I:%M %p")
    print(f"Current time: {now}")
    
    if platform.system() == "Windows":
        print("(Skipping calendar checks on Windows)")

if __name__ == "__main__":
    main()
