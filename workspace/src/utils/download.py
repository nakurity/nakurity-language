import os
import sys
import urllib.request
import re
from typing import List, Dict
import requests

class Download:
    def __init__(self, version: str, repo: str):
        self.version = version
        self.repo = repo  # e.g., "username/repo"
        self.base_url = f"https://raw.githubusercontent.com/{repo}/prototype-dev:{version}/downloadables.md"
        self.modules_info = {}

    def fetch_downloadable_md(self):
        try:
            response = requests.get(self.base_url)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Error fetching downloadable.md: {e}")
            sys.exit(1)

    def parse_md(self, md_content: str):
        current_section = None
        for line in md_content.splitlines():
            line = line.strip()
            if line.startswith("##"):
                current_section = line[2:].strip().lower()
                self.modules_info[current_section] = []
            elif line.startswith("-") and current_section:
                match = re.match(r"-\s*(\S+)\s*\((.+?)\)\s*->\s*(.+)", line)
                if match:
                    name, url, dest = match.groups()
                    self.modules_info[current_section].append({
                        "name": name,
                        "url": url,
                        "dest": dest
                    })

    def resolve_modules(self, user_input: str) -> List[Dict]:
        parts = user_input.split("@")
        module_path = parts[0].split("-")
        section = "recommended" if len(parts) == 1 else "all"

        resolved = []
        for mod in module_path:
            section_key = f"{mod}/{section}".lower()
            if section_key in self.modules_info:
                resolved.extend(self.modules_info[section_key])
            else:
                print(f"Warning: Section '{section_key}' not found in downloadable.md")
        return resolved

    def download_modules(self, modules: List[Dict]):
        for mod in modules:
            dest_path = os.path.join(os.getcwd(), mod["dest"])
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            try:
                urllib.request.urlretrieve(mod["url"], dest_path)
                print(f"Downloaded {mod['name']} to {dest_path}")
            except urllib.error.URLError as e:
                print(f"Failed to download {mod['name']}: {e}")

    def handle(self, args: List[str]):
        if not args:
            print("No modules specified.")
            return

        md_content = self.fetch_downloadable_md()
        self.parse_md(md_content)
        modules = self.resolve_modules(args[0])
        self.download_modules(modules)
