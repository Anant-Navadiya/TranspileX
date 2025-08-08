import sys

class Messenger:
    COLORS = {
        "INFO": "\033[38;5;39m",  # A pleasant, professional blue
        "SUCCESS": "\033[38;5;35m",  # A calmer, sea-green
        "WARNING": "\033[38;5;178m",  # A visible but not jarring amber/gold
        "ERROR": "\033[38;5;160m",  # A clear, but less intense red
        "RESET": "\033[0m",
    }

    SYMBOLS = {
        "START":    "╠═",
        "INFO":     "╠═",
        "SUCCESS":  "╠═",
        "WARNING":  "╠═",
        "ERROR":    "╠═",
        "REMOVED":  "╠═",
        "PRESERVE": "╠═",
        "REPLACED": "╠═",
        "UPDATED":  "╠═",
        "COMPLETE": "╠═",
        "END":      "╚═",
    }

    @staticmethod
    def _print(symbol_key: str, message: str, color: str = "", file=sys.stdout):
        symbol = Messenger.SYMBOLS.get(symbol_key, "")
        print(f"{color}{symbol} {message}{Messenger.COLORS['RESET']}", file=file)

    @staticmethod
    def info(message: str):
        Messenger._print("INFO", message, Messenger.COLORS["INFO"])

    @staticmethod
    def success(message: str):
        Messenger._print("SUCCESS", message, Messenger.COLORS["SUCCESS"])

    @staticmethod
    def warning(message: str):
        Messenger._print("WARNING", message, Messenger.COLORS["WARNING"])

    @staticmethod
    def error(message: str):
        Messenger._print("ERROR", message, Messenger.COLORS["ERROR"], file=sys.stderr)

    @staticmethod
    def removed(message: str):
        Messenger._print("REMOVED", message, Messenger.COLORS["ERROR"])

    @staticmethod
    def preserved(message: str):
        Messenger._print("PRESERVE", message, Messenger.COLORS["INFO"])

    @staticmethod
    def replaced(file_path: str):
        Messenger._print("REPLACED", f"Replaced includes in: {file_path}", Messenger.COLORS["INFO"])

    @staticmethod
    def updated(file_path: str):
        Messenger._print("UPDATED", f"Updated {file_path}", Messenger.COLORS["INFO"])

    @staticmethod
    def completed(task: str, location: str):
        Messenger._print("COMPLETE", f"{task} completed at: {location}", Messenger.COLORS["SUCCESS"])

    @staticmethod
    def project_start(project_name: str):
        Messenger._print("START", f"Initiating project setup for: {project_name}", Messenger.COLORS["INFO"])

    @staticmethod
    def project_end(project_name: str, location: str):
        Messenger._print("END", f"Completed project setup for '{project_name}' at {location} ✨", Messenger.COLORS["SUCCESS"])
