from __future__ import annotations

from urllib.parse import urlparse

import whois

from laitoxx.shared.console import Color


def _normalize_domain(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"//{raw}")
    domain = parsed.netloc or parsed.path
    return domain.split("/")[0].strip().lower()


def _field_value(domain_info, name: str):
    if isinstance(domain_info, dict):
        return domain_info.get(name)
    return getattr(domain_info, name, None)


def _whois_error_types() -> tuple[type[BaseException], ...]:
    parser = getattr(whois, "parser", None)
    error_type = getattr(parser, "PywhoisError", None)
    return (error_type,) if isinstance(error_type, type) else ()


def get_website_info():
    """Retrieve and display WHOIS information for a domain."""
    raw_domain = input(
        f"{Color.DARK_GRAY}[{Color.DARK_RED}?{Color.DARK_GRAY}]"
        f"{Color.DARK_RED} Enter the website domain: {Color.RESET}"
    )
    domain = _normalize_domain(raw_domain)

    if not domain:
        print(
            f"{Color.DARK_GRAY}[{Color.DARK_RED}?{Color.DARK_GRAY}]{Color.RED} No domain entered."
        )
        return

    print(
        f"\n{Color.DARK_GRAY}[{Color.DARK_RED}?{Color.DARK_GRAY}]"
        f"{Color.LIGHT_BLUE} Retrieving WHOIS information for {domain}..."
    )

    try:
        domain_info = whois.whois(domain)
        domain_name = _field_value(domain_info, "domain_name")

        if not domain_name:
            print(
                f"{Color.DARK_GRAY}[{Color.DARK_RED}?{Color.DARK_GRAY}]{Color.RED} "
                "Could not retrieve WHOIS information. The domain may be incorrect or not registered."
            )
            return

        info_map = {
            "Domain": domain_name,
            "Registrar": _field_value(domain_info, "registrar"),
            "Creation Date": _field_value(domain_info, "creation_date"),
            "Expiration Date": _field_value(domain_info, "expiration_date"),
            "Last Updated": _field_value(domain_info, "updated_date"),
            "Name Servers": _field_value(domain_info, "name_servers"),
            "Status": _field_value(domain_info, "status"),
            "Registrant Name": _field_value(domain_info, "name"),
            "Organization": _field_value(domain_info, "org"),
            "Address": _field_value(domain_info, "address"),
            "City": _field_value(domain_info, "city"),
            "State": _field_value(domain_info, "state"),
            "Postal Code": _field_value(domain_info, "zipcode"),
            "Country": _field_value(domain_info, "country"),
        }

        print(f"\n{Color.DARK_RED}--- WHOIS Information for {domain} ---")
        for label, value in info_map.items():
            if not value:
                continue
            if isinstance(value, list):
                value_str = ", ".join(map(str, value))
            else:
                value_str = str(value).replace("\n", ", ")
            print(f"{Color.LIGHT_RED}{label:<20}: {Color.WHITE}{value_str}")
        print(f"{Color.DARK_RED}" + "-" * 45)

    except _whois_error_types() as e:
        print(f"{Color.DARK_GRAY}[{Color.DARK_RED}?{Color.DARK_GRAY}]{Color.RED} Error: {e}")
    except Exception as e:
        print(
            f"{Color.DARK_GRAY}[{Color.DARK_RED}?{Color.DARK_GRAY}]{Color.RED} "
            f"WHOIS lookup failed: {e}"
        )
