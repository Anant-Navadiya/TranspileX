class Messenger:

    @staticmethod
    def info(message: str):
        print(f"ℹ️{message}")

    @staticmethod
    def success(message: str):
        print(f"✅{message}")

    @staticmethod
    def warning(message: str):
        print(f"⚠️{message}")

    @staticmethod
    def error(message: str):
        print(f"❌{message}")

    @staticmethod
    def removed(message: str):
        print(f"🗑️{message}")

    @staticmethod
    def replaced(file_path: str):
        print(f"🔁Replaced includes in: {file_path}")

    @staticmethod
    def updated(file_path: str):
        print(f"🔁Updated {file_path}")

    @staticmethod
    def completed(task: str, location: str):
        print(f"🎉{task} completed at: {location}")