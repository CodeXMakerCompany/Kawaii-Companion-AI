import os
import colorama
from colorama import Fore, Back, Style

colorama.init(autoreset=True)

username = os.getenv('USERNAME')
user_name = os.getenv('AI_ASSISTANT_NAME')

class LoggerUtil:
    @staticmethod
    def agent(message: str):
        """Prints messages from the agent in a distinct color and style."""
        print(f"{Back.BLUE}{Fore.WHITE}{Style.BRIGHT}{user_name}: {message}{Style.RESET_ALL}")

    @staticmethod
    def error(message: str):
        """Prints error messages in a distinct color and style."""
        print(f"{Back.RED}{Fore.YELLOW}{Style.BRIGHT}OH NO! {message}{Style.RESET_ALL}")

    @staticmethod
    def user(message: str):
        """Prints user messages in a distinct color and style."""
        print(f"{Back.GREEN}{Fore.BLACK}{Style.NORMAL}{username}: {message}{Style.RESET_ALL}")
