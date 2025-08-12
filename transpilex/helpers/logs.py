import sys

COLORS = {
    "INFO": "\033[38;5;39m",
    "SUCCESS": "\033[38;5;35m",
    "WARNING": "\033[38;5;178m",
    "ERROR": "\033[38;5;203m",
    "RESET": "\033[0m",
}


class Log:

    @staticmethod
    def _print(message: str, color: str = "", file=sys.stdout):
        print(f"{color}{message}{COLORS['RESET']}", file=file)

    @staticmethod
    def info(message: str):
        Log._print(message, COLORS["INFO"])

    @staticmethod
    def success(message: str):
        Log._print(message, COLORS["SUCCESS"])

    @staticmethod
    def warning(message: str):
        Log._print(message, COLORS["WARNING"])

    @staticmethod
    def error(message: str):
        Log._print(message, COLORS["ERROR"], file=sys.stderr)

    @staticmethod
    def created(path: str):
        Log._print(f"Created: {path}", COLORS["SUCCESS"])

    @staticmethod
    def updated(path: str):
        Log._print(f"Updated: {path}", COLORS["SUCCESS"])

    @staticmethod
    def removed(path: str):
        Log._print(f"Removed: {path}", COLORS["ERROR"])

    @staticmethod
    def preserved(path: str):
        Log._print(f"Preserved: {path}", COLORS["INFO"])

    @staticmethod
    def copied(path: str):
        Log._print(f"Copied: {path}", COLORS["SUCCESS"])

    @staticmethod
    def processed(path: str):
        Log._print(f"Processed: {path}", COLORS["SUCCESS"])

    @staticmethod
    def converted(path: str):
        Log._print(f"Converted: {path}", COLORS["SUCCESS"])

    @staticmethod
    def completed(task: str, location: str):
        Log._print(f"{task} completed at: {location}", COLORS["SUCCESS"])

    @staticmethod
    def project_start(project_name: str):
        Log._print(f"Initiating project setup for: {project_name}", COLORS["INFO"])

    @staticmethod
    def project_end(project_name: str, location: str):
        Log._print(f"Project setup completed for '{project_name}' at {location} ✨",
                   COLORS["INFO"])
