import subprocess
import time
import os
import tarfile
import glob

ADB = r"D:\Android\Sdk\platform-tools\adb.exe"
DEVICE_ID = "R3CX202A5NE"
APK_PATH = r"D:\work\dev\ebook\app\build\outputs\apk\debug\app-debug.apk"

# Find output directory
output_dirs = [d for d in glob.glob(r"D:\work\dev\ebook\output\*") if os.path.isdir(d)]
if not output_dirs:
    raise FileNotFoundError("Output directory not found!")
OUT_DIR = output_dirs[0]

BOOK_ID = "c0000000-0000-0000-0000-000000000001"

DB_PATH = os.path.join(OUT_DIR, "reader.db")
COVER_PATH = os.path.join(OUT_DIR, "cover.jpg")
if not os.path.exists(COVER_PATH):
    COVER_PATH = os.path.join(OUT_DIR, f"{BOOK_ID}.jpg")

TXT_PATH = os.path.join(OUT_DIR, "book.txt")
if not os.path.exists(TXT_PATH):
    TXT_PATH = os.path.join(OUT_DIR, f"{BOOK_ID}.txt")

IMAGES_DIR = os.path.join(OUT_DIR, "images")

# Find zip file in OUT_DIR
zips = [f for f in glob.glob(os.path.join(OUT_DIR, "*.zip"))]
ZIP_PATH = zips[0] if zips else None
TAR_PATH = r"D:\work\dev\ebook\images_temp.tar"

def run_adb(cmd_list):
    full_cmd = [ADB, "-s", DEVICE_ID] + cmd_list
    print(f"-> adb {' '.join(cmd_list[:6])}")
    res = subprocess.run(full_cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0 and res.stderr.strip():
        print(f"   [Error] {res.stderr.strip()[:120]}")
    elif res.stdout.strip():
        print(f"   [Output] {res.stdout.strip()[:100]}")
    return res

def deploy():
    print("=" * 65)
    print("  Deploying Latest APK & Perfect Book Package to Galaxy (S24 Ultra)")
    print("=" * 65)

    # 1. Install APK if needed
    print("\n[Step 1/6] Checking Reader APK installation...")
    pkg_check = run_adb(["shell", "pm", "list", "packages", "com.ebook.ocrreader"])
    if "com.ebook.ocrreader" in pkg_check.stdout:
        print("   -> App already installed on Galaxy, skipping APK re-install.")
    else:
        print("   -> App not found on Galaxy, installing APK...")
        if not os.path.exists(APK_PATH):
            raise FileNotFoundError(f"APK not found: {APK_PATH}")
        install_res = run_adb(["install", "-r", "-d", APK_PATH])
        if "Success" not in install_res.stdout:
            print("[Notice] Regular install output:", install_res.stdout)

    # 2. Stop the app
    print("\n[Step 2/6] Stopping app process...")
    run_adb(["shell", "am", "force-stop", "com.ebook.ocrreader"])
    time.sleep(1)

    # 3. Package images into tar archive for fast transfer
    print("\n[Step 3/6] Packaging 95 high-res diagram images...")
    img_files = [f for f in os.listdir(IMAGES_DIR) if f.endswith(('.png', '.jpg'))]
    print(f"   Packaging {len(img_files)} images into {TAR_PATH}...")
    with tarfile.open(TAR_PATH, "w") as tar:
        for f in img_files:
            tar.add(os.path.join(IMAGES_DIR, f), arcname=f)
    print(f"   Archive created: {os.path.getsize(TAR_PATH)/(1024*1024):.2f} MB")

    # 4. Push files to device (/data/local/tmp and /sdcard/Download)
    print("\n[Step 4/6] Pushing database, cover, images, and ZIP package to Galaxy...")
    run_adb(["push", DB_PATH, "/data/local/tmp/reader.db"])
    run_adb(["push", COVER_PATH, "/data/local/tmp/cover.jpg"])
    run_adb(["push", TXT_PATH, "/data/local/tmp/book.txt"])
    run_adb(["push", TAR_PATH, "/data/local/tmp/images.tar"])
    
    # Also push the ZIP package directly to the Galaxy Download folder
    if ZIP_PATH and os.path.exists(ZIP_PATH):
        zip_name = os.path.basename(ZIP_PATH)
        print(f"   Copying {zip_name} to /sdcard/Download/...")
        run_adb(["push", ZIP_PATH, f"/sdcard/Download/{zip_name}"])
        run_adb(["push", ZIP_PATH, "/sdcard/Download/llm-finetuning.zip"])

    # 5. Inject database and images directly into app container
    print("\n[Step 5/6] Injecting clean database and images into app storage...")
    commands = [
        "mkdir -p databases files files/images",
        "rm -f databases/reader.db databases/reader.db-wal databases/reader.db-shm",
        "cp /data/local/tmp/reader.db databases/reader.db",
        f"cp /data/local/tmp/cover.jpg files/{BOOK_ID}.jpg",
        f"cp /data/local/tmp/book.txt files/{BOOK_ID}.txt",
        "tar -xf /data/local/tmp/images.tar -C files/images/",
        "chmod 660 databases/reader.db",
        f"chmod 660 files/{BOOK_ID}.jpg",
        f"chmod 660 files/{BOOK_ID}.txt",
        "ls -la databases",
        "ls -la files/images | head -n 8"
    ]

    for cmd in commands:
        p = subprocess.run([ADB, "-s", DEVICE_ID, "shell", "run-as", "com.ebook.ocrreader", *cmd.split()],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if p.stdout.strip():
            print(f"   [run-as] {cmd[:25]:<25} -> {p.stdout.strip()[:80]}")

    # Clean up temporary files on device
    run_adb(["shell", "rm", "-f", "/data/local/tmp/reader.db", "/data/local/tmp/cover.jpg", "/data/local/tmp/book.txt", "/data/local/tmp/images.tar"])
    if os.path.exists(TAR_PATH):
        os.remove(TAR_PATH)

    # 6. Wake screen, Launch the app and capture screen
    print("\n[Step 6/6] Launching Reader App on Galaxy S24 Ultra...")
    run_adb(["shell", "input", "keyevent", "224"])  # WAKEUP
    run_adb(["shell", "input", "keyevent", "82"])   # MENU / UNLOCK
    time.sleep(1)
    run_adb(["shell", "am", "start", "-a", "android.intent.action.MAIN", "-c", "android.intent.category.LAUNCHER", "-n", "com.ebook.ocrreader/.MainActivity"])
    time.sleep(3)

    # Screencap
    print("   Capturing device screen...")
    run_adb(["shell", "screencap", "-p", "/sdcard/deploy_check.png"])
    run_adb(["pull", "/sdcard/deploy_check.png", "galaxy_screen_check.png"])
    run_adb(["shell", "rm", "-f", "/sdcard/deploy_check.png"])

    print("\n" + "=" * 65)
    print("  [ALL SUCCESS] APK installed & Book package loaded into Galaxy!")
    print("=" * 65)

if __name__ == "__main__":
    deploy()
