import time
import subprocess

from transpilex.config.base import COLORS


def check_prerequisite(command, expected_output=None):
    """
    Runs a command to check for a prerequisite.

    Args:
        command (list): The command and its arguments to execute.
        expected_output (str, optional): A string to look for in the output.

    Returns:
        tuple: A tuple containing (status_string, details_string).
    """
    try:
        # Run the command, capturing both stdout and stderr
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=5
        )

        # Combine stdout and stderr for a comprehensive check (handles tools like Java)
        combined_output = (process.stdout + process.stderr).lower()

        # Check if the command was successful and if the expected output is present
        output_check = True
        if expected_output:
            output_check = expected_output.lower() in combined_output

        if process.returncode == 0 and output_check:
            status = "ONLINE"
            details = combined_output.strip().split('\n')[0] # Show the first line of version info
        else:
            # Failure case (command ran but failed or output was wrong)
            status = "OFFLINE"
            error_message = (process.stderr.strip() or process.stdout.strip() or "No output.")
            details = f"Check failed. {COLORS['GRAY']}({error_message.splitlines()[0]}){COLORS['RESET']}"

    except FileNotFoundError:
        # The command executable was not found in the system's PATH
        status = "MISSING"
        details = f"Command '{command[0]}' not found in PATH."
    except subprocess.TimeoutExpired:
        # The command took too long to execute
        status = "TIMEOUT"
        details = f"Command '{' '.join(command)}' timed out."
    except Exception as e:
        # Any other unexpected error
        status = "ERROR"
        details = f"An unexpected error occurred: {e}"

    return status, details

def system_check():
    """
    Performs a system diagnostic check for all required development tools.
    """

    prerequisites = [
        ("Git",               ["git", "--version"], "git"),
        ("Node.js",           ["node", "-v"], "v"),
        ("PHP",               ["php", "-v"], "PHP"),
        ("Composer",          ["composer", "--version"], "Composer"),
        ("Laravel Installer", ["laravel", "--version"], "Laravel Installer"),
        ("Symfony CLI",       ["symfony", "-V"], "Symfony"),
        ("Python",            ["python", "-V"], "Python"),
        ("Ruby",              ["ruby", "-v"], "ruby"),
        ("Rails",             ["rails", "-v"], "Rails"),
        ("Java",              ["java", "-version"], "version"),
        ("Maven",             ["mvn", "--version"], "Apache Maven"),
        (".NET SDK",          ["dotnet", "--version"], None),
    ]

    for name, command, expected_output in prerequisites:
        status, details = check_prerequisite(command, expected_output)

        # Determine the color based on the status
        if status == "ONLINE":
            color = COLORS['SUCCESS']
        elif status == "MISSING" or status == "TIMEOUT":
            color = COLORS['WARNING']
        else:
            color = COLORS['ERROR']

        # Format and print the result line
        status_tag = f"[{color}{status:^9}{COLORS['RESET']}]"
        print(f"{status_tag} {name:<20} {COLORS['GRAY']}{details}{COLORS['RESET']}")

        time.sleep(0.1)