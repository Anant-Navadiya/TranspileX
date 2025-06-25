import time
import subprocess

from rich.console import Console
from rich.text import Text
from rich.table import Table

console = Console()


def check_prerequisite(name, command, success_msg, fail_msg, args=None, expected_output=None):
    try:
        if args:
            command_to_run = command + args
        else:
            command_to_run = command

        # Attempt to run the command, checking for existence or expected output
        process = subprocess.run(
            command_to_run,
            capture_output=True,
            text=True,
            check=False,  # Don't raise CalledProcessError for non-zero exit codes
            timeout=5  # Prevent hanging
        )

        output_check = True
        if expected_output:
            output_check = expected_output.lower() in process.stdout.lower()

        if process.returncode == 0 and output_check:
            status = Text("ONLINE", style="bold bright_green")
            details = Text(success_msg, style="dim green")
        else:
            status = Text("OFFLINE", style="bold red")
            details = Text(
                f"{fail_msg} [dim]{process.stderr.strip() or process.stdout.strip() or 'Command not found.'}[/dim]",
                style="dim red")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        status = Text("MISSING", style="bold yellow")
        details = Text(f"Executable for '{command[0]}' not found or timed out.", style="dim yellow")
    except Exception as e:
        status = Text("ERROR", style="bold red")
        details = Text(f"Unexpected error during check: {e}", style="dim red")
    return status, details


# --- Boot Function (renamed from boot_sequence) ---
from rich.align import Align
from rich.rule import Rule


def system_check(_):
    console.print(Rule("[bold orange1]TRANSPILEX DIAGNOSTIC MODE[/bold orange1]", style="green"))

    table = Table(
        show_header=True,
        header_style="bold orange1",
        box=None,
        pad_edge=False,
        expand=False
    )

    table.add_column("MODULE", justify="left", style="bold white", width=18)
    table.add_column("STATUS", justify="center", style="bold", width=10)
    table.add_column("DETAILS", justify="left", style="dim", no_wrap=False)

    prerequisites = [
        ("Node.js", ["node", "-v"], "Node.js is installed.", "Node.js not found or not in PATH.", "v"),
        ("PHP", ["php", "-v"], "PHP CLI detected.", "PHP not installed or accessible.", "PHP"),
        ("Composer", ["composer", "--version"], "Composer detected.", "Composer not installed.", "Composer"),
        ("Symfony CLI", ["symfony", "-V"], "Symfony CLI detected.", "Symfony CLI not installed.", "Symfony"),
        ("Python", ["python", "-V"], "Python environment detected.", "Python not found or version mismatch.", "Python"),
        ("Python venv", ["python", "-c",
                         "import sys; print(hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix))"],
         "Virtual environment detected.", "Not in a virtual environment or unable to detect.", "True"),
        (".NET SDK", ["dotnet", "--version"], ".NET SDK detected.", ".NET SDK not installed."),
        ("Git", ["git", "--version"], "Git is installed.", "Git not installed or not in PATH.", "git"),
    ]

    for name, command, success_msg, fail_msg, *opt_args in prerequisites:
        current_args = None
        current_expected_output = None

        if opt_args:
            if isinstance(opt_args[0], list):
                current_args = opt_args[0]
                if len(opt_args) > 1:
                    current_expected_output = opt_args[1]
            elif isinstance(opt_args[0], str):
                current_expected_output = opt_args[0]

        status, details = check_prerequisite(
            name, command, success_msg, fail_msg,
            args=current_args,
            expected_output=current_expected_output
        )
        table.add_row(name, status, details)
        time.sleep(0.2)

    console.print()
    console.print(Align.center(table))
    console.print()
    console.print(Rule(style="green"))
