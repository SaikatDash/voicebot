# Standard library imports
import time
import re
import os
import csv
import datetime
import webbrowser
import requests
import json
import sys
import logging
import math
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote_plus

# Third-party package imports
from dotenv import load_dotenv
import pyttsx3
import speech_recognition as sr
from fuzzywuzzy import fuzz

# Selenium imports for browser automation
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException, 
    WebDriverException
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('voice_automation.log'),
        logging.StreamHandler()
    ]
)

class VoiceAutomationAssistant:
    """Main class for voice-controlled web automation assistant."""
    
    def __init__(self):
        """Initialize the voice automation assistant."""
        self.driver = None
        self.engine = None
        self.recognizer = None
        self.ride_data: List[Dict[str, object]] = []
        self.area_centers = {
            "salt lake": (22.58, 88.42),
            "new town": (22.61, 88.48),
            "howrah": (22.59, 88.31),
            "park street": (22.553, 88.352),
            "dumdum": (22.62, 88.42),
            "garia": (22.46, 88.38),
            "sealdah": (22.57, 88.37),
            "kolkata": (22.57, 88.36)
        }
        
        # Setup travel site URL BEFORE components initialization
        travel_test_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "travel-test-site.html")
        )
        travel_test_url = f"file:///{travel_test_path.replace(os.sep, '/')}"
        
        # Predefined websites for quick access
        self.quick_sites = {
            "travel-test-site": travel_test_url,
            "travel test site": travel_test_url,
            "booking": travel_test_url,
            "testtravel": travel_test_url,
            "test": travel_test_url
        }
        self.default_site_url = travel_test_url
        
        # NOW initialize components (which will load the travel site)
        self.setup_components()
        
        # Command patterns for better matching
        self.command_patterns = {
            'open': [
                r'open\s+(.+)',
                r'go\s+to\s+(.+)',
                r'navigate\s+to\s+(.+)',
                r'visit\s+(.+)'
            ],
            'search': [
                r'search\s+for\s+(.+)',
                r'google\s+(.+)',
                r'look\s+up\s+(.+)',
                r'find\s+(.+)'
            ],
            'search_amazon': [
                r'search\s+amazon\s+(.+)',
                r'amazon\s+(.+)',
                r'buy\s+(.+)'
            ],
            'scroll_down': [
                r'scroll\s+down(?:\s+(\d+))?',
                r'page\s+down(?:\s+(\d+))?'
            ],
            'scroll_up': [
                r'scroll\s+up(?:\s+(\d+))?',
                r'page\s+up(?:\s+(\d+))?'
            ],
            'click': [
                r'click\s+on\s+(.+)',
                r'click\s+(.+)',
                r'press\s+(.+)'
            ],
            'search_hotel_site': [
                r'search\s+hotels?\s+in\s+(.+)',
                r'find\s+hotels?\s+in\s+(.+)',
                r'book\s+hotels?\s+in\s+(.+)'
            ],
            'search_flight_route': [
                r'(?:search|find|book)\s+flights?\s+from\s+(.+?)\s+to\s+(.+?)(?:\s+on\s+(.+))?$',
                r'flights?\s+from\s+(.+?)\s+to\s+(.+?)(?:\s+on\s+(.+))?$'
            ],
            'search_train_route': [
                r'(?:search|find|book)\s+trains?\s+from\s+(.+?)\s+to\s+(.+?)(?:\s+on\s+(.+))?$',
                r'trains?\s+from\s+(.+?)\s+to\s+(.+?)(?:\s+on\s+(.+))?$'
            ],
            'search_bus_route': [
                r'(?:search|find|book)\s+buses?\s+from\s+(.+?)\s+to\s+(.+?)(?:\s+on\s+(.+))?$',
                r'buses?\s+from\s+(.+?)\s+to\s+(.+?)(?:\s+on\s+(.+))?$'
            ],
            'rides_between_time': [
                r'(?:show|find|get)\s+rides?\s+between\s+(.+?)\s+and\s+(.+?)(?:\s+in\s+(.+))?$',
                r'rides?\s+between\s+(.+?)\s+and\s+(.+?)(?:\s+in\s+(.+))?$'
            ],
            'top_driver_area': [
                r'(?:which|who\s+is\s+the)?\s*(?:highest|best|top)\s+rated\s+driver(?:\s+in|\s+near|\s+for)?\s+(.+)$',
                r'driver\s+with\s+highest\s+rating(?:\s+in|\s+near|\s+for)?\s+(.+)$'
            ],
            'auto_book_ride': [
                r'(?:auto(?:matically)?\s+)?book\s+ride(?:\s+in\s+(.+))?(?:\s+and\s+go\s+to\s+payment(?:\s+page)?)?$',
                r'book\s+ride\s+and\s+go\s+to\s+payment(?:\s+page)?(?:\s+in\s+(.+))?$'
            ],
            'auto_book_ride_route': [
                r'(?:auto(?:matically)?\s+)?book\s+ride\s+from\s+(.+?)\s+to\s+(.+?)(?:\s+in\s+(.+?))?(?:\s+and\s+go\s+to\s+payment(?:\s+page)?)?$',
                r'book\s+ride\s+from\s+(.+?)\s+to\s+(.+?)(?:\s+and\s+go\s+to\s+payment(?:\s+page)?)?$'
            ]
        }
        self.load_ride_data()

    def is_travel_related_command(self, command: str) -> bool:
        """Return True if command is related to travel test site actions."""
        travel_keywords = [
            "travel", "trip", "ride", "book", "booking", "hotel", "driver", "rating",
            "from", "to", "flight", "train", "bus", "pickup", "drop", "payment", "location"
        ]
        return any(keyword in command for keyword in travel_keywords)

    def ensure_travel_test_site_open(self):
        """Open local travel test site if not already on it."""
        try:
            current_url = (self.driver.current_url or "").lower()
            if "travel-test-site.html" not in current_url:
                self.driver.get(self.default_site_url)
                time.sleep(1.5)
        except Exception:
            self.driver.get(self.default_site_url)
            time.sleep(1.5)

    def set_input_value_by_id(self, field_id: str, value: str) -> bool:
        """Set value in an input by id using Selenium and fallback JS."""
        try:
            element = self.driver.find_element(By.ID, field_id)
            element.clear()
            element.send_keys(value)
            return True
        except Exception:
            try:
                script = (
                    "const el = document.getElementById(arguments[0]);"
                    "if (!el) return false;"
                    "el.value = arguments[1];"
                    "el.dispatchEvent(new Event('input', { bubbles: true }));"
                    "el.dispatchEvent(new Event('change', { bubbles: true }));"
                    "return true;"
                )
                return bool(self.driver.execute_script(script, field_id, value))
            except Exception:
                return False

    def set_select_value_by_id(self, field_id: str, value: str) -> bool:
        """Set value in a select by id using JS."""
        try:
            script = (
                "const el = document.getElementById(arguments[0]);"
                "if (!el) return false;"
                "el.value = arguments[1];"
                "el.dispatchEvent(new Event('change', { bubbles: true }));"
                "return true;"
            )
            return bool(self.driver.execute_script(script, field_id, value))
        except Exception:
            return False

    def click_by_id(self, element_id: str) -> bool:
        """Click button by id."""
        try:
            element = self.driver.find_element(By.ID, element_id)
            element.click()
            return True
        except Exception:
            return False

    def get_available_locations(self) -> List[str]:
        """Fetch available locations from travel site."""
        try:
            locations = self.driver.execute_script("return window.getAvailableLocations ? window.getAvailableLocations() : [];")
            return locations if locations else []
        except Exception:
            return []

    def validate_location(self, location: str) -> Optional[str]:
        """Check if location exists in available list; return matched name or None."""
        if not location:
            return None
        try:
            matched = self.driver.execute_script(
                "return window.getMatchingLocation ? window.getMatchingLocation(arguments[0]) : null;",
                location
            )
            return matched
        except Exception:
            return None

    def announce_available_locations(self, limit: int = 10):
        """Read out available locations to user."""
        try:
            locations = self.get_available_locations()
            if not locations:
                self.speak("No locations found. Please try again.")
                return
            
            displayed = locations[:limit]
            loc_text = ", ".join(displayed)
            self.speak(f"Available cities are: {loc_text}")
        except Exception as e:
            logging.error(f"Error announcing locations: {e}")
            self.speak("Could not load available locations.")

    def parse_driver_rating_command(self, command: str) -> Optional[Dict]:
        """Parse voice commands for driver rating filters.
        Handles: 'show drivers above 4.5', 'drivers below 3.5', 'rating greater than 4.0', etc.
        Returns: {min_rating: float, max_rating: float, area: str} or None
        """
        command_lower = command.lower()
        
        # Extract numeric ratings from command
        rating_match = re.search(r'(\d+\.?\d*)', command_lower)
        if not rating_match:
            return None
        
        rating_value = float(rating_match.group(1))
        
        # Determine if it's a minimum or maximum rating filter
        above_keywords = ["above", "greater than", "higher than", "at least", "minimum"]
        below_keywords = ["below", "less than", "lower than", "maximum", "under"]
        
        min_rating = None
        max_rating = None
        
        if any(kw in command_lower for kw in above_keywords):
            min_rating = rating_value
        elif any(kw in command_lower for kw in below_keywords):
            max_rating = rating_value
        else:
            # If no operator specified, treat as minimum rating
            min_rating = rating_value
        
        # Extract location if mentioned
        area = None
        area_match = re.search(r'(?:in|for|at|near)\s+([a-zA-Z\s]+?)(?:\s+(?:city|area)|$)', command_lower)
        if area_match:
            area_candidate = area_match.group(1).strip()
            matched_area = self.validate_location(area_candidate)
            if matched_area:
                area = matched_area
        
        return {
            "min_rating": min_rating,
            "max_rating": max_rating,
            "area": area
        }

    def search_drivers_by_rating(self, min_rating: Optional[float] = None, max_rating: Optional[float] = None, area: Optional[str] = None) -> bool:
        """Call the HTML page's driver search function directly."""
        try:
            self.ensure_travel_test_site_open()
            
            # Prepare parameters for JavaScript call
            area_param = area if area else "all"
            
            # Call the window.searchDriversByRating function on the page
            self.driver.execute_script(
                "return window.searchDriversByRating(arguments[0], arguments[1], arguments[2]);",
                min_rating,
                max_rating,
                area_param
            )
            
            # Provide voice feedback
            if min_rating and max_rating:
                self.speak(f"Showing drivers with rating between {min_rating} and {max_rating}{' in ' + area if area else ''}.")
            elif min_rating:
                self.speak(f"Showing drivers with rating {min_rating} and above{' in ' + area if area else ''}.")
            elif max_rating:
                self.speak(f"Showing drivers with rating {max_rating} and below{' in ' + area if area else ''}.")
            else:
                self.speak(f"Showing all drivers{' in ' + area if area else ''}.")
            
            return True
        except Exception as e:
            logging.error(f"Driver search error: {e}")
            self.speak("Could not search drivers. Please check the location or rating.")
            return False

    def run_travel_site_action(self, command: str) -> bool:
        """Execute natural-language booking with location validation and driver rating display."""
        self.ensure_travel_test_site_open()

        # Trip route action on local page
        route_match = re.search(
            r'(?:book|search|find)?\s*(?:trip|ride|travel|flight|train|bus)?\s*from\s+(.+?)\s+to\s+(.+?)(?:\s+on|at|around)?\s*(.+)?$',
            command, re.IGNORECASE
        )
        if route_match:
            origin = route_match.group(1).strip()
            destination = route_match.group(2).strip()
            time_or_date = route_match.group(3).strip() if route_match.group(3) else ""

            # Validate locations
            matched_origin = self.validate_location(origin)
            matched_destination = self.validate_location(destination)

            if not matched_origin:
                self.speak(f"{origin} is not available.")
                self.announce_available_locations()
                return False

            if not matched_destination:
                self.speak(f"{destination} is not available.")
                self.announce_available_locations()
                return False

            origin = matched_origin
            destination = matched_destination

            mode = "flight"
            if "train" in command.lower():
                mode = "train"
            elif "bus" in command.lower():
                mode = "bus"

            self.set_input_value_by_id("from", origin)
            self.set_input_value_by_id("to", destination)
            if time_or_date and re.match(r'^\d{4}-\d{2}-\d{2}$', time_or_date):
                self.set_input_value_by_id("date", time_or_date)
            self.set_select_value_by_id("mode", mode)

            if self.click_by_id("searchBtn"):
                time.sleep(0.8)
                if "book" in command.lower():
                    self.click_by_id("bookBtn")
                    self.speak(f"Booked {mode} from {origin} to {destination}. Displaying rides sorted by driver rating.")
                else:
                    self.speak(f"Found {mode} options from {origin} to {destination}. Showing best-rated drivers first.")
                return True

        # Hotel action on local page
        hotel_match = re.search(r'(?:search|find|book)\s+hotels?\s+in\s+(.+)', command, re.IGNORECASE)
        if hotel_match:
            city = hotel_match.group(1).strip()
            matched_city = self.validate_location(city)
            if not matched_city:
                self.speak(f"{city} is not available.")
                self.announce_available_locations()
                return False
            self.set_input_value_by_id("to", matched_city)
            if self.click_by_id("hotelBtn"):
                self.speak(f"Searching hotels in {matched_city}.")
                return True

        # Generic booking with from/to
        if "book" in command.lower() and ("from" in command.lower() or "ride" in command.lower()):
            pickup = re.search(r'from\s+(.+?)(?:\s+to|\s+at)', command, re.IGNORECASE)
            drop = re.search(r'(?:to|drop)\s+(.+?)(?:\s+and|\s+at|\s+around|$)', command, re.IGNORECASE)
            
            if pickup and drop:
                pickup_loc = pickup.group(1).strip()
                drop_loc = drop.group(1).strip()
                
                matched_pickup = self.validate_location(pickup_loc)
                matched_drop = self.validate_location(drop_loc)
                
                if not matched_pickup:
                    self.speak(f"{pickup_loc} not available.")
                    self.announce_available_locations()
                    return False
                if not matched_drop:
                    self.speak(f"{drop_loc} not available.")
                    self.announce_available_locations()
                    return False
                
                self.set_input_value_by_id("from", matched_pickup)
                self.set_input_value_by_id("to", matched_drop)
                self.click_by_id("searchBtn")
                time.sleep(0.8)
                self.click_by_id("bookBtn")
                self.speak(f"Booking ride from {matched_pickup} to {matched_drop}. Showing drivers sorted by rating.")
                return True

        # Driver rating search - parse natural language and search
        if ("driver" in command.lower() and "rating" in command.lower()) or "show drivers" in command.lower():
            rating_params = self.parse_driver_rating_command(command)
            if rating_params:
                return self.search_drivers_by_rating(
                    min_rating=rating_params.get("min_rating"),
                    max_rating=rating_params.get("max_rating"),
                    area=rating_params.get("area")
                )
            else:
                # No rating found in command
                self.speak("Please specify a rating like 'show drivers above 4.5' or 'drivers below 3.5'.")
                return False

        return False

    def fill_location_field(self, selectors: List[str], value: str) -> bool:
        """Fill first matching input field with given location value."""
        for selector in selectors:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                element.clear()
                element.send_keys(value)
                return True
            except Exception:
                continue
        return False

    def fill_booking_locations(self, pickup: str, drop: str) -> bool:
        """Try to populate pickup/drop fields on booking page with spoken locations."""
        pickup_selectors = [
            "#from",
            "#pickup",
            "#pickupLocation",
            "input[name='from']",
            "input[name='pickup']",
            "input[placeholder*='Pickup']",
            "input[placeholder*='From']"
        ]
        drop_selectors = [
            "#to",
            "#drop",
            "#dropLocation",
            "input[name='to']",
            "input[name='drop']",
            "input[placeholder*='Drop']",
            "input[placeholder*='To']"
        ]

        pickup_ok = self.fill_location_field(pickup_selectors, pickup)
        drop_ok = self.fill_location_field(drop_selectors, drop)
        return pickup_ok and drop_ok

    def load_ride_data(self):
        """Load driver and rating data from CSV files for voice ride queries."""
        try:
            data_dir = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "prev", "data")
            )
            drivers_path = os.path.join(data_dir, "drivers.csv")
            ratings_path = os.path.join(data_dir, "rating.csv")

            ratings: Dict[str, float] = {}
            with open(ratings_path, "r", encoding="utf-8") as rating_file:
                for row in csv.DictReader(rating_file):
                    driver_id = (row.get("driverId") or "").strip()
                    try:
                        ratings[driver_id] = float((row.get("rating") or "0").strip())
                    except ValueError:
                        ratings[driver_id] = 0.0

            records: List[Dict[str, object]] = []
            with open(drivers_path, "r", encoding="utf-8") as drivers_file:
                for row in csv.DictReader(drivers_file):
                    driver_id = (row.get("driverId") or "").strip()
                    try:
                        pickup_lat = float((row.get("pickupLat") or "0").strip())
                        pickup_lng = float((row.get("pickupLng") or "0").strip())
                    except ValueError:
                        continue

                    records.append({
                        "driverId": driver_id,
                        "driverName": (row.get("driverName") or "Unknown").strip(),
                        "availability": (row.get("availability") or "Unavailable").strip().lower(),
                        "workStartTime": (row.get("workStartTime") or "00:00").strip(),
                        "workEndTime": (row.get("workEndTime") or "00:00").strip(),
                        "pickupLat": pickup_lat,
                        "pickupLng": pickup_lng,
                        "rating": ratings.get(driver_id, 0.0)
                    })

            self.ride_data = records
            logging.info(f"Loaded {len(self.ride_data)} driver records for ride commands")
        except Exception as e:
            self.ride_data = []
            logging.error(f"Failed to load ride data: {e}")

    def parse_time_to_minutes(self, time_text: str) -> Optional[int]:
        """Convert spoken time text to minutes from midnight, handling natural expressions."""
        clean = " ".join(time_text.strip().lower().split())
        
        # Handle natural time expressions
        natural_times = {
            "morning": 6,
            "noon": 12,
            "afternoon": 14,
            "evening": 18,
            "night": 21,
            "midnight": 0,
            "dawn": 5,
            "dusk": 18
        }
        
        for natural, hour in natural_times.items():
            if natural in clean:
                return hour * 60
        
        # Try standard formats
        formats = ["%H:%M", "%I:%M %p", "%I %p", "%H"]
        for fmt in formats:
            try:
                parsed = datetime.datetime.strptime(clean, fmt)
                return parsed.hour * 60 + parsed.minute
            except ValueError:
                continue

        # Convert forms like 6am / 9pm / 6 / 9
        compact = clean.replace(" ", "").replace("o'clock", "")
        
        # Try 6am/6pm format
        try:
            if compact.endswith("am") or compact.endswith("pm"):
                parsed = datetime.datetime.strptime(compact, "%I%p")
                return parsed.hour * 60 + parsed.minute
        except ValueError:
            pass

        # Try plain number like "6" or "9"
        try:
            if compact.isdigit() and 0 <= int(compact) <= 24:
                return int(compact) * 60
        except ValueError:
            pass

        return None

    def is_time_overlap(self, start_a: int, end_a: int, start_b: int, end_b: int) -> bool:
        """Check overlap between two time windows, supporting overnight shifts."""
        def expand_window(start_min: int, end_min: int) -> List[Tuple[int, int]]:
            if end_min >= start_min:
                return [(start_min, end_min)]
            return [(start_min, 24 * 60), (0, end_min)]

        window_a = expand_window(start_a, end_a)
        window_b = expand_window(start_b, end_b)

        for a_start, a_end in window_a:
            for b_start, b_end in window_b:
                if max(a_start, b_start) < min(a_end, b_end):
                    return True
        return False

    def get_nearest_area_center(self, area_text: Optional[str]) -> Tuple[float, float, str]:
        """Resolve area text to nearest known area center."""
        if not area_text:
            lat, lng = self.area_centers["kolkata"]
            return lat, lng, "kolkata"

        area_text = area_text.strip().lower()
        for area_name, coords in self.area_centers.items():
            if area_name in area_text or area_text in area_name:
                return coords[0], coords[1], area_name

        lat, lng = self.area_centers["kolkata"]
        return lat, lng, "kolkata"

    def distance_score(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Simple geographic distance score for ranking nearby drivers."""
        return math.sqrt((lat1 - lat2) ** 2 + (lng1 - lng2) ** 2)

    def to_float(self, value: object, default: float = 0.0) -> float:
        """Convert unknown values to float safely."""
        try:
            return float(str(value))
        except (TypeError, ValueError):
            return default

    def get_rides_between_timings(self, from_time: str, to_time: str, area_text: Optional[str] = None) -> List[Dict[str, object]]:
        """Return available rides matching time overlap and optional area."""
        if not self.ride_data:
            return []

        from_min = self.parse_time_to_minutes(from_time)
        to_min = self.parse_time_to_minutes(to_time)
        if from_min is None or to_min is None:
            return []

        area_lat, area_lng, _ = self.get_nearest_area_center(area_text)
        matches: List[Dict[str, object]] = []

        for row in self.ride_data:
            if row["availability"] != "available":
                continue

            shift_start = self.parse_time_to_minutes(str(row["workStartTime"]))
            shift_end = self.parse_time_to_minutes(str(row["workEndTime"]))
            if shift_start is None or shift_end is None:
                continue

            if not self.is_time_overlap(shift_start, shift_end, from_min, to_min):
                continue

            dist = self.distance_score(
                self.to_float(row.get("pickupLat")),
                self.to_float(row.get("pickupLng")),
                area_lat,
                area_lng
            )

            row_with_dist = dict(row)
            row_with_dist["distance"] = dist
            matches.append(row_with_dist)

        matches.sort(
            key=lambda item: (
                -self.to_float(item.get("rating")),
                self.to_float(item.get("distance"))
            )
        )
        return matches

    def get_highest_rated_driver_by_area(self, area_text: Optional[str]) -> Optional[Dict[str, object]]:
        """Find the highest rated available driver near a requested area."""
        candidates = self.get_rides_between_timings("00:00", "23:59", area_text)
        if not candidates:
            return None
        return candidates[0]

    def show_rides_between_timings(self, from_time: str, to_time: str, area_text: Optional[str] = None):
        """Speak and print ride options for a spoken time range."""
        rides = self.get_rides_between_timings(from_time, to_time, area_text)
        if not rides:
            self.speak("I could not find available rides for that timing and area.")
            return

        top_rides = rides[:5]
        summary = ", ".join(
            f"{ride['driverName']} rated {ride['rating']}"
            for ride in top_rides
        )
        self.speak(f"I found {len(rides)} rides. Top options are {summary}.")

    def announce_top_driver(self, area_text: Optional[str] = None) -> Optional[Dict[str, object]]:
        """Speak top-rated driver for a requested area."""
        driver = self.get_highest_rated_driver_by_area(area_text)
        if not driver:
            self.speak("I could not find an available top-rated driver in your area.")
            return None

        self.speak(
            f"Highest rated driver near your area is {driver['driverName']} with rating {driver['rating']}."
        )
        return driver

    def auto_book_ride_and_payment(
        self,
        area_text: Optional[str] = None,
        pickup_location: Optional[str] = None,
        drop_location: Optional[str] = None
    ):
        """Select a best driver from data and try to navigate booking flow to payment."""
        selected = self.announce_top_driver(area_text)
        if not selected:
            return

        if pickup_location and drop_location:
            if self.fill_booking_locations(pickup_location, drop_location):
                self.speak(f"Selected pickup {pickup_location} and drop {drop_location}.")
            else:
                self.speak("I could not detect location fields on this page to set pickup and drop.")

        self.speak(f"Booking ride with {selected['driverName']}.")

        # Attempt generic booking/payment clicks on current page.
        try:
            click_targets = [
                "Search Trip",
                "Search Ride",
                "Find Ride",
                "Book Ride",
                "Book",
                "Confirm",
                "Proceed",
                "Continue",
                "Payment",
                "Proceed to Payment",
                "Pay Now"
            ]

            for target in click_targets:
                self.click_element(target)
                time.sleep(0.8)

            self.speak("Booking flow attempted. Reaching payment page now.")
        except Exception as e:
            logging.error(f"Auto book/payment flow error: {e}")
            self.speak("I selected the best driver but could not complete payment navigation automatically.")

    def setup_components(self):
        """Initialize all required components."""
        try:
            # Initialize text-to-speech engine
            self.engine = pyttsx3.init()
            self.configure_tts()
            
            # Initialize speech recognizer
            self.recognizer = sr.Recognizer()
            
            # Initialize browser
            self.setup_browser()
            
            logging.info("All components initialized successfully")
            
        except Exception as e:
            logging.error(f"Error setting up components: {e}")
            self.speak("There was a problem initializing the assistant.")
            sys.exit(1)

    def configure_tts(self):
        """Configure text-to-speech settings."""
        try:
            voices = self.engine.getProperty('voices')
            if voices:
                # Try to set a female voice if available
                for voice in voices:
                    if 'female' in voice.name.lower() or 'zira' in voice.name.lower():
                        self.engine.setProperty('voice', voice.id)
                        break
            
            # Set speech rate and volume
            self.engine.setProperty('rate', 180)  # Speed of speech
            self.engine.setProperty('volume', 0.9)  # Volume level (0.0 to 1.0)
            
        except Exception as e:
            logging.warning(f"Could not configure TTS settings: {e}")

    def setup_browser(self):
        """Initialize and configure the Chrome browser."""
        try:
            service = Service(ChromeDriverManager().install())
            options = webdriver.ChromeOptions()
            
            # Chrome options for better performance and compatibility
            options.add_argument('--ignore-certificate-errors')
            options.add_argument('--ignore-ssl-errors')
            options.add_argument('--disable-extensions')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_experimental_option('excludeSwitches', ['enable-logging'])
            options.add_experimental_option('useAutomationExtension', False)
            
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.maximize_window()
            
            # Load the travel test site immediately
            try:
                self.driver.get(self.default_site_url)
                time.sleep(2)
                logging.info("Travel test site loaded successfully")
            except Exception as e:
                logging.warning(f"Could not load travel site: {e}")
            
            logging.info("Browser initialized successfully")
            
        except Exception as e:
            logging.error(f"Error setting up browser: {e}")
            raise

    def speak(self, text: str):
        """Speak the given text using pyttsx3."""
        try:
            print(f"Assistant: {text}")
            self.engine.say(text)
            self.engine.runAndWait()
        except Exception as e:
            logging.error(f"TTS error: {e}")
            print(f"Assistant: {text}")  # Fallback to text output

    def get_voice_command(self) -> str:
        """Capture and return voice input as lowercase text."""
        try:
            with sr.Microphone() as source:
                print("🎤 Listening...")
                self.recognizer.pause_threshold = 1
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                
                # Listen for audio input
                audio = self.recognizer.listen(source, timeout=10, phrase_time_limit=10)
                print("🔄 Recognizing...")
                
                # Recognize speech using Google API
                query = self.recognizer.recognize_google(audio, language="en-US")
                print(f"👤 User: {query}")
                return query.lower().strip()
                
        except sr.WaitTimeoutError:
            print("⏰ No speech detected within timeout.")
            return ""
        except sr.UnknownValueError:
            self.speak("Sorry, I didn't understand that. Please try again.")
            return ""
        except sr.RequestError as e:
            self.speak("There is a problem with speech recognition.")
            logging.error(f"Speech recognition error: {e}")
            return ""
        except Exception as e:
            self.speak("There is a problem.")
            logging.error(f"Voice command error: {e}")
            return ""

    def normalize_url(self, url: str) -> str:
        """Resolve to only allowed local test site URL."""
        url = url.strip()
        
        # Check if it's a quick site
        if url in self.quick_sites:
            return self.quick_sites[url]

        return self.default_site_url

    def open_website(self, website: str):
        """Open a website in the browser."""
        try:
            url = self.normalize_url(website)
            if website.strip().lower() not in self.quick_sites:
                self.speak("Only travel test site navigation is enabled. Opening travel test site.")
            self.speak(f"Opening {website}")
            self.driver.get(url)
            time.sleep(2)  # Wait for page to load
            
        except WebDriverException as e:
            self.speak(f"There was a problem opening {website}")
            logging.error(f"Error opening website {website}: {e}")

    def search_google(self, query: str):
        """Perform a Google search."""
        try:
            self.speak(f"Searching Google for {query}")
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            self.driver.get(search_url)
            time.sleep(2)
            
        except Exception as e:
            self.speak("There was a problem with the Google search")
            logging.error(f"Google search error: {e}")

    def search_amazon(self, query: str):
        """Perform an Amazon search."""
        try:
            self.speak(f"Searching Amazon for {query}")
            search_url = f"https://www.amazon.com/s?k={query.replace(' ', '+')}"
            self.driver.get(search_url)
            time.sleep(2)
            
        except Exception as e:
            self.speak("There was a problem with the Amazon search")
            logging.error(f"Amazon search error: {e}")

    def search_hotels(self, city: str):
        """Search hotels for a city using Booking.com."""
        try:
            city = city.strip()
            self.speak(f"Searching hotels in {city}")
            search_url = f"https://www.booking.com/searchresults.html?ss={quote_plus(city)}"
            self.driver.get(search_url)
            time.sleep(2)
        except Exception as e:
            self.speak("There was a problem searching hotels")
            logging.error(f"Hotel search error: {e}")

    def search_flights(self, origin: str, destination: str, travel_date: Optional[str] = None):
        """Search flights between origin and destination using Google Flights."""
        try:
            route_text = f"Flights from {origin} to {destination}"
            if travel_date:
                route_text = f"{route_text} on {travel_date}"

            self.speak(f"Searching {route_text}")
            search_url = f"https://www.google.com/travel/flights?q={quote_plus(route_text)}"
            self.driver.get(search_url)
            time.sleep(2)
        except Exception as e:
            self.speak("There was a problem searching flights")
            logging.error(f"Flight search error: {e}")

    def search_trains(self, origin: str, destination: str, travel_date: Optional[str] = None):
        """Search train options using Google query."""
        try:
            query = f"trains from {origin} to {destination}"
            if travel_date:
                query = f"{query} on {travel_date}"

            self.speak(f"Searching {query}")
            self.driver.get(f"https://www.google.com/search?q={quote_plus(query)}")
            time.sleep(2)
        except Exception as e:
            self.speak("There was a problem searching trains")
            logging.error(f"Train search error: {e}")

    def search_buses(self, origin: str, destination: str, travel_date: Optional[str] = None):
        """Search bus options using Google query."""
        try:
            query = f"buses from {origin} to {destination}"
            if travel_date:
                query = f"{query} on {travel_date}"

            self.speak(f"Searching {query}")
            self.driver.get(f"https://www.google.com/search?q={quote_plus(query)}")
            time.sleep(2)
        except Exception as e:
            self.speak("There was a problem searching buses")
            logging.error(f"Bus search error: {e}")

    def parse_route_command(self, command: str, patterns: List[str]) -> Optional[Tuple[str, str, Optional[str]]]:
        """Parse route-based voice commands like 'flights from A to B on date'."""
        for pattern in patterns:
            match = re.search(pattern, command, re.IGNORECASE)
            if match:
                origin = match.group(1).strip()
                destination = match.group(2).strip()
                travel_date = match.group(3).strip() if len(match.groups()) >= 3 and match.group(3) else None
                return origin, destination, travel_date
        return None

    def scroll_page(self, direction: str, pixels: int = 300):
        """Scroll the page in the specified direction."""
        try:
            if direction == "down":
                self.speak(f"Scrolling down by {pixels} pixels")
                self.driver.execute_script(f"window.scrollBy(0, {pixels});")
            elif direction == "up":
                self.speak(f"Scrolling up by {pixels} pixels")
                self.driver.execute_script(f"window.scrollBy(0, -{pixels});")
            elif direction == "bottom":
                self.speak("Scrolling to the bottom of the page")
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            elif direction == "top":
                self.speak("Scrolling to the top of the page")
                self.driver.execute_script("window.scrollTo(0, 0);")
                
        except Exception as e:
            self.speak("There was a problem scrolling")
            logging.error(f"Scroll error: {e}")

    def click_element(self, element_text: str):
        """Click on an element containing the specified text."""
        try:
            self.speak(f"Looking for element containing '{element_text}'")
            
            # Try different strategies to find the element
            strategies = [
                (By.PARTIAL_LINK_TEXT, element_text),
                (By.LINK_TEXT, element_text),
                (By.XPATH, f"//*[contains(text(), '{element_text}')]"),
                (By.XPATH, f"//button[contains(text(), '{element_text}')]"),
                (By.XPATH, f"//input[@value='{element_text}']"),
                (By.XPATH, f"//*[@title='{element_text}']")
            ]
            
            element = None
            for by, value in strategies:
                try:
                    element = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((by, value))
                    )
                    break
                except TimeoutException:
                    continue
            
            if element:
                element.click()
                self.speak(f"Clicked on {element_text}")
            else:
                self.speak(f"Could not find element containing '{element_text}'")
                
        except Exception as e:
            self.speak("There was a problem clicking the element")
            logging.error(f"Click error: {e}")

    def navigate_browser(self, action: str):
        """Navigate browser (back, forward, refresh)."""
        try:
            if action == "back":
                self.speak("Going back")
                self.driver.back()
            elif action == "forward":
                self.speak("Going forward")
                self.driver.forward()
            elif action == "refresh":
                self.speak("Refreshing the page")
                self.driver.refresh()
            time.sleep(1)
            
        except Exception as e:
            self.speak(f"There was a problem with browser navigation")
            logging.error(f"Navigation error: {e}")

    def get_current_time(self):
        """Get and speak the current time."""
        try:
            current_time = datetime.datetime.now().strftime("%I:%M %p")
            self.speak(f"The current time is {current_time}")
            
        except Exception as e:
            self.speak("There was a problem getting the time")
            logging.error(f"Time error: {e}")

    def get_weather(self, city: str):
        """Get weather information for a specified city."""
        try:
            self.speak(f"Getting weather information for {city}")
            url = f"https://wttr.in/{city}?format=%C+%t"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                weather = response.text.strip()
                self.speak(f"The weather in {city} is {weather}")
            else:
                self.speak("Could not fetch weather information")
                
        except requests.RequestException as e:
            self.speak("There was a problem fetching the weather")
            logging.error(f"Weather error: {e}")

    def match_command_pattern(self, command: str) -> Tuple[Optional[str], Optional[str]]:
        """Match command against predefined patterns."""
        for cmd_type, patterns in self.command_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, command, re.IGNORECASE)
                if match:
                    return cmd_type, match.group(1) if match.groups() else None
        return None, None

    def process_command(self, command: str):
        """Process voice commands using pattern matching."""
        if not command:
            return

        command = command.strip().lower()

        if self.is_travel_related_command(command):
            if self.run_travel_site_action(command):
                return
        
        # Exit commands
        exit_commands = ["exit", "close", "quit", "bye", "goodbye", "stop"]
        if any(word in command for word in exit_commands):
            self.speak("Closing the browser. Goodbye!")
            self.cleanup()
            return

        # Time commands
        if any(phrase in command for phrase in ["time", "what time", "current time"]):
            self.get_current_time()
            return

        # Weather commands
        weather_match = re.search(r"weather\s+(?:in\s+)?(\w+)", command)
        if weather_match:
            city = weather_match.group(1)
            self.get_weather(city)
            return

        # Browser navigation commands
        if re.search(r'\b(go\s+back|back)\b', command):
            self.navigate_browser("back")
            return
        elif re.search(r'\b(go\s+forward|forward)\b', command):
            self.navigate_browser("forward")
            return
        elif re.search(r'\b(refresh|reload)\b', command):
            self.navigate_browser("refresh")
            return

        # Scroll commands
        if "scroll to bottom" in command or "bottom" in command:
            self.scroll_page("bottom")
            return
        elif "scroll to top" in command or "top" in command:
            self.scroll_page("top")
            return

        # Travel-focused commands
        flight_match = self.parse_route_command(command, self.command_patterns['search_flight_route'])
        if flight_match:
            origin, destination, travel_date = flight_match
            self.search_flights(origin, destination, travel_date)
            return

        train_match = self.parse_route_command(command, self.command_patterns['search_train_route'])
        if train_match:
            origin, destination, travel_date = train_match
            self.search_trains(origin, destination, travel_date)
            return

        bus_match = self.parse_route_command(command, self.command_patterns['search_bus_route'])
        if bus_match:
            origin, destination, travel_date = bus_match
            self.search_buses(origin, destination, travel_date)
            return

        for pattern in self.command_patterns['auto_book_ride_route']:
            match = re.search(pattern, command, re.IGNORECASE)
            if match:
                pickup = match.group(1).strip()
                drop = match.group(2).strip()
                area_text = match.group(3).strip() if len(match.groups()) >= 3 and match.group(3) else None
                self.auto_book_ride_and_payment(
                    area_text=area_text,
                    pickup_location=pickup,
                    drop_location=drop
                )
                return

        # Ride-focused commands from microphone
        for pattern in self.command_patterns['rides_between_time']:
            match = re.search(pattern, command, re.IGNORECASE)
            if match:
                from_time = match.group(1)
                to_time = match.group(2)
                area_text = match.group(3) if len(match.groups()) >= 3 else None
                self.show_rides_between_timings(from_time, to_time, area_text)
                return

        for pattern in self.command_patterns['top_driver_area']:
            match = re.search(pattern, command, re.IGNORECASE)
            if match:
                area_text = match.group(1)
                self.announce_top_driver(area_text)
                return

        for pattern in self.command_patterns['auto_book_ride']:
            match = re.search(pattern, command, re.IGNORECASE)
            if match:
                area_text = match.group(1) if match.groups() else None
                self.auto_book_ride_and_payment(area_text)
                return

        # Pattern-based command matching
        cmd_type, value = self.match_command_pattern(command)
        
        if cmd_type == "open" and value:
            self.open_website(value)
        elif cmd_type == "search" and value:
            self.search_google(value)
        elif cmd_type == "search_amazon" and value:
            self.search_amazon(value)
        elif cmd_type == "search_hotel_site" and value:
            self.search_hotels(value)
        elif cmd_type == "scroll_down":
            pixels = int(value) if value and value.isdigit() else 300
            self.scroll_page("down", pixels)
        elif cmd_type == "scroll_up":
            pixels = int(value) if value and value.isdigit() else 300
            self.scroll_page("up", pixels)
        elif cmd_type == "click" and value:
            self.click_element(value)
        else:
            # Fuzzy matching for close commands
            best_match = None
            best_score = 0
            
            for site in self.quick_sites.keys():
                if site in command:
                    self.open_website(site)
                    return
            
            # If no exact match, try fuzzy matching
            for cmd in ["open google", "search", "scroll down", "go back"]:
                score = fuzz.partial_ratio(cmd, command)
                if score > best_score and score > 70:
                    best_score = score
                    best_match = cmd
            
            if best_match:
                self.speak(f"Did you mean {best_match}? Please try again with clearer pronunciation.")
            else:
                self.speak("I didn't understand that command. Please try again.")

    def cleanup(self):
        """Clean up resources before exit."""
        try:
            if self.driver:
                self.driver.quit()
            if self.engine:
                self.engine.stop()
            logging.info("Cleanup completed successfully")
        except Exception as e:
            logging.error(f"Cleanup error: {e}")
        finally:
            sys.exit(0)

    def run(self):
        """Main loop for the voice automation assistant."""
        # Minimal welcome message - just speak briefly
        welcome_msg = "Travel assistant ready. Click the microphone icon to start."
        print(f"✅ {welcome_msg}")
        self.speak(welcome_msg)
        
        # Main command loop
        while True:
            try:
                command = self.get_voice_command()
                if command:
                    print(f"🔄 Processing: {command}")
                    # Send command to HTML page
                    try:
                        self.driver.execute_script(f"window.processVoiceCommand('{command}')")
                    except Exception as e:
                        logging.debug(f"HTML communication: {e}")
                    # Process the command
                    self.process_command(command)
                    
            except KeyboardInterrupt:
                self.speak("Stopping assistant...")
                break
            except Exception as e:
                logging.error(f"Main loop error: {e}")
        
        self.cleanup()


def main():
    """Main function to start the voice automation assistant."""
    try:
        assistant = VoiceAutomationAssistant()
        assistant.run()
    except Exception as e:
        logging.error(f"Failed to start assistant: {e}")
        print("Failed to start the assistant. Please check the logs for details.")


if __name__ == "__main__":
    main()