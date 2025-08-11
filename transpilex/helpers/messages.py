import sys


class Messenger:
    COLORS = {
        "INFO": "\033[38;5;39m",
        "SUCCESS": "\033[38;5;35m",
        "WARNING": "\033[38;5;178m",
        "ERROR": "\033[38;5;203m",
        "RESET": "\033[0m",
    }

    @staticmethod
    def _print(message: str, color: str = "", file=sys.stdout):
        print(f"{color}{message}{Messenger.COLORS['RESET']}", file=file)

    @staticmethod
    def info(message: str):
        Messenger._print(message, Messenger.COLORS["INFO"])

    @staticmethod
    def success(message: str):
        Messenger._print(message, Messenger.COLORS["SUCCESS"])

    @staticmethod
    def warning(message: str):
        Messenger._print(message, Messenger.COLORS["WARNING"])

    @staticmethod
    def error(message: str):
        Messenger._print(message, Messenger.COLORS["ERROR"], file=sys.stderr)

    @staticmethod
    def created(path: str):
        Messenger._print(f"Created: {path}", Messenger.COLORS["SUCCESS"])

    @staticmethod
    def updated(path: str):
        Messenger._print(f"Updated: {path}", Messenger.COLORS["SUCCESS"])

    @staticmethod
    def removed(path: str):
        Messenger._print(f"Removed: {path}", Messenger.COLORS["ERROR"])

    @staticmethod
    def preserved(path: str):
        Messenger._print(f"Preserved: {path}", Messenger.COLORS["INFO"])

    @staticmethod
    def copied(path: str):
        Messenger._print(f"Copied: {path}", Messenger.COLORS["SUCCESS"])

    @staticmethod
    def processed(path: str):
        Messenger._print(f"Processed: {path}", Messenger.COLORS["SUCCESS"])

    @staticmethod
    def converted(path: str):
        Messenger._print(f"Converted: {path}", Messenger.COLORS["SUCCESS"])

    @staticmethod
    def completed(task: str, location: str):
        Messenger._print(f"{task} completed at: {location}", Messenger.COLORS["SUCCESS"])

    @staticmethod
    def project_start(project_name: str):
        Messenger._print(f"Initiating project setup for: {project_name}", Messenger.COLORS["INFO"])

    @staticmethod
    def project_end(project_name: str, location: str):
        Messenger._print(f"Project setup Completed for '{project_name}' at {location} ✨",
                         Messenger.COLORS["INFO"])
