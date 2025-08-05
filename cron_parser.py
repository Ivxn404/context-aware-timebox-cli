import subprocess
import platform

def get_cron_jobs():
    if platform.system() == "Windows":
        print("Skipping cron parsing — 'crontab' not available on Windows.")
        return []

    try:
        result = subprocess.run(['crontab', '-l'], capture_output=True, text=True, check=True)
        cron_lines = result.stdout.strip().split('\n')
        cron_jobs = [line for line in cron_lines if line and not line.startswith('#')]
        return cron_jobs
    except subprocess.CalledProcessError:
        print("No cron jobs found.")
        return []

def parse_cron_time(cron_line):
    parts = cron_line.split()
    if len(parts) < 6:
        return None
    return parts[:5]

def main():
    cron_jobs = get_cron_jobs()
    if not cron_jobs:
        print("No active cron jobs detected.")
        return

    print("Your cron job schedules:")
    for job in cron_jobs:
        schedule = parse_cron_time(job)
        if schedule:
            print(f" - {schedule} | full line: {job}")
        else:
            print(f" - Could not parse schedule: {job}")

if __name__ == "__main__":
    main()
