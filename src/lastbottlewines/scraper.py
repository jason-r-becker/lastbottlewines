"""Web scraping logic for lastbottlewines.com"""

import logging
from typing import Optional, Tuple
from bs4 import BeautifulSoup
import requests

logger = logging.getLogger(__name__)


def scrape_last_bottle() -> Optional[Tuple[str, float]]:
    """
    Scrapes lastbottlewines.com to find the current sale
    bottle and its price.

    Returns:
        Tuple of (wine_name, price) or None if scraping fails
    """
    url = "https://lastbottlewines.com/"

    try:
        # Set a user-agent to avoid being blocked
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        # Remove script and style elements to clean up text
        for script in soup(["script", "style"]):
            script.decompose()

        # Find the main content area
        main = soup.find("main")
        if not main:
            logger.error("Could not find main container")
            return None

        # Extract wine name - look for the h1 tag
        wine_name_elem = main.find("h1")
        if wine_name_elem:
            wine_name = wine_name_elem.get_text(strip=True)
        else:
            logger.error("Could not find wine name")
            return None

        # Extract price - find price sections and locate
        # the one with "LAST BOTTLE" label
        price_sections = main.find_all("div", class_="product__price")
        if not price_sections:
            logger.error("Could not find price sections")
            return None

        # Find the first price section that contains "LAST BOTTLE" text
        last_bottle_section = None
        for section in price_sections:
            if "LAST BOTTLE" in section.get_text():
                last_bottle_section = section
                break

        if not last_bottle_section:
            logger.error("Could not find 'LAST BOTTLE' price section")
            return None

        # Extract the price - it's in the first span within the section
        price_span = last_bottle_section.find("span")
        if price_span:
            price_text = price_span.get_text(strip=True)
            try:
                price = float(price_text.replace(",", ""))
            except ValueError:
                logger.error("Could not parse price: %s", price_text)
                return None
        else:
            logger.error("Could not find price span in LAST BOTTLE section")
            return None

        return (wine_name, price)

    except requests.exceptions.RequestException as e:
        logger.error("Error fetching the website: %s", e)
        return None
    except Exception as e:
        logger.error("Error parsing website: %s", e)
        return None
