class Messenger:

    @staticmethod
    def info(message: str):
        print(f"\nℹ️  {message}")

    @staticmethod
    def success(message: str):
        print(f"\n✅ {message}")

    @staticmethod
    def warning(message: str):
        print(f"\n⚠️ {message}")

    @staticmethod
    def error(message: str):
        print(f"\n❌ {message}")

    @staticmethod
    def replaced(file_path: str):
        print(f"\n🔁 Replaced includes in: {file_path}")

    @staticmethod
    def completed(task: str, location: str):
        print(f"\n🎉 {task} complete at: {location}")