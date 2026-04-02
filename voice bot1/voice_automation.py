import time
import re
import os
import pyttsx3
import speech_recognition as sr

from selenium import webdriver
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service


class CarpoolBot:

    def __init__(self):
        self.driver = None
        self.engine = pyttsx3.init()
        self.recognizer = sr.Recognizer()

        self.pickup = None
        self.drop = None

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
        with sr.Microphone() as source:
            print("🎤 Listening...")
            audio = self.recognizer.listen(source)

        try:
            text = self.recognizer.recognize_google(audio)
            print("User:", text)
            return text.lower()
        except:
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
            self.driver.find_element(By.ID, id).click()
        except:
            pass

    # ------------------ LOGIC ------------------

    def handle_command(self, text):

        # EXIT
        if "exit" in text:
            self.speak("Goodbye")
            self.driver.quit()
            exit()

        # BOOK START
        if "book" in text:
            self.speak("Please tell pickup location")
            return

        # FROM
        if "from" in text:
            self.pickup = text.replace("from", "").strip()
            self.speak(f"Pickup set to {self.pickup}. Now tell destination.")
            return

        # TO
        if "to" in text:
            self.drop = text.replace("to", "").strip()
            self.book_ride()
            return

        # DIRECT "howrah new town"
        words = text.split()
        if len(words) >= 2:
            mid = len(words) // 2
            self.pickup = " ".join(words[:mid])
            self.drop = " ".join(words[mid:])
            self.book_ride()
            return

        self.speak("Please say valid pickup and drop locations")

    # ------------------ BOOKING ------------------

    def book_ride(self):

        if not self.pickup or not self.drop:
            self.speak("Incomplete details")
            return

        self.set_input("from", self.pickup)
        self.set_input("to", self.drop)

        self.click("searchBtn")
        time.sleep(1)

        self.click("bookBtn")

        self.speak(f"Ride booked from {self.pickup} to {self.drop}")

        self.pickup = None
        self.drop = None

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