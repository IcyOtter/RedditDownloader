import praw
from dotenv import load_dotenv
import os
import requests
import re
import shutil

# --- Load environment variables ---
load_dotenv()

client_id = os.getenv("REDDIT_CLIENT_ID")
client_secret = os.getenv("REDDIT_CLIENT_SECRET")
user_agent = os.getenv("REDDIT_USER_AGENT")
username = os.getenv("REDDIT_USERNAME")
password = os.getenv("REDDIT_PASSWORD")

reddit = praw.Reddit(
    client_id=client_id,
    client_secret=client_secret,
    user_agent=user_agent,
    username=username,
    password=password
)

print("Logged in as:", reddit.user.me())

# --- Load known NSFW subreddit names from file ---
def load_known_nsfw(filepath="known_nsfw.txt"):
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8") as file:
        return sorted(set(
            line.strip().replace("/r/", "").lower()
            for line in file
            if line.strip() and not line.startswith("#")
        ))

# --- Clear master folder ---
def clear_master_folder(master_folder="communitydownloader"):
    if not os.path.exists(master_folder):
        print(f"ℹ️ Master folder '{master_folder}' does not exist.")
        return

    confirm = input(f"⚠️ This will permanently delete all contents inside '{master_folder}'. Continue? [y/N]: ").strip().lower()
    if confirm != "y":
        print("❌ Deletion cancelled.")
        return

    try:
        for item in os.listdir(master_folder):
            path = os.path.join(master_folder, item)
            if os.path.isfile(path) or os.path.islink(path):
                os.unlink(path)
            elif os.path.isdir(path):
                shutil.rmtree(path)
        print(f"✅ All contents deleted from '{master_folder}' (folder itself kept).")
    except Exception as e:
        print(f"❌ Failed to delete contents: {e}")

# --- Downloader ---
def download_images_from_subreddit(subreddit_name, limit=20, master_folder="communitydownloader", cache_folder="cache"):
    subreddit_name = subreddit_name.replace("/r/", "").replace("r/", "")
    subreddit = reddit.subreddit(subreddit_name)
    print(f"Downloading up to {limit} new images from r/{subreddit.display_name}...")

    # --- Folder setup ---
    os.makedirs(master_folder, exist_ok=True)
    safe_name = re.sub(r'[^\w\-]', '_', subreddit_name.lower())
    subfolder_name = f"r_{safe_name}"
    download_folder = os.path.join(master_folder, subfolder_name)

    try:
        os.makedirs(download_folder, exist_ok=True)
    except Exception as e:
        print(f"Failed to create folder {download_folder}: {e}")
        return

    # --- Cache setup ---
    os.makedirs(cache_folder, exist_ok=True)
    cache_file = os.path.join(cache_folder, f"{subfolder_name}.txt")

    # --- Load cache ---
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            cached_urls = set(line.strip() for line in f if line.strip())
    else:
        cached_urls = set()

    count = 0
    new_urls = []

    for post in subreddit.hot(limit=100):
        url = post.url.strip()

        if url.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')) and url not in cached_urls:
            try:
                image_data = requests.get(url).content
                extension = os.path.splitext(url)[1]
                filename = os.path.join(download_folder, f"{subfolder_name}_{count}_{post.id}{extension}")
                with open(filename, "wb") as f:
                    f.write(image_data)
                print(f"Saved: {filename}")
                count += 1
                new_urls.append(url)

                if count >= limit:
                    break
            except Exception as e:
                print(f"Failed to download {url}: {e}")

    # --- Update cache ---
    if new_urls:
        with open(cache_file, "a") as f:
            for url in new_urls:
                f.write(url + "\n")

    if count == 0:
        print("No new images found (all duplicates).")
    else:
        print(f"{count} new images downloaded to '{os.path.abspath(download_folder)}'")

# --- Clear subreddit cache ---
def clear_subreddit_cache(subreddit_name, cache_folder="cache"):
    safe_name = subreddit_name.replace("/", "_").lower()
    cache_file = os.path.join(cache_folder, f"r_{safe_name}.txt")

    if os.path.exists(cache_file):
        os.remove(cache_file)
        print(f"Cache for r/{subreddit_name} cleared.")
    else:
        print(f"No cache found for r/{subreddit_name}.")

# --- Clear all subreddit caches ---
def clear_all_subreddit_caches(cache_folder="cache"):
    if not os.path.exists(cache_folder):
        print(f"Cache folder '{cache_folder}' does not exist.")
        return

    confirm = input(f"⚠️ This will permanently delete all cache files in '{cache_folder}'. Continue? [y/N]: ").strip().lower()
    if confirm != "y":
        print("❌ Deletion cancelled.")
        return

    try:
        for item in os.listdir(cache_folder):
            path = os.path.join(cache_folder, item)
            if os.path.isfile(path):
                os.unlink(path)
        print(f"✅ All cache files deleted from '{cache_folder}'.")
    except Exception as e:
        print(f"❌ Failed to delete cache files: {e}")

# --- Copy master folder to desired location ---
def copy_master_folder(master_folder="communitydownloader"):
    if not os.path.exists(master_folder):
        print(f"Master folder '{master_folder}' does not exist.")
        return

    dest = input("Enter the full path to copy the folder to (e.g., /Users/yourname/Desktop): ").strip()

    if not os.path.isdir(dest):
        print("That destination folder does not exist.")
        return

    dest_path = os.path.join(dest, master_folder)

    # If it already exists, confirm overwrite
    if os.path.exists(dest_path):
        confirm = input(f"⚠️ Folder '{dest_path}' already exists. Overwrite? [y/N]: ").strip().lower()
        if confirm != "y":
            print("Copy cancelled.")
            return
        shutil.rmtree(dest_path)

    try:
        shutil.copytree(master_folder, dest_path)
        print(f"Successfully copied to: {dest_path}")
    except Exception as e:
        print(f"Failed to copy folder: {e}")

# --- Search logic ---
def search_hybrid_subreddits(keyword, limit=100, nsfw_filter="both"):
    keyword_lower = keyword.lower()
    results = []
    seen_subreddits = set()

    print(f"\n🔍 Searching for subreddits with '{keyword}' in the name ({nsfw_filter.upper()})...\n")

    # SFW search
    if nsfw_filter in ("sfw", "both"):
        for subreddit in reddit.subreddits.search(keyword, limit=limit):
            name = subreddit.display_name.lower()
            if keyword_lower in name and not subreddit.over18 and subreddit.subscribers is not None:
                if name not in seen_subreddits:
                    results.append({
                        "name": subreddit.display_name,
                        "title": subreddit.title,
                        "subscribers": subreddit.subscribers,
                        "over18": subreddit.over18
                    })
                    seen_subreddits.add(name)

    # NSFW list
    if nsfw_filter in ("nsfw", "both"):
        known_nsfw = load_known_nsfw()
        for name in known_nsfw:
            if keyword_lower in name and name not in seen_subreddits:
                try:
                    sub = reddit.subreddit(name)
                    if sub.over18 and sub.subscribers is not None:
                        results.append({
                            "name": sub.display_name,
                            "title": sub.title,
                            "subscribers": sub.subscribers,
                            "over18": sub.over18
                        })
                        seen_subreddits.add(name)
                except Exception as e:
                    print(f"Error loading r/{name}: {e}")

    if not results:
        print("No subreddits found with that keyword and filter.")
        return

    results.sort(key=lambda x: x["subscribers"], reverse=True)

    print(f"\n📊 Results sorted by subscribers:\n")
    for i, r in enumerate(results, start=1):
        tag = "🔞" if r["over18"] else "✅"
        print(f"{i}. {tag} r/{r['name']} ({r['subscribers']:,} members) - {r['title']}")

    # Prompt user to pick a subreddit
    try:
        choice = int(input("\nEnter the number of a subreddit to download images from (or 0 to skip): "))
        if 1 <= choice <= len(results):
            selected = results[choice - 1]
            try:
                max_images = int(input("How many images would you like to download? (e.g. 5): "))
                download_images_from_subreddit(selected["name"], limit=max_images)
            except ValueError:
                print("Invalid number. Skipping image download.")
        else:
            print("Skipped image download.")
    except ValueError:
        print("Invalid input. Skipping image download.")


# --- Update known NSFW subreddit list ---
def update_nsfw_list(url="https://raw.githubusercontent.com/IcyOtter/redditNSFW/main/known_nsfw.txt",
                     local_path="known_nsfw.txt"):
    try:
        response = requests.get(url)
        response.raise_for_status()
        with open(local_path, "w") as f:
            f.write(response.text)
        print(f"NSFW list updated. {len(response.text.splitlines())} entries saved to {local_path}")
    except Exception as e:
        print(f"Failed to update NSFW list: {e}")

# --- Main part of script ---
while True:
    if __name__ == "__main__":
        update_nsfw_list()  # Update the known NSFW list at startup

        print("\nMain options:")
        print("1. Search subreddits and optionally download images")
        print("2. Download images from a subreddit by name")
        print("3. Cache management")
        print("4. Backup master download folder")
        print("5. Clear master folder")
        print("0. Exit\n")

        main_choice = input("Choose an action [0–4]: ").strip()

        if main_choice == "1":
            keyword = input("Enter a keyword to search in subreddit names: ").strip()

            print("\nFilter options:")
            print("1. SFW (Safe For Work)")
            print("2. NSFW (Not Safe For Work)")
            print("3. Both\n")
            choice = input("Select a filter [1/2/3]: ").strip()

            nsfw_filter = {
                "1": "sfw",
                "2": "nsfw",
                "3": "both"
            }.get(choice, "both")

            search_hybrid_subreddits(keyword, limit=100, nsfw_filter=nsfw_filter)

        elif main_choice == "2":
            sub = input("Enter the subreddit name (no /r/): ").strip()
            try:
                max_images = int(input("How many images would you like to download? (e.g. 5): "))
                download_images_from_subreddit(sub, limit=max_images)
            except ValueError:
                print("Invalid number. Skipping image download.")

        elif main_choice == "3":
            print("\nCache management options:")
            print("1. Clear all subreddit caches")
            print("2. Clear cache for a specific subreddit\n")
            choice = input("Choose an action [1/2]: ").strip()
            if choice == "1":
                clear_all_subreddit_caches()
            elif choice == "2":
                sub = input("Enter the subreddit name to clear its cache (no /r/): ").strip()
                clear_subreddit_cache(sub)

        elif main_choice == "4":
            copy_master_folder()

        elif main_choice == "5":
            clear_master_folder()

        elif main_choice == "0":
            print("Exiting.")
            exit()

        else:
            print("Invalid choice.")
