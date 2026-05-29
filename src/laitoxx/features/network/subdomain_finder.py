from __future__ import annotations

import json
from urllib.parse import urlparse

import requests

from laitoxx.shared.console import Color

try:
    from laitoxx.core.settings.network_manager import get_session as _get_session
except Exception:
    _get_session = None


def _normalize_domain(value: str) -> str:
    raw = (value or "").strip()
    parsed = urlparse(raw if "://" in raw else f"//{raw}")
    domain = parsed.netloc or parsed.path
    return domain.split("/")[0].strip().lower()


def _extract_subdomains(response_text: str) -> set[str]:
    text = response_text.strip()
    if not text:
        return set()

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = []
        for line in text.splitlines():
            try:
                payload.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if isinstance(payload, dict):
        payload = [payload]

    subdomains: set[str] = set()
    for item in payload if isinstance(payload, list) else []:
        if not isinstance(item, dict):
            continue
        for key in ("common_name", "name_value"):
            value = item.get(key)
            if not value:
                continue
            for part in str(value).splitlines():
                cleaned = part.strip().lstrip("*.")
                if cleaned:
                    subdomains.add(cleaned)
    return subdomains


def find_subdomains():
    """Find subdomains of a domain using crt.sh."""
    domain = _normalize_domain(
        input(
            f"{Color.DARK_GRAY}[{Color.DARK_RED}?{Color.DARK_GRAY}]"
            f"{Color.RED} Enter the target domain (e.g., example.com): {Color.RESET}"
        )
    )

    if not domain:
        print(f"{Color.DARK_GRAY}[{Color.RED}?{Color.DARK_GRAY}]{Color.RED} No domain entered.")
        return

    print(
        f"\n{Color.DARK_GRAY}[{Color.DARK_RED}?{Color.DARK_GRAY}]"
        f"{Color.LIGHT_BLUE} Searching for subdomains of {domain} using crt.sh..."
    )

    url = f"https://crt.sh/?q=%.{domain}&output=json"

    try:
        session = _get_session() if _get_session else requests.Session()
        response = session.get(url, timeout=20)
        response.raise_for_status()
        subdomains = _extract_subdomains(response.text)

        if not subdomains:
            print(
                f"\n{Color.DARK_GRAY}[{Color.RED}?{Color.DARK_GRAY}]{Color.RED} No subdomains found for {domain}."
            )
            return

        print(
            f"\n{Color.DARK_GRAY}[{Color.LIGHT_GREEN}?{Color.DARK_GRAY}]"
            f"{Color.LIGHT_GREEN} Found {len(subdomains)} unique subdomains:"
        )

        sorted_subdomains = sorted(subdomains)
        for subdomain in sorted_subdomains:
            print(f"  {Color.DARK_GRAY}-{Color.WHITE} {subdomain}")

        save_to_file = (
            input(
                f"\n{Color.DARK_GRAY}[{Color.DARK_RED}?{Color.DARK_GRAY}]"
                f"{Color.WHITE} Save the list to a file? (y/n) [default: y]: {Color.RESET}"
            )
            .strip()
            .lower()
        )

        if save_to_file != "n":
            filename = f"{domain}_subdomains.txt"
            with open(filename, "w", encoding="utf-8") as f:
                f.write("\n".join(sorted_subdomains))
            print(
                f"{Color.DARK_GRAY}[{Color.LIGHT_GREEN}?{Color.DARK_GRAY}]"
                f"{Color.LIGHT_GREEN} Subdomain list saved to {filename}"
            )

    except requests.exceptions.Timeout:
        print(
            f"\n{Color.DARK_GRAY}[{Color.RED}?{Color.DARK_GRAY}]{Color.RED} The request to crt.sh timed out."
        )
    except requests.exceptions.RequestException as e:
        print(
            f"\n{Color.DARK_GRAY}[{Color.RED}?{Color.DARK_GRAY}]{Color.RED} An error occurred: {e}"
        )
