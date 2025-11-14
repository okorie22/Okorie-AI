import os
import sys
import platform
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw

def check_requirements():
    """Check if required packages are installed"""
    print("🚀 AI Trading System - Build Script")
    print("==================================")
    
    required_packages = ["PyInstaller", "PySide6"]
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ Required package found: {package}")
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ Missing required packages:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\nPlease install missing packages with:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    return True

def create_icon():
    """Create a simple icon for the application"""
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    icon_path = os.path.join(parent_dir, "icon.ico")
    
    # Skip if icon already exists
    if os.path.exists(icon_path):
        print(f"✅ Icon already exists at {icon_path}")
        return icon_path
    
    # Create a simple icon
    img_size = 256
    img = Image.new('RGBA', (img_size, img_size), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw a cyberpunk-style moon icon
    # Background circle
    draw.ellipse([(20, 20), (img_size-20, img_size-20)], fill=(13, 13, 20))
    # Cyan border
    draw.arc([(20, 20), (img_size-20, img_size-20)], 0, 360, fill=(0, 255, 255), width=5)
    # Purple accent
    draw.arc([(40, 40), (img_size-40, img_size-40)], 45, 180, fill=(255, 0, 255), width=3)
    # Green accent
    draw.arc([(60, 60), (img_size-60, img_size-60)], 180, 315, fill=(0, 255, 0), width=3)
    
    # Save as .ico
    img.save(icon_path)
    print(f"✅ Created {icon_path} file")
    
    return icon_path

def build_executable():
    """Build executable using PyInstaller"""
    system = platform.system().lower()
    print(f"🔨 Building executable for {system}...")
    
    # Get paths
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    icon_path = os.path.join(parent_dir, "icon.ico")
    ui_path = os.path.join(parent_dir, "trading_ui_connected.py")
    
    # Get the Python executable path
    python_exe = sys.executable
    
    # Use the Python executable to run PyInstaller
    if system == "windows":
        cmd = [
            python_exe, 
            "-m", "PyInstaller",
            "--name=AI_Trading_System",
            "--windowed",
            f"--icon={icon_path}",
            ui_path
        ]
    else:
        cmd = [
            python_exe,
            "-m", "PyInstaller",
            "--name=AI_Trading_System",
            "--windowed",
            f"--icon={icon_path}",
            ui_path
        ]
    
    try:
        # Change to parent directory for build
        os.chdir(parent_dir)
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ Build failed with error:")
            print(result.stderr)
            return False
        else:
            print("✅ Build completed successfully!")
            return True
    except Exception as e:
        print(f"❌ Build failed with exception: {str(e)}")
        return False

def package_distribution():
    """Package the distribution as a zip file"""
    system = platform.system().lower()
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dist_dir = Path(os.path.join(parent_dir, "dist/AI_Trading_System"))
    
    if not dist_dir.exists():
        print(f"❌ Distribution directory not found: {dist_dir}")
        return False
    
    # Create zip file
    zip_name = f"AI_Trading_System_{system}.zip"
    print(f"📦 Packaging distribution as {zip_name}...")
    
    try:
        import shutil
        os.chdir(parent_dir)
        shutil.make_archive("AI_Trading_System_" + system, 'zip', "dist/AI_Trading_System")
        print(f"✅ Package created: {zip_name}")
        return True
    except Exception as e:
        print(f"❌ Packaging failed with error: {str(e)}")
        return False

def main():
    if not check_requirements():
        return
    
    icon_path = create_icon()
    
    if build_executable():
        package_distribution()
        print("\n✨ Build process completed!")
        print("You can find your executable in the dist/AI_Trading_System directory")
    else:
        print("\n❌ Build process failed")

if __name__ == "__main__":
    main()
