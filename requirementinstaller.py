import subprocess
import sys

packages = [
    "flask",
    "openai>=1.0.0",
    "ragflow-sdk",
    "python-dotenv",
    "requests",
    "mysql-connector-python"
]

def install(package):
    print(f"\nInstalling: {package}")
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

if __name__ == "__main__":
    for pkg in packages:
        try:
            install(pkg)
        except Exception as e:
            print(f"Failed to install {pkg}: {e}")
