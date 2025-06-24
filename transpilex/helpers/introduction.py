import time
import random
import subprocess
import sys

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns
from rich.live import Live
from rich.table import Table
from rich.style import Style

console = Console()


# --- System Prerequisite Check Function ---
def check_prerequisite(name, command, success_msg, fail_msg, args=None, expected_output=None):
    """
    Runs a command to check for a prerequisite and returns its status.
    Args:
        name (str): The name of the prerequisite (e.g., "PHP").
        command (list): The command and its arguments to run (e.g., ["php", "--version"]).
        success_msg (str): Message to display on success.
        fail_msg (str): Message to display on failure.
        args (list, optional): Additional arguments for the command.
        expected_output (str, optional): A string expected in the command's output for success.
    Returns:
        tuple: (status_text (rich.Text), details_text (rich.Text))
    """
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
def boot(_):
    """
    Initiates system checks for prerequisites and displays them in a cyberpunk style.
    """
    console.print("[bold cyan]█████████████████████████████████████████████████████████[/bold cyan]")
    console.print("[bold magenta]INITIATING DIAGNOSTICS...[/bold magenta]")
    console.print("[bold green]SYSTEM_SCAN.STARTING...[/bold green]")
    console.print("[dim white]Analyzing core modules and dependencies...[/dim white]\n")

    # Create a table for prerequisite check results
    check_table = Table(
        title="[bold yellow]PRE_REQUISITE_MATRIX[/bold yellow]",
        show_header=True,
        header_style="bold magenta",
        border_style="bright_green",
        padding=(0, 1),
        expand=True
    )
    check_table.add_column("MODULE", style="cyan", justify="left")
    check_table.add_column("STATUS", style="white", justify="center")
    check_table.add_column("DETAILS", style="white", justify="left")

    prerequisites = [
        ("Python Core", ["python", "-V"], "Python environment detected.", "Python not found or version mismatch.",
         "Python"),  # expected_output
        ("PHP", ["php", "-v"], "PHP CLI detected.", "PHP not installed or accessible.", "PHP"),  # expected_output
        ("Django", ["django-admin", "--version"], "Django CLI detected.", "Django not installed or CLI not found."),
        # For PHP frameworks, we check for PHP itself.
        # Direct installation checks for PHP frameworks without project context are complex.
        ("Laravel Runtime", ["php", "-r", "exit(class_exists('Illuminate\\Foundation\\Application') ? 0 : 1);"],
         "Laravel framework detected.", "Laravel framework not available (requires Composer/project).", ""),
        # expected_output (empty string if command succeeds and we just need exit code 0)
        ("CodeIgniter Runtime", ["php", "-r", "exit(class_exists('CodeIgniter\\CodeIgniter') ? 0 : 1);"],
         "CodeIgniter framework detected.", "CodeIgniter framework not available (requires Composer/project).", ""),
        # expected_output
        ("CakePHP Runtime", ["php", "-r", "exit(class_exists('Cake\\Core\\Configure') ? 0 : 1);"],
         "CakePHP framework detected.", "CakePHP framework not available (requires Composer/project).", ""),
    ]

    for name, command, success_msg, fail_msg, *opt_args in prerequisites:
        console.print(f"[dim]>> Scanning: {name}...[/dim]")

        current_args = None
        current_expected_output = None

        if opt_args:
            # If the first optional argument is a list, it's 'args'
            if isinstance(opt_args[0], list):
                current_args = opt_args[0]
                # If there's a second optional argument, it must be 'expected_output'
                if len(opt_args) > 1:
                    current_expected_output = opt_args[1]
            # If the first optional argument is a string, it's 'expected_output'
            elif isinstance(opt_args[0], str):
                current_expected_output = opt_args[0]

        status, details = check_prerequisite(
            name, command, success_msg, fail_msg,
            args=current_args,
            expected_output=current_expected_output
        )
        check_table.add_row(name, status, details)
        time.sleep(0.3)  # Simulate scan time

    console.print(check_table)
    console.print("\n[bold green]SYSTEM_SCAN.COMPLETE.[/bold green]")
    console.print("[bold magenta]DIAGNOSTICS_SUMMARY: [bold cyan]FINALIZED[/bold cyan][/bold magenta]\n")
