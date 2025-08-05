import os
import sys
import json
import subprocess
import platform
import requests
import time
import re
from datetime import datetime, timedelta

# Optional Windows notifications
if platform.system() == "Windows":
    try:
        from win10toast import ToastNotifier
        toaster = ToastNotifier()
    except ImportError:
        toaster = None
else:
    toaster = None

# CONFIG
GITHUB_OWNER = os.getenv("GITHUB_OWNER") or "Ivxn404"  # default, replace or export env var
GITHUB_TOKEN = os.getenv("GITHUB_PAT")
QUIET_HOURS = (22, 7)  # 10 PM to 7 AM

BASE_DIR = None  # will be detected as git root folder
DATA_DIR = None  # will be BASE_DIR/.timebox


def debug_print(*args):
    # Uncomment to enable debug prints
    # print("[DEBUG]", *args)
    pass


def is_in_quiet_hours():
    now = datetime.now()
    start, end = QUIET_HOURS
    if start < end:
        return start <= now.hour < end
    else:
        return now.hour >= start or now.hour < end


def get_git_root():
    try:
        res = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True)
        root = res.stdout.strip()
        return root
    except Exception:
        return None


class GitAnalyzer:
    def __init__(self, owner, token):
        self.owner = owner
        self.token = token

    def github_api_get(self, url, params=None):
        headers = {}
        if self.token:
            headers['Authorization'] = f'token {self.token}'
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            debug_print(f"GitHub API error {response.status_code}: {response.text}")
            return None
        return response.json()

    def get_all_repos(self):
        repos = []
        page = 1
        while True:
            url = f"https://api.github.com/users/{self.owner}/repos"
            params = {'per_page': 100, 'page': page}
            data = self.github_api_get(url, params)
            if not data:
                break
            if len(data) == 0:
                break
            repos.extend(data)
            page += 1
        return repos

    def get_commit_dates_for_repo(self, repo_name):
        dates = []
        page = 1
        while True:
            url = f"https://api.github.com/repos/{self.owner}/{repo_name}/commits"
            params = {'per_page': 100, 'page': page}
            data = self.github_api_get(url, params)
            if not data:
                break
            if len(data) == 0:
                break
            for commit in data:
                try:
                    dates.append(commit['commit']['author']['date'][:10])
                except KeyError:
                    pass
            page += 1
        return dates

    def get_all_commit_dates(self):
        repos = self.get_all_repos()
        if not repos:
            return []
        all_dates = []
        for repo in repos:
            repo_name = repo['name']
            debug_print(f"Fetching commits for {repo_name}")
            commits = self.get_commit_dates_for_repo(repo_name)
            all_dates.extend(commits)
        unique_dates = list(set(all_dates))
        return unique_dates

    def get_local_commit_dates(self):
        # fallback: get commit dates from local git log
        try:
            res = subprocess.run(
                ["git", "log", "--pretty=format:%ad", "--date=short"],
                capture_output=True,
                text=True,
                check=True,
                cwd=BASE_DIR)
            dates = res.stdout.strip().split('\n')
            return dates
        except Exception:
            return []


class SessionLogger:
    def __init__(self, data_dir):
        self.log_file = os.path.join(data_dir, "focus_log.json")
        self.mood_file = os.path.join(data_dir, "mood_log.json")
        self.notes_file = os.path.join(data_dir, "task_notes.txt")
        # Initialize files if not exist
        if not os.path.exists(self.log_file):
            with open(self.log_file, "w") as f:
                json.dump([], f)
        if not os.path.exists(self.mood_file):
            with open(self.mood_file, "w") as f:
                json.dump([], f)

    def log_session(self, suggestion, intensity, session_type):
        now = datetime.now().isoformat()
        entry = {"timestamp": now, "suggestion": suggestion, "intensity": intensity, "session_type": session_type}
        data = self._load_json(self.log_file)
        data.append(entry)
        self._save_json(self.log_file, data)

    def log_mood(self, mood_score):
        now = datetime.now().isoformat()
        entry = {"timestamp": now, "mood": mood_score}
        data = self._load_json(self.mood_file)
        data.append(entry)
        self._save_json(self.mood_file, data)

    def save_note(self, note):
        with open(self.notes_file, "a", encoding="utf-8") as f:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"{now} - {note}\n")

    def get_mood_trend(self, days=7):
        data = self._load_json(self.mood_file)
        cutoff = datetime.now() - timedelta(days=days)
        filtered = [e for e in data if datetime.fromisoformat(e["timestamp"]) > cutoff]
        return filtered

    def _load_json(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_json(self, path, data):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


class TimeboxPlanner:
    def __init__(self):
        self.owner = GITHUB_OWNER
        self.token = GITHUB_TOKEN
        self.git = GitAnalyzer(self.owner, self.token)
        self.logger = SessionLogger(DATA_DIR)
        self.quiet_hours = QUIET_HOURS

    def get_commit_count_last_days(self, days=7):
        # Prefer local first, fallback to GitHub API if token exists
        dates = []
        if BASE_DIR:
            dates = self.git.get_local_commit_dates()
        if (not dates or len(dates) < 3) and self.token:
            dates = self.git.get_all_commit_dates()
        if not dates:
            return 0, []

        today = datetime.today().date()
        recent_dates = []
        count = 0
        for i in range(days):
            day = today - timedelta(days=i)
            str_day = str(day)
            day_commits = dates.count(str_day)
            if day_commits > 0:
                count += day_commits
                recent_dates.append(str_day)
        return count, recent_dates

    def calculate_streak(self, commit_dates):
        today = datetime.today().date()
        streak = 0
        for i in range(100):
            day = today - timedelta(days=i)
            if str(day) in commit_dates:
                streak += 1
            else:
                if i == 0:
                    break
                else:
                    return streak
        return streak

    def get_work_intensity(self):
        # Analyze last commit diff lines added/removed as proxy intensity
        if not BASE_DIR:
            return 0
        try:
            # last commit diff stats summary
            res = subprocess.run(
                ["git", "diff", "--shortstat", "HEAD~1", "HEAD"],
                capture_output=True, text=True, check=True, cwd=BASE_DIR)
            out = res.stdout.strip()
            match = re.search(r"(\d+) insertions?\(\+\)", out)
            insertions = int(match.group(1)) if match else 0
            match = re.search(r"(\d+) deletions?\(-\)", out)
            deletions = int(match.group(1)) if match else 0
            intensity = insertions + deletions
            return intensity
        except Exception:
            return 0

    def suggest_timebox(self, commit_count, intensity):
        # Combine commit count and intensity for suggestions
        if commit_count >= 20 and intensity > 50:
            return "High activity: 45 min sprint + 5 min break", "sprint"
        elif commit_count >= 10:
            return "Moderate activity: 60 min deep work + 10 min break", "deep"
        elif commit_count > 0:
            return "Low activity: 90 min deep work + 15 min break", "deep"
        else:
            return "No recent commits: Start with a 25 min Pomodoro + 5 min break", "pomodoro"

    def print_commit_graph(self, commit_dates, days=7):
        print("\n📊 Git Pulse (last 7 days commits):")
        today = datetime.today().date()
        counts = []
        for i in reversed(range(days)):
            day = today - timedelta(days=i)
            count = commit_dates.count(str(day))
            counts.append(count)
        max_count = max(counts) if counts else 1
        max_count = max(max_count, 1)
        for i, count in enumerate(counts):
            bar = "█" * count if count > 0 else "-"
            print(f"Day {i+1}: {bar} ({count})")

    def print_mood_trend(self, mood_entries, days=7):
        print("\n🙂 Mood trend (last 7 days):")
        if not mood_entries:
            print("No mood data recorded.")
            return
        # Aggregate mood by day
        day_map = {}
        for entry in mood_entries:
            dt = datetime.fromisoformat(entry["timestamp"]).date()
            day_map.setdefault(dt, []).append(entry["mood"])
        # Average mood per day
        today = datetime.today().date()
        for i in reversed(range(days)):
            day = today - timedelta(days=i)
            moods = day_map.get(day, [])
            avg = round(sum(moods)/len(moods), 2) if moods else None
            bar = "█" * int(avg) if avg else "-"
            print(f"Day {days - i}: {bar} ({avg if avg else '-'})")

    def show_achievements(self, streak):
        print("\n🏆 Achievements:")
        if streak >= 10:
            print(r"""
 __   __            _    _ _       _ 
 \ \ / /           | |  | (_)     | |
  \ V /___  _   _  | |  | |_ _ __ | |
   \ // _ \| | | | | |  | | | '_ \| |
   | | (_) | |_| | | |__| | | | | |_|
   \_/\___/ \__,_|  \____/|_|_| |_(_)
                                        
            """)
            print(f"🔥 Epic {streak}-day streak! Keep smashing it!\n")
        elif streak >= 5:
            print(f"🔥 Great job! {streak}-day streak!\n")
        else:
            print("Keep building your streak!\n")

    def suggest_break(self, session_type):
        tips = {
            "pomodoro": "Take a short 5 min break: stretch your arms and relax your eyes.",
            "deep": "Take a longer break: walk for 10 minutes or meditate.",
            "sprint": "You’ve been sprinting hard! Consider a 15 min break with some light exercise."
        }
        return tips.get(session_type, "Take a break!")

    def prompt_mood(self):
        try:
            mood = int(input("Rate your focus/mood this session (1-5): ").strip())
            if 1 <= mood <= 5:
                self.logger.log_mood(mood)
                print("Mood logged.")
            else:
                print("Invalid input. Mood not logged.")
        except Exception:
            print("Invalid input. Mood not logged.")

    def start_timer(self, minutes):
        try:
            total_seconds = minutes * 60
            print(f"\n⏱️ Starting timer for {minutes} minutes. Press Ctrl+C to cancel.")
            while total_seconds > 0:
                mins, secs = divmod(total_seconds, 60)
                timer = f"{mins:02d}:{secs:02d}"
                print(f"\rTime left: {timer}", end="")
                time.sleep(1)
                total_seconds -= 1
            print("\n⏰ Time's up! Take a break or start a new session.")
            if toaster:
                toaster.show_toast("Timebox Timer", "Time's up! Take a break or start a new session.", duration=5)
        except KeyboardInterrupt:
            print("\n⏸️ Timer cancelled.")

    def run(self):
        if is_in_quiet_hours():
            print("⚠️ Currently in quiet hours — no session suggestions or timers.")
            return

        count, recent_dates = self.get_commit_count_last_days()
        intensity = self.get_work_intensity()
        suggestion, session_type = self.suggest_timebox(count, intensity)
        now_str = datetime.now().strftime("%A, %I:%M %p")
        streak = self.calculate_streak(recent_dates)

        print("⏳ Context-Aware Timebox Planner (Enhanced CLI)")
        print("-" * 50)
        print(f"Commits last 7 days: {count}")
        print(f"Git streak: {streak} day(s)")
        print(f"Work intensity (lines changed last commit): {intensity}")
        print(f"Suggested session: {suggestion}")
        print(f"Current time: {now_str}")

        self.show_achievements(streak)
        self.print_commit_graph(recent_dates)
        self.print_mood_trend(self.logger.get_mood_trend())

        self.logger.log_session(suggestion, intensity, session_type)

        print("\n" + self.suggest_break(session_type))

        start = input("\nStart timer now? (y/n): ").strip().lower()
        if start == "y":
            note = input("Add a short note for this session (or leave blank): ").strip()
            if note:
                self.logger.save_note(note)
                print("📝 Note saved.")
            self.prompt_mood()
            mins_match = re.search(r"(\d+)", suggestion)
            minutes = int(mins_match.group(1)) if mins_match else 25
            self.start_timer(minutes)
        else:
            print("Okay, session not started.")

def main():
    global BASE_DIR, DATA_DIR
    BASE_DIR = get_git_root()
    if not BASE_DIR:
        print("⚠️ Not inside a git repository. Please cd into a git repo folder and rerun.")
        sys.exit(1)

    DATA_DIR = os.path.join(BASE_DIR, ".timebox")
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    planner = TimeboxPlanner()
    planner.run()


if __name__ == "__main__":
    main()
