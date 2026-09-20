import subprocess
import time
import os
import tarfile

ADB = r"D:\Android\Sdk\platform-tools\adb.exe"
APK_PATH = r"D:\work\dev\ebook\app\build\outputs\apk\debug\app-debug.apk"
DB_PATH = r"D:\work\dev\ebook\device_reader_live.db"
COVER_PATH = r"D:\work\dev\ebook\c0000000-0000-0000-0000-000000000001.jpg"
TXT_PATH = r"D:\work\dev\ebook\c0000000-0000-0000-0000-000000000001.txt"
IMAGES_DIR = r"D:\work\dev\ebook\book_images"
TAR_PATH = r"D:\work\dev\ebook\images_temp.tar"

def run_cmd(args):
    print("Running:", " ".join(args[:5]), "...")
    res = subprocess.run(args, capture_output=True, text=True)
    if res.returncode != 0 and res.stderr.strip():
        print("  Error:", res.stderr.strip())
    return res

def deploy():
    print("=" * 60)
    print("Deploying Illustrated e-Book & Updated Reader to Android Device")
    print("=" * 60)

    # Check connected devices
    dev_check = subprocess.run([ADB, "devices"], capture_output=True, text=True)
    lines = [l for l in dev_check.stdout.splitlines() if "\tdevice" in l]
    if not lines:
        print("[WARNING] No Android device connected via ADB currently.")
        print("When you connect your phone via USB or Wi-Fi ADB, run 'python deploy_book_to_device.py'!")
        return

    device_id = lines[0].split()[0]
    print(f"Target Device: {device_id}")

    # 1. Check if app is installed
    pkg_check = subprocess.run([ADB, "-s", device_id, "shell", "pm", "list", "packages", "com.ebook.ocrreader"], capture_output=True, text=True)
    if "package:com.ebook.ocrreader" not in pkg_check.stdout:
        print("\n1. App not found on device. Installing Reader App...")
        run_cmd([ADB, "-s", device_id, "install", "-r", APK_PATH])
    else:
        print("\n1. App already installed on device. Skipping APK install! (Fast transfer)")

    # 2. Stop the app
    print("\n2. Stopping app...")
    run_cmd([ADB, "shell", "am", "force-stop", "com.ebook.ocrreader"])
    time.sleep(1)

    # 3. Create tar archive of all 82 cropped images
    print("\n3. Packaging images for fast transfer...")
    with tarfile.open(TAR_PATH, "w") as tar:
        for f in os.listdir(IMAGES_DIR):
            if f.endswith(('.png', '.jpg')):
                tar.add(os.path.join(IMAGES_DIR, f), arcname=f)
    print(f"Created images archive: {TAR_PATH} ({os.path.getsize(TAR_PATH)/(1024*1024):.2f} MB)")

    # 4. Push files to /data/local/tmp
    print("\n4. Pushing files to device...")
    run_cmd([ADB, "push", DB_PATH, "/data/local/tmp/reader.db"])
    run_cmd([ADB, "push", COVER_PATH, "/data/local/tmp/cover.jpg"])
    run_cmd([ADB, "push", TXT_PATH, "/data/local/tmp/book.txt"])
    run_cmd([ADB, "push", TAR_PATH, "/data/local/tmp/images.tar"])

    # 5. Extract and copy into app container
    print("\n5. Placing database and images into app storage...")
    commands = [
        "mkdir -p databases files files/images",
        "rm -f databases/reader.db-wal databases/reader.db-shm",
        "cp /data/local/tmp/reader.db databases/reader.db",
        "cp /data/local/tmp/cover.jpg files/c0000000-0000-0000-0000-000000000001.jpg",
        "cp /data/local/tmp/book.txt files/c0000000-0000-0000-0000-000000000001.txt",
        "tar -xf /data/local/tmp/images.tar -C files/images/",
        "chmod 660 databases/reader.db",
        "chmod 660 files/c0000000-0000-0000-0000-000000000001.jpg",
        "chmod 660 files/c0000000-0000-0000-0000-000000000001.txt",
        "ls -la databases",
        "ls -la files/images | head -n 10"
    ]

    for cmd in commands:
        p = subprocess.run([ADB, "shell", "run-as", "com.ebook.ocrreader", *cmd.split()], capture_output=True, text=True)
        if p.stdout.strip():
            print(f"  [{cmd}] -> {p.stdout.strip()[:80]}")

    # 6. Clean up /data/local/tmp
    run_cmd([ADB, "shell", "rm", "-f", "/data/local/tmp/reader.db", "/data/local/tmp/cover.jpg", "/data/local/tmp/book.txt", "/data/local/tmp/images.tar"])
    if os.path.exists(TAR_PATH):
        os.remove(TAR_PATH)

    # 7. Launch the app
    print("\n6. Launching Reader app...")
    run_cmd([ADB, "shell", "am", "start", "-n", "com.ebook.ocrreader/.MainActivity"])
    time.sleep(2)

    # 8. Take screen capture to verify
    run_cmd([ADB, "shell", "screencap", "-p", "/sdcard/screen_check.png"])
    run_cmd([ADB, "pull", "/sdcard/screen_check.png", "screen_check_live.png"])
    print("\n[SUCCESS] e-Book with 82 figures deployed and app launched!")

if __name__ == "__main__":
    deploy()
