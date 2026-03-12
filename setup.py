#!/usr/bin/env python3
"""
Setup script for Vald Hub Dashboard
Handles environment setup and dependency installation
"""

import os
import sys
import subprocess
from pathlib import Path


def run_command(cmd, description):
    """Run a shell command and handle errors"""
    print(f"\n📦 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, check=True, text=True)
        print(f"✅ {description} - Done!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - Failed!")
        print(f"Error: {e}")
        return False


def main():
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    print("=" * 50)
    print("🚀 Vald Hub Dashboard Setup")
    print("=" * 50)
    
    # Detect OS and Python command
    is_windows = sys.platform == "win32"
    python_cmd = "python" if is_windows else "python3"
    
    # Check Python version
    print(f"\n🔍 Checking Python installation...")
    result = subprocess.run(f"{python_cmd} --version", shell=True, capture_output=True, text=True)
    print(f"   {result.stdout.strip()}")
    
    # Create virtual environment
    venv_path = "venv"
    if not (project_root / venv_path).exists():
        if is_windows:
            run_command(f"{python_cmd} -m venv {venv_path}", "Creating virtual environment")
            activate_cmd = f"{venv_path}\\Scripts\\activate.bat &&"
        else:
            run_command(f"{python_cmd} -m venv {venv_path}", "Creating virtual environment")
            activate_cmd = f"source {venv_path}/bin/activate &&"
    else:
        print("✅ Virtual environment already exists")
        activate_cmd = f"source {venv_path}/bin/activate &&" if not is_windows else f"{venv_path}\\Scripts\\activate.bat &&"
    
    # Upgrade pip
    run_command(f"{activate_cmd} python -m pip install --upgrade pip", "Upgrading pip")
    
    # Install requirements
    run_command(f"{activate_cmd} pip install -r requirements.txt", "Installing dependencies")
    
    # Create .env file if it doesn't exist
    env_file = project_root / ".env"
    if not env_file.exists():
        print("\n📝 Creating .env file...")
        with open(env_file, 'w') as f:
            f.write("VALD_HUB_API_KEY=your_api_key_here\n")
            f.write("VALD_HUB_BASE_URL=https://api.vald-hub.com\n")
        print("✅ Created .env file (UPDATE WITH YOUR CREDENTIALS)")
    else:
        print("✅ .env file already exists")
    
    # Print next steps
    print("\n" + "=" * 50)
    print("✨ Setup Complete!")
    print("=" * 50)
    print("\n📋 Next Steps:")
    print(f"   1. Edit .env with your Vald Hub API key")
    print(f"   2. Activate virtual environment:")
    if is_windows:
        print(f"      {venv_path}\\Scripts\\activate")
    else:
        print(f"      source {venv_path}/bin/activate")
    print(f"   3. Run the app:")
    print(f"      streamlit run app.py")
    print("\n🌐 App will open at: http://localhost:8501")
    print("=" * 50)


if __name__ == "__main__":
    main()
