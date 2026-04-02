import time
import re
import os
import pyttsx3
import speech_recognition as sr

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service


class CarpoolBot:

    def __init__(self):
        self.driver = None
        self.engine = pyttsx3.init()
        self.recognizer = sr.Recognizer()
        
        # Tune recognizer for better listening
        self.recognizer.pause_threshold = 1.0  # 1 second pause to detect end of speech
        self.recognizer.energy_threshold = 4000  # Adjust for ambient noise
        self.recognizer.dynamic_energy_threshold = True

        # Known locations database
        self.locations = [
            "Howrah", "Kolkata", "Salt Lake", "New Town", "Park Street",
            "Dumdum", "Garia", "Sealdah", "Newtown", "Bangalore", "Airport"
        ]

        self.pickup = None
        self.drop = None
        self.timing = None  # Store timing preference

        self.setup_browser()

    # ------------------ SETUP ------------------

    def setup_browser(self):
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service)

        base = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(base, "travel-test-site.html")

        url = f"file:///{path.replace(os.sep, '/')}"
        self.driver.get(url)

        time.sleep(2)

    # ------------------ VOICE ------------------

    def speak(self, text):
        print("Bot:", text)
        self.engine.say(text)
        self.engine.runAndWait()

    def listen(self):
        try:
            with sr.Microphone() as source:
                print("🎤 Listening...")
                # Adjust for ambient noise and listen with timeout
                self.recognizer.adjust_for_ambient_noise(source, duration=1.0)
                audio = self.recognizer.listen(source, timeout=15, phrase_time_limit=20)

            try:
                text = self.recognizer.recognize_google(audio)
                print("User:", text)
                return text.lower()
            except sr.UnknownValueError:
                print("⚠️  Could not understand audio - Please speak clearly")
                self.speak("Sorry, I couldn't hear that clearly. Please repeat.")
                return ""
            except sr.RequestError as e:
                print(f"API error: {e}")
                self.speak("Network error. Please try again.")
                return ""
        except sr.RequestError as e:
            print(f"Microphone error: {e}")
            self.speak("Microphone error. Check your audio device.")
            return ""
        except Exception as e:
            print(f"Error: {e}")
            return ""

    # ------------------ SELENIUM ------------------

    def set_input(self, id, value):
        try:
            el = self.driver.find_element(By.ID, id)
            el.clear()
            el.send_keys(value)
        except:
            pass

    def click(self, id):
        try:
            # Wait for element to be present and clickable
            wait = WebDriverWait(self.driver, 10)
            element = wait.until(EC.element_to_be_clickable((By.ID, id)))
            element.click()
            print(f"✓ Clicked button: {id}")
            time.sleep(0.5)
        except Exception as e:
            print(f"✗ Failed to click {id}: {e}")
            # Try alternative click methods
            try:
                element = self.driver.find_element(By.ID, id)
                self.driver.execute_script("arguments[0].click();", element)
                print(f"✓ Clicked {id} using JS")
            except Exception as e2:
                print(f"✗ JS click also failed: {e2}")

    # ------------------ LOGIC ------------------

    def extract_locations(self, text):
        """Extract and validate location names from user input"""
        found_locations = []
        text_lower = text.lower()
        
        for location in self.locations:
            if location.lower() in text_lower:
                found_locations.append(location)
        
        return found_locations

    def handle_command(self, text):
        # Confirm what was heard
        self.speak(f"You said: {text}")
        time.sleep(0.5)

        # EXIT
        if "exit" in text:
            self.speak("Goodbye")
            self.driver.quit()
            exit()

        # BOOK - Extract both locations at once and ask for timing
        if "book" in text or "ride" in text:
            found_locations = self.extract_locations(text)
            
            if len(found_locations) >= 2:
                # Both locations found - ask for timing immediately
                self.pickup = found_locations[0]
                self.drop = found_locations[1]
                self.speak(f"Booking ride from {self.pickup} to {self.drop}. When do you want the ride?")
                self.speak("Say: now, today, tomorrow, morning, afternoon, evening, or specific time like 3 PM")
                return
            elif len(found_locations) == 1:
                # Only one location found
                self.pickup = found_locations[0]
                self.speak(f"Pickup location is {self.pickup}. Where would you like to go?")
                return
            else:
                # No locations found - provide valid options
                locations_list = ", ".join(self.locations[:8])  # List first 8 locations
                self.speak(f"Available locations are: {locations_list}. Please say: Book ride from Howrah to New Town")
                return

        # TIMING - Handle timing preferences
        if any(word in text for word in ["now", "today", "tomorrow", "morning", "afternoon", "evening", "night", "am", "pm"]):
            if not self.pickup or not self.drop:
                locations_list = ", ".join(self.locations[:8])
                self.speak(f"Please provide both pickup and dropoff locations first. Valid options: {locations_list}")
                return
            
            # Extract timing
            if "now" in text:
                self.timing = "Now"
            elif "morning" in text:
                self.timing = "Morning (8-11 AM)"
            elif "afternoon" in text:
                self.timing = "Afternoon (12-3 PM)"
            elif "evening" in text:
                self.timing = "Evening (4-7 PM)"
            elif "night" in text:
                self.timing = "Night (8 PM onwards)"
            elif "tomorrow" in text:
                self.timing = "Tomorrow"
            elif "today" in text:
                self.timing = "Today"
            elif re.search(r'\d{1,2}\s*(am|pm|AM|PM|o.?clock)', text):
                # Extract specific time like "3 PM", "10 AM"
                match = re.search(r'(\d{1,2})\s*(am|pm|AM|PM|o.?clock)', text)
                if match:
                    self.timing = f"{match.group(1)} {match.group(2)}"
            else:
                self.timing = "As soon as possible"
            
            self.speak(f"Ride scheduled for: {self.timing}")
            time.sleep(1)
            self.book_ride()
            return

        # FROM - Extract pickup location
        if "from" in text:
            found_locations = self.extract_locations(text)
            if found_locations:
                self.pickup = found_locations[0]
                self.speak(f"Pickup set to {self.pickup}. Where do you want to go?")
            else:
                locations_list = ", ".join(self.locations[:8])
                self.speak(f"Pickup location not found. Valid options: {locations_list}")
            return

        # TO - Extract drop location
        if "to" in text:
            found_locations = self.extract_locations(text)
            if found_locations:
                self.drop = found_locations[0]
                if self.pickup and self.drop:
                    self.speak(f"Ride from {self.pickup} to {self.drop}. When do you want the ride?")
                    self.speak("Say: now, today, tomorrow, morning, afternoon, evening, or specific time like 3 PM")
                    return
                elif self.pickup:
                    self.speak(f"Destination set to {self.drop}. When do you want to go?")
                else:
                    pickup_list = ", ".join(self.locations[:8])
                    self.speak(f"Please tell me the pickup location first. Valid options: {pickup_list}")
            else:
                locations_list = ", ".join(self.locations[:8])
                self.speak(f"Destination not recognized. Valid options: {locations_list}")
            return

        locations_list = ", ".join(self.locations[:8])
        self.speak(f"I didn't understand. Try: Book ride from Howrah to New Town. Valid locations: {locations_list}")

    # ------------------ BOOKING ------------------

    def book_ride(self):

        if not self.pickup or not self.drop:
            self.speak("Incomplete details")
            return

        print(f"\n📍 Booking: {self.pickup} → {self.drop}")
        if self.timing:
            print(f"⏰ Timing: {self.timing}\n")
        
        self.set_input("from", self.pickup)
        time.sleep(0.5)
        self.set_input("to", self.drop)
        time.sleep(0.5)

        print("Clicking search button...")
        self.click("searchBtn")
        time.sleep(2)

        print("Clicking book button to proceed to payment...")
        self.speak(f"Ride booked from {self.pickup} to {self.drop} at {self.timing or 'requested time'}")
        time.sleep(1)
        
        self.click("bookBtn")
        time.sleep(3)

        self.speak("Booked ride. Please select the correct payment method to proceed.")
        time.sleep(2)
        self.speak("You can enter your card details, choose the payment amount, and confirm your booking.")

        # Reset for next booking
        self.pickup = None
        self.drop = None
        self.timing = None

    # ------------------ MAIN ------------------

    def run(self):
        self.speak("Carpool assistant ready")

        while True:
            text = self.listen()
            if text:
                self.handle_command(text)


if __name__ == "__main__":
    bot = CarpoolBot()
    bot.run()