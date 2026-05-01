import time
import re
import os
from difflib import SequenceMatcher
from datetime import date, datetime, timedelta
import pyttsx3
import speech_recognition as sr

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

try:
    import nltk
except ImportError:
    nltk = None

AutoTokenizer = None
AutoModelForSeq2SeqLM = None

try:
    import sounddevice as sd
except ImportError:
    sd = None

class CarpoolBot:

    def __init__(self):
        self.driver = None
        self.engine = pyttsx3.init()
        self.recognizer = sr.Recognizer()
        self.voice_ids = self.detect_tts_voices()
        self.current_language = "en"
        self.hindi_tokenizer = None
        self.hindi_model = None
        self.language_names = {
            "en": "English",
            "hi": "Hindi",
            "bn": "Bengali",
        }
        self.intent_words = {
            "book": [
                "book", "booking", "ride", "right", "write", "raid", "cab", "car", "taxi",
                "बुक", "राइड", "राईड", "रायड", "रैड", "राइट", "राईट", "गाड़ी", "गाड़ी", "टैक्सी", "कैब", "जाना", "चलना",
                "mujhe", "muje", "jana", "jaana", "chalna", "chahiye", "kar do", "kardo",
                "raiḍ", "raid", "raide", "raita", "right", "gaadi", "gadi", "taxi", "cab",
                "বুক", "রাইড", "রাইডে", "রাইট", "গাড়ি", "গাড়ি", "ট্যাক্সি", "যাব", "যেতে", "চাই",
                "ami", "amake", "jabo", "jete", "chai", "lagbe", "koro", "kore dao",
            ],
            "from": ["from", "pickup", "source", "से", "shuru", "se", "থেকে", "পিকআপ", "theke"],
            "to": [
                "to", "drop", "destination", "तक", "को", "में", "जाना", "jana", "jaana", "tak",
                "পর্যন্ত", "যাব", "যেতে", "jabo", "jete",
            ],
            "schedule": [
                "now", "today", "tomorrow", "morning", "afternoon", "evening", "night", "am", "pm",
                "date", "tarikh", "tareekh", "tarik",
                "अभी", "आज", "कल", "परसों", "सुबह", "दोपहर", "शाम", "रात", "बजे", "तारीख", "दिनांक",
                "abhi", "aaj", "aj", "kal", "parso", "parson", "subah", "dopahar", "shaam", "sham", "raat", "baje",
                "এখন", "আজ", "আগামীকাল", "পরশু", "কাল", "সকাল", "দুপুর", "বিকেল", "সন্ধ্যা", "রাত", "টা", "তারিখ",
                "ekhon", "agamikal", "porshu", "sokal", "dupur", "bikel", "sondha", "shondha",
            ],
            "exit": ["exit", "stop", "quit", "close", "बंद", "रुको", "band", "ruko", "বন্ধ", "থামুন", "bondho", "thamun"],
        }
        
        self.recognizer.pause_threshold = 1.0 
        self.recognizer.energy_threshold = 4000  
        self.recognizer.dynamic_energy_threshold = True 

        # Known locations database
        self.locations = [
            "Howrah", "Kolkata", "Salt Lake", "New Town", "Park Street",
            "Dumdum", "Garia", "Sealdah", "Newtown", "Bangalore", "Airport","Karunamoyee","Tollygunge","Esplanade","Rabindra Sadan","Shyambazar",
            "Titagarh","Barasat","Sodepur","Belgharia","Dum Dum Cantonment","Kalyani","Madhyamgram","Baranagar","Jadavpur","Gariahat",
            "Bidhannagar","Kankurgachi","Maniktala","Phoolbagan","Baguiati","Rajarhat","Ultadanga","Kamarhati","Sarsuna","New Alipore",
        ]

        self.pickup = None
        self.drop = None
        self.travel_date = None  # Store travel date preference
        self.timing = None  # Store timing preference

        self.setup_browser()

    # ------------------ SETUP ------------------

    def setup_browser(self):
        service = Service(ChromeDriverManager().install())

        base = os.path.dirname(os.path.abspath(__file__))
        profile_path = os.path.join(base, "chrome-profile")
        path = os.path.join(base, "travel-test-site.html")

        chrome_options = Options()
        chrome_options.add_argument(f"--user-data-dir={profile_path}")
        chrome_options.add_argument("--use-fake-ui-for-media-stream")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_experimental_option("prefs", {
            "profile.default_content_setting_values.media_stream_mic": 1,
            "profile.default_content_setting_values.media_stream_camera": 1,
            "profile.default_content_setting_values.geolocation": 1,
            "profile.default_content_setting_values.notifications": 1,
        })

        self.driver = webdriver.Chrome(service=service, options=chrome_options)

        url = f"file:///{path.replace(os.sep, '/')}"
        self.driver.get(url)

        time.sleep(2)

    # ------------------ VOICE ------------------

    def detect_tts_voices(self):
        voices = {"en": None, "hi": None, "bn": None}
        try:
            for voice in self.engine.getProperty("voices"):
                voice_text = " ".join([
                    str(getattr(voice, "id", "")),
                    str(getattr(voice, "name", "")),
                    str(getattr(voice, "languages", "")),
                ]).lower()

                if voices["hi"] is None and any(word in voice_text for word in ["hindi", "hi-in", "hi_in", "hi"]):
                    voices["hi"] = voice.id
                if voices["bn"] is None and any(word in voice_text for word in ["bengali", "bangla", "bn-in", "bn"]):
                    voices["bn"] = voice.id
                if voices["en"] is None and any(word in voice_text for word in ["english", "en-us", "en-in", "en_gb"]):
                    voices["en"] = voice.id
        except Exception:
            pass

        return voices

    def has_hindi_text(self, text):
        return bool(re.search(r'[\u0900-\u097F]', text))

    def has_bangla_text(self, text):
        return bool(re.search(r'[\u0980-\u09FF]', text))

    def detect_language(self, text):
        text_lower = text.lower()
        if self.has_hindi_text(text):
            return "hi"
        if self.has_bangla_text(text):
            return "bn"

        hindi_score = self.language_keyword_score(text_lower, "hi")
        bangla_score = self.language_keyword_score(text_lower, "bn")
        if hindi_score > bangla_score and hindi_score > 0:
            return "hi"
        if bangla_score > hindi_score and bangla_score > 0:
            return "bn"
        return "en"

    def language_keyword_score(self, text, language):
        if language == "hi":
            words = [
                "mujhe", "muje", "mai", "main", "jana", "jaana", "chahiye", "kardo", "kar do",
                "aaj", "abhi", "kal", "subah", "dopahar", "shaam", "sham", "raat", "baje",
            ]
        elif language == "bn":
            words = [
                "ami", "amake", "amar", "theke", "jabo", "jete", "chai", "lagbe", "koro",
                "aj", "ekhon", "agamikal", "sokal", "dupur", "bikel", "sondha", "shondha",
            ]
        else:
            words = []

        return sum(1 for word in words if word in text)

    def load_hindi_translator(self):
        global AutoTokenizer, AutoModelForSeq2SeqLM

        if self.hindi_tokenizer and self.hindi_model:
            return True
        if AutoTokenizer is None or AutoModelForSeq2SeqLM is None:
            try:
                from transformers import AutoTokenizer as TransformersAutoTokenizer
                from transformers import AutoModelForSeq2SeqLM as TransformersAutoModelForSeq2SeqLM
                AutoTokenizer = TransformersAutoTokenizer
                AutoModelForSeq2SeqLM = TransformersAutoModelForSeq2SeqLM
            except ImportError:
                print("Transformers library not found. Hindi translation will be unavailable.")
                return False

        try:
            self.hindi_tokenizer = AutoTokenizer.from_pretrained("Helsinki-NLP/opus-mt-en-hi")
            self.hindi_model = AutoModelForSeq2SeqLM.from_pretrained("Helsinki-NLP/opus-mt-en-hi")
            return True
        except Exception as e:
            print(f"Hindi translator unavailable: {e}")
            self.hindi_tokenizer = None
            self.hindi_model = None
            return False

    def translate_english_to_hindi(self, text):
        if not self.load_hindi_translator() or not self.hindi_tokenizer or not self.hindi_model:
            return text

        try:
            inputs = self.hindi_tokenizer([text], return_tensors="pt", padding=True)
            translated = self.hindi_model.generate(**inputs, max_length=128)
            return self.hindi_tokenizer.decode(translated[0], skip_special_tokens=True)
        except Exception as e:
            print(f"Hindi translation failed: {e}")
            return text

    def speak(self, text, language=None):
        language = language or self.detect_language(text)
        print("Bot:", text)
        voice_id = self.voice_ids.get(language)
        if voice_id:
            self.engine.setProperty("voice", voice_id)
        self.engine.say(text)
        self.engine.runAndWait()

    def respond(self, english_text, hindi_text=None, bangla_text=None):
        if self.current_language == "hi":
            self.speak(hindi_text or self.translate_english_to_hindi(english_text), language="hi")
        elif self.current_language == "bn" and bangla_text:
            self.speak(bangla_text, language="bn")
        else:
            self.speak(english_text, language="en")

    def listen(self):
        try:
            if sd is not None:
                audio = self.listen_with_sounddevice()
            else:
                with sr.Microphone() as source:
                    print("🎤 Listening with PyAudio...")
                    # Adjust for ambient noise and listen with timeout
                    self.recognizer.adjust_for_ambient_noise(source, duration=1.0)
                    audio = self.recognizer.listen(source, timeout=15, phrase_time_limit=20)

            try:
                # Use getattr to avoid static attribute access issues in some analyzers
                recognizer_method = getattr(self.recognizer, "recognize_google", None)
                if callable(recognizer_method):
                    text = self.recognize_dynamic_language(recognizer_method, audio)
                else:
                    # Fallback: try the alternative API name if present
                    raise sr.RequestError("Speech recognition method not available")
                print("User:", text)
                self.current_language = self.detect_language(str(text))
                return str(text).lower()
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

    def listen_with_sounddevice(self, duration=8, sample_rate=16000):
        if sd is None:
            raise RuntimeError("sounddevice is not installed. Install it with: pip install sounddevice")

        print("🎤 Listening with sounddevice...")
        frames = int(duration * sample_rate)
        recording = sd.rec(frames, samplerate=sample_rate, channels=1, dtype="int16")
        sd.wait()
        return sr.AudioData(recording.tobytes(), sample_rate, 2)

    def recognize_dynamic_language(self, recognizer_method, audio):
        candidates = []

        for language_code in ["hi-IN", "bn-IN", "en-IN"]:
            try:
                recognized_text = str(recognizer_method(audio, language=language_code))
                detected_language = self.detect_language(recognized_text)
                score = self.score_recognition_candidate(recognized_text, language_code, detected_language)
                candidates.append((score, recognized_text, detected_language, language_code))
                print(f"Candidate {language_code}: {recognized_text} | score={score}")
            except sr.UnknownValueError:
                continue

        if not candidates:
            raise sr.UnknownValueError()

        candidates.sort(key=lambda item: item[0], reverse=True)
        best_score, best_text, best_language, best_code = candidates[0]
        self.current_language = best_language
        print(f"Selected language: {self.language_names.get(best_language, best_language)} ({best_code})")
        return best_text

    def score_recognition_candidate(self, text, language_code, detected_language):
        text_lower = self.normalize_for_matching(text)
        score = 0

        if language_code.startswith(detected_language):
            score += 6
        if self.has_hindi_text(text) and language_code.startswith("hi"):
            score += 10
        if self.has_bangla_text(text) and language_code.startswith("bn"):
            score += 10

        score += len(self.extract_locations(text_lower)) * 4
        for intent in self.intent_words:
            if self.has_intent(text_lower, intent):
                score += 5

        score += min(len(text_lower.split()), 12)
        return score

    # ------------------ SELENIUM ------------------

    def set_input(self, id, value):
        try:
            if self.driver is None:
                return
            el = self.driver.find_element(By.ID, id)
            el.clear()
            el.send_keys(value)
        except:
            pass

    def click(self, id):
        try:
            # Ensure driver is available
            if self.driver is None:
                print(f"✗ Cannot click {id}: WebDriver is not initialized")
                return
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
                if self.driver is None:
                    return
                element = self.driver.find_element(By.ID, id)
                self.driver.execute_script("arguments[0].click();", element)
                print(f"✓ Clicked {id} using JS")
            except Exception as e2:
                print(f"✗ JS click also failed: {e2}")

    # ------------------ LOGIC ------------------

    def tokenize_hindi(self, text):
        if not self.has_hindi_text(text):
            return []

        if nltk:
            try:
                return nltk.word_tokenize(text)
            except Exception:
                pass

        return re.findall(r'[\u0900-\u097F]+', text)

    def normalize_indic_digits(self, text):
        digit_map = str.maketrans("०१२३४५६७८९০১২৩৪৫৬৭৮৯", "01234567890123456789")
        return text.translate(digit_map)

    def number_word_map(self):
        return {
            "zero": 0, "one": 1, "ek": 1, "एक": 1, "এক": 1,
            "two": 2, "do": 2, "दो": 2, "দুই": 2, "dui": 2,
            "three": 3, "teen": 3, "तीन": 3, "তিন": 3, "tin": 3,
            "four": 4, "char": 4, "chaar": 4, "चार": 4, "চার": 4,
            "five": 5, "panch": 5, "paanch": 5, "पांच": 5, "पाँच": 5, "পাঁচ": 5, "pach": 5,
            "six": 6, "chhe": 6, "che": 6, "छह": 6, "छः": 6, "ছয়": 6, "ছয়": 6, "choy": 6,
            "seven": 7, "saat": 7, "सात": 7, "সাত": 7, "sat": 7,
            "eight": 8, "aath": 8, "आठ": 8, "আট": 8, "aat": 8,
            "nine": 9, "nau": 9, "नौ": 9, "নয়": 9, "নয়": 9, "noy": 9,
            "ten": 10, "das": 10, "दस": 10, "দশ": 10, "dosh": 10,
            "eleven": 11, "gyarah": 11, "ग्यारह": 11, "এগারো": 11, "egaro": 11,
            "twelve": 12, "barah": 12, "बारह": 12, "বারো": 12, "baro": 12,
            "thirteen": 13, "terah": 13, "तेरह": 13, "তেরো": 13, "tero": 13,
            "fourteen": 14, "chaudah": 14, "चौदह": 14, "চৌদ্দ": 14, "chouddo": 14,
            "fifteen": 15, "pandrah": 15, "पंद्रह": 15, "पन्द्रह": 15, "পনেরো": 15, "ponero": 15,
            "sixteen": 16, "solah": 16, "सोलह": 16, "ষোল": 16, "sholo": 16,
            "seventeen": 17, "satrah": 17, "सत्रह": 17, "সতেরো": 17, "sotero": 17,
            "eighteen": 18, "atharah": 18, "अठारह": 18, "আঠারো": 18, "atharo": 18,
            "nineteen": 19, "unnis": 19, "उन्नीस": 19, "উনিশ": 19, "unish": 19,
            "twenty": 20, "bees": 20, "बीस": 20, "বিশ": 20, "bish": 20,
            "twenty one": 21, "ikkees": 21, "इक्कीस": 21, "একুশ": 21, "ekush": 21,
            "twenty two": 22, "bais": 22, "baees": 22, "बाईस": 22, "বাইশ": 22, "baish": 22,
            "twenty three": 23, "teis": 23, "तेईस": 23, "তেইশ": 23, "teish": 23,
            "twenty four": 24, "chaubees": 24, "चौबीस": 24, "চব্বিশ": 24, "chobbish": 24,
            "twenty five": 25, "pachchees": 25, "पच्चीस": 25, "পঁচিশ": 25, "pochish": 25,
            "twenty six": 26, "chhabbees": 26, "छब्बीस": 26, "ছাব্বিশ": 26, "chabbish": 26,
            "twenty seven": 27, "sattais": 27, "सत्ताईस": 27, "সাতাশ": 27, "satash": 27,
            "twenty eight": 28, "atthais": 28, "अट्ठाईस": 28, "আটাশ": 28, "atash": 28,
            "twenty nine": 29, "untis": 29, "उनतीस": 29, "ঊনত্রিশ": 29, "unotrish": 29,
            "thirty": 30, "tees": 30, "तीस": 30, "ত্রিশ": 30, "trish": 30,
            "thirty one": 31, "ikattis": 31, "इकतीस": 31, "একত্রিশ": 31, "ekotrish": 31,
        }

    def normalize_spoken_numbers(self, text):
        normalized = text
        for word, value in sorted(self.number_word_map().items(), key=lambda item: len(item[0]), reverse=True):
            normalized = re.sub(rf'(?<!\w){re.escape(word)}(?!\w)', str(value), normalized)
        return normalized

    def month_aliases(self):
        return {
            1: ["january", "jan", "जनवरी", "janvari", "জানুয়ারি", "জানুয়ারি", "januari"],
            2: ["february", "feb", "फरवरी", "farvari", "ফেব্রুয়ারি", "ফেব্রুয়ারি", "februari"],
            3: ["march", "mar", "मार्च", "মার্চ"],
            4: ["april", "apr", "अप्रैल", "aprail", "এপ্রিল"],
            5: ["may", "मई", "mai", "মে"],
            6: ["june", "jun", "जून", "জুন"],
            7: ["july", "jul", "जुलाई", "julai", "জুলাই"],
            8: ["august", "aug", "अगस्त", "agast", "আগস্ট", "agost"],
            9: ["september", "sep", "sept", "सितंबर", "sitambar", "সেপ্টেম্বর"],
            10: ["october", "oct", "अक्टूबर", "aktubar", "অক্টোবর"],
            11: ["november", "nov", "नवंबर", "navambar", "নভেম্বর"],
            12: ["december", "dec", "दिसंबर", "disambar", "ডিসেম্বর"],
        }

    def normalize_for_matching(self, text):
        text = self.normalize_indic_digits(text.lower())
        text = self.normalize_spoken_numbers(text)
        text = re.sub(r'[।,;:!?]+', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        replacements = {
            "haora": "howrah",
            "hawra": "howrah",
            "haurah": "howrah",
            "newtown": "new town",
            "saltlake": "salt lake",
            "dum dum": "dumdum",
            "kaal": "kal",
            "shokal": "sokal",
            "shondha": "sondha",
            "shaam": "sham",
            "raaid": "ride",
            "raide": "ride",
            "raid": "ride",
            "right": "ride",
            "write": "ride",
            "राइट": "राइड",
            "राईट": "राइड",
            "राईड": "राइड",
            "रायड": "राइड",
            "রাইট": "রাইড",
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        return text

    def text_tokens(self, text):
        return re.findall(r'[\w\u0900-\u097F\u0980-\u09FF]+', text, flags=re.UNICODE)

    def contains_any(self, text, words):
        text_lower = self.normalize_for_matching(text)
        tokens = set(self.text_tokens(text_lower))

        for word in words:
            word_lower = self.normalize_for_matching(word)
            if not word_lower:
                continue
            if " " in word_lower:
                if word_lower in text_lower:
                    return True
            elif len(word_lower) <= 3 and word_lower.isascii():
                if word_lower in tokens:
                    return True
            elif word_lower in text_lower or word_lower in tokens:
                return True

        return False

    def fuzzy_contains_any(self, text, words, threshold=0.82):
        text_lower = self.normalize_for_matching(text)
        tokens = self.text_tokens(text_lower)

        for token in tokens:
            if len(token) < 4:
                continue
            for word in words:
                word_lower = self.normalize_for_matching(word)
                if " " in word_lower or len(word_lower) < 4:
                    continue
                ratio = SequenceMatcher(None, token, word_lower).ratio()
                if ratio >= threshold:
                    return True

        return False

    def has_intent(self, text, intent):
        text_lower = self.normalize_for_matching(text)
        words = self.intent_words.get(intent, [])
        return self.contains_any(text_lower, words) or self.fuzzy_contains_any(text_lower, words)

    def extract_locations(self, text):
        """Extract and validate location names from user input"""
        found_locations = []
        text_lower = self.normalize_for_matching(text)
        location_aliases = {
            "Howrah": ["howrah", "haora", "hawra", "haurah", "हावड़ा", "हावड़ा", "हावडा", "হাওড়া", "হাওড়া"],
            "Kolkata": ["kolkata", "calcutta", "kolkata city", "कोलकाता", "কলকাতা"],
            "Salt Lake": ["salt lake", "saltlake", "साल्ट लेक", "সল্ট লেক", "সল্টলেক"],
            "New Town": ["new town", "newtown", "न्यू टाउन", "न्यूटाउन", "নিউ টাউন", "নিউটাউন"],
            "Park Street": ["park street", "पार्क स्ट्रीट", "পার্ক স্ট্রিট"],
            "Dumdum": ["dumdum", "dum dum", "दमदम", "दुमदुम", "দমদম"],
            "Garia": ["garia", "गरिया", "गड़िया", "গড়িয়া", "গড়িয়া"],
            "Sealdah": ["sealdah", "सियालदह", "শিয়ালদহ", "শিয়ালদহ"],
            "Airport": ["airport", "एयरपोर्ट", "हवाई अड्डा", "এয়ারপোর্ট", "এয়ারপোর্ট", "বিমানবন্দর"],
        }
        
        for location in self.locations:
            aliases = location_aliases.get(location, [location.lower()])
            if any(alias.lower() in text_lower for alias in aliases):
                found_locations.append(location)
        
        return found_locations

    def build_travel_date(self, day, month, year=None, roll_forward=True):
        try:
            today = date.today()
            explicit_year = year is not None
            selected_year = year or today.year
            if selected_year < 100:
                selected_year += 2000

            selected_date = date(selected_year, month, day)
            if roll_forward and not explicit_year and selected_date < today:
                selected_date = date(selected_year + 1, month, day)

            return selected_date.strftime("%d %B %Y")
        except ValueError:
            return None

    def build_date_from_day_only(self, day):
        today = date.today()
        month = today.month
        year = today.year

        try:
            selected_date = date(year, month, day)
            if selected_date < today:
                month += 1
                if month > 12:
                    month = 1
                    year += 1
                selected_date = date(year, month, day)
            return selected_date.strftime("%d %B %Y")
        except ValueError:
            return None

    def extract_named_date(self, text):
        text_lower = self.normalize_for_matching(text)

        for month_number, aliases in self.month_aliases().items():
            for alias in sorted(aliases, key=len, reverse=True):
                alias_lower = self.normalize_for_matching(alias)
                patterns = [
                    rf'(?:^|\s)(\d{{1,2}})(?:st|nd|rd|th)?\s+{re.escape(alias_lower)}(?:\s+(\d{{2,4}}))?(?=\s|$)',
                    rf'(?:^|\s){re.escape(alias_lower)}\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:\s+(\d{{2,4}}))?(?=\s|$)',
                ]

                for pattern in patterns:
                    match = re.search(pattern, text_lower)
                    if match:
                        day = int(match.group(1))
                        year = int(match.group(2)) if match.group(2) else None
                        travel_date = self.build_travel_date(day, month_number, year)
                        if travel_date:
                            return travel_date

        date_marker_match = re.search(
            r'(?:^|\s)(\d{1,2})(?:st|nd|rd|th)?\s*(?:date|tarikh|tareekh|tarik|तारीख|दिनांक|তারিখ)(?=\s|$)',
            text_lower
        )
        if date_marker_match:
            return self.build_date_from_day_only(int(date_marker_match.group(1)))

        reverse_marker_match = re.search(
            r'(?:date|tarikh|tareekh|tarik|तारीख|दिनांक|তারিখ)\s*(\d{1,2})(?:st|nd|rd|th)?(?=\s|$)',
            text_lower
        )
        if reverse_marker_match:
            return self.build_date_from_day_only(int(reverse_marker_match.group(1)))

        return None

    def has_date_hint(self, text):
        text_lower = self.normalize_for_matching(text)
        if re.search(r'\b\d{1,2}[/-]\d{1,2}', text_lower):
            return True
        if re.search(r'\b\d{1,2}\s*(?:date|tarikh|tareekh|tarik|तारीख|दिनांक|তারিখ)\b', text_lower):
            return True
        for aliases in self.month_aliases().values():
            if self.contains_any(text_lower, aliases):
                return True
        return False

    def extract_schedule(self, text):
        """Extract date and timing from user input."""
        text_lower = self.normalize_for_matching(text)
        travel_date = None
        timing = None

        if self.contains_any(text_lower, ["today", "now", "आज", "अभी", "aaj", "aj", "abhi", "আজ", "এখন", "ekhon"]):
            travel_date = date.today().strftime("%d %B %Y")
        elif self.contains_any(text_lower, ["tomorrow", "कल", "kal", "আগামীকাল", "agamikal", "কাল"]):
            travel_date = (date.today() + timedelta(days=1)).strftime("%d %B %Y")
        elif self.contains_any(text_lower, ["day after tomorrow", "parso", "parson", "परसों", "porshu", "পরশু"]):
            travel_date = (date.today() + timedelta(days=2)).strftime("%d %B %Y")

        date_match = re.search(r'\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b', text_lower)
        if date_match:
            day = int(date_match.group(1))
            month = int(date_match.group(2))
            year_text = date_match.group(3)
            year = int(year_text) if year_text else date.today().year
            if year < 100:
                year += 2000

            try:
                travel_date = datetime(year, month, day).strftime("%d %B %Y")
            except ValueError:
                travel_date = date_match.group(0)

        named_date = self.extract_named_date(text_lower)
        if named_date:
            travel_date = named_date

        time_match = re.search(r'(?:^|\s)(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.|बजे|baje|o.?clock|টা|টায়|টায়)(?=\s|$)', text_lower)
        if self.contains_any(text_lower, ["now", "अभी", "abhi", "এখন", "ekhon"]):
            timing = "Now"
        elif time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or 0)
            period = time_match.group(3).replace(".", "").lower()
            if period == "pm" and hour < 12:
                hour += 12
            elif period == "am" and hour == 12:
                hour = 0
            elif period in ["बजे", "baje", "টা", "টায়", "টায়"]:
                if self.contains_any(text_lower, ["दोपहर", "शाम", "sham", "raat", "रात", "বিকেল", "সন্ধ্যা", "sondha"]) and hour < 12:
                    hour += 12

            timing = datetime.strptime(f"{hour:02d}:{minute:02d}", "%H:%M").strftime("%I:%M %p").lstrip("0")
        elif self.contains_any(text_lower, ["morning", "सुबह", "subah", "sokal", "সকাল"]):
            timing = "Morning (8-11 AM)"
        elif self.contains_any(text_lower, ["afternoon", "दोपहर", "dopahar", "dupur", "দুপুর", "বিকেল"]):
            timing = "Afternoon (12-3 PM)"
        elif self.contains_any(text_lower, ["evening", "शाम", "sham", "shaam", "sondha", "সন্ধ্যা"]):
            timing = "Evening (4-7 PM)"
        elif self.contains_any(text_lower, ["night", "रात", "raat", "রাত"]):
            timing = "Night (8 PM onwards)"

        if timing and not travel_date:
            travel_date = date.today().strftime("%d %B %Y")

        return travel_date, timing

    def handle_command(self, text):
        self.current_language = self.detect_language(text)
        text = self.normalize_for_matching(text)
        hindi_tokens = self.tokenize_hindi(text)
        print("Language:", self.language_names.get(self.current_language, "English"))
        if hindi_tokens:
            print("Hindi NLP tokens:", hindi_tokens)

        # Confirm what was heard
        self.respond(
            f"You said: {text}",
            f"आपने कहा: {text}",
            f"আপনি বলেছেন: {text}"
        )
        time.sleep(0.5)

        # EXIT
        if self.has_intent(text, "exit"):
            self.respond(
                "Stopping the carpool assistant. Goodbye!",
                "कारपूल असिस्टेंट बंद कर रहा हूं। धन्यवाद!",
                "কারপুল সহকারী বন্ধ করছি। ধন্যবাদ!"
            )
            if self.driver is not None:
                self.driver.quit()
            exit()

        found_locations = self.extract_locations(text)
        looks_like_booking = self.has_intent(text, "book") or (
            len(found_locations) >= 2 and (self.has_intent(text, "from") or self.has_intent(text, "to"))
        )

        # BOOK - Extract both locations at once and ask for timing
        if looks_like_booking:
            
            if len(found_locations) >= 2:
                # Both locations found - ask for timing immediately
                self.pickup = found_locations[0]
                self.drop = found_locations[1]
                self.respond(
                    f"Booking ride from {self.pickup} to {self.drop}. When do you want the ride?",
                    f"{self.pickup} से {self.drop} तक राइड बुक कर रहा हूं। आप कब जाना चाहते हैं?",
                    f"{self.pickup} থেকে {self.drop} পর্যন্ত রাইড বুক করছি। আপনি কখন যেতে চান?"
                )
                self.respond(
                    f"I found your pickup as {self.pickup} and your destination as {self.drop}.",
                    f"पिकअप {self.pickup} और डेस्टिनेशन {self.drop} मिला है।",
                    f"পিকআপ {self.pickup}, গন্তব্য {self.drop}।"
                )
                self.respond(
                    "Say: now, today, tomorrow morning, or a date and time like 5 May at 3 PM",
                    "बोलिए: अभी, आज, कल सुबह, या 5 मई शाम 3 बजे।",
                    "বলুন: এখন, আজ, আগামীকাল সকাল, অথবা ৫ মে বিকেল ৩ টা।"
                )
                return
            elif len(found_locations) == 1:
                # Only one location found
                self.pickup = found_locations[0]
                self.respond(
                    f"Pickup location is {self.pickup}. Where would you like to go?",
                    f"पिकअप लोकेशन {self.pickup} है। आप कहां जाना चाहते हैं?",
                    f"পিকআপ লোকেশন {self.pickup}। আপনি কোথায় যেতে চান?"
                )
                return
            else:
                # No locations found - provide valid options
                locations_list = ", ".join(self.locations[:8])  # List first 8 locations
                self.respond(
                    f"Available locations are: {locations_list}. Please say: Book ride from Howrah to New Town",
                    f"उपलब्ध लोकेशन हैं: {locations_list}। बोलिए: हावड़ा से न्यू टाउन राइड बुक करो।",
                    f"লোকেশনগুলো হলো: {locations_list}। বলুন: হাওড়া থেকে নিউ টাউন রাইড বুক করুন।"
                )
                return

        # TIMING - Handle timing preferences
        schedule_words = [
            "now", "today", "tomorrow", "morning", "afternoon", "evening", "night", "am", "pm",
            "अभी", "आज", "कल", "सुबह", "दोपहर", "शाम", "रात", "बजे",
            "abhi", "aaj", "aj", "kal", "parso", "parson", "subah", "dopahar", "sham", "raat", "baje",
            "এখন", "আজ", "আগামীকাল", "পরশু", "সকাল", "দুপুর", "বিকেল", "সন্ধ্যা", "রাত", "টা",
            "ekhon", "agamikal", "sokal", "dupur", "bikel", "sondha"
        ]
        if self.has_intent(text, "schedule") or any(word in text for word in schedule_words) or self.has_date_hint(text):
            if not self.pickup or not self.drop:
                locations_list = ", ".join(self.locations[:8])
                self.respond(
                    f"Please provide both pickup and dropoff locations first. Valid options: {locations_list}",
                    f"पहले पिकअप और ड्रॉप दोनों लोकेशन बताइए। उपलब्ध लोकेशन: {locations_list}",
                    f"আগে পিকআপ এবং ড্রপ লোকেশন বলুন। লোকেশনগুলো হলো: {locations_list}"
                )
                return
            
            self.travel_date, self.timing = self.extract_schedule(text)
            if not self.travel_date:
                self.travel_date = date.today().strftime("%d %B %Y")
            if not self.timing:
                self.timing = "As soon as possible"
            
            self.respond(
                f"Ride scheduled on {self.travel_date} at {self.timing}.",
                f"राइड {self.travel_date} को {self.timing} पर शेड्यूल हो गई है।",
                f"রাইডটি {self.travel_date} তারিখে {self.timing} সময়ে রাখা হলো।"
            )
            time.sleep(1)
            self.book_ride()
            return

        # FROM - Extract pickup location
        if self.has_intent(text, "from"):
            found_locations = self.extract_locations(text)
            if found_locations:
                self.pickup = found_locations[0]
                self.respond(
                    f"Pickup set to {self.pickup}. Where do you want to go?",
                    f"पिकअप {self.pickup} सेट हो गया है। आप कहां जाना चाहते हैं?",
                    f"পিকআপ {self.pickup} সেট করা হয়েছে। আপনি কোথায় যেতে চান?"
                )
            else:
                locations_list = ", ".join(self.locations[:8])
                self.respond(
                    f"Pickup location not found. Valid options: {locations_list}",
                    f"पिकअप लोकेशन नहीं मिली। उपलब्ध लोकेशन: {locations_list}",
                    f"পিকআপ লোকেশন পাওয়া যায়নি। লোকেশনগুলো হলো: {locations_list}"
                )
            return

        # TO - Extract drop location
        if self.has_intent(text, "to"):
            found_locations = self.extract_locations(text)
            if found_locations:
                self.drop = found_locations[0]
                if self.pickup and self.drop:
                    self.respond(
                        f"Ride from {self.pickup} to {self.drop}. When do you want the ride?",
                        f"{self.pickup} से {self.drop} तक राइड। आप कब जाना चाहते हैं?",
                        f"{self.pickup} থেকে {self.drop} পর্যন্ত রাইড। আপনি কখন যেতে চান?"
                    )
                    self.respond(
                        "Say: now, today, tomorrow morning, or a date and time like 5 May at 3 PM",
                        "बोलिए: अभी, आज, कल सुबह, या 5 मई शाम 3 बजे।",
                        "বলুন: এখন, আজ, আগামীকাল সকাল, অথবা ৫ মে বিকেল ৩ টা।"
                    )
                    return
                elif self.pickup:
                    self.respond(
                        f"Destination set to {self.drop}. When do you want to go?",
                        f"डेस्टिनेशन {self.drop} सेट हो गया है। आप कब जाना चाहते हैं?",
                        f"গন্তব্য {self.drop} সেট করা হয়েছে। আপনি কখন যেতে চান?"
                    )
                else:
                    pickup_list = ", ".join(self.locations[:8])
                    self.respond(
                        f"Please tell me the pickup location first. Valid options: {pickup_list}",
                        f"पहले पिकअप लोकेशन बताइए। उपलब्ध लोकेशन: {pickup_list}",
                        f"আগে পিকআপ লোকেশন বলুন। লোকেশনগুলো হলো: {pickup_list}"
                    )
            else:
                locations_list = ", ".join(self.locations[:8])
                self.respond(
                    f"Destination not recognized. Valid options: {locations_list}",
                    f"डेस्टिनेशन समझ नहीं आया। उपलब्ध लोकेशन: {locations_list}",
                    f"গন্তব্য বুঝতে পারিনি। লোকেশনগুলো হলো: {locations_list}"
                )
            return

        locations_list = ", ".join(self.locations[:8])
        self.respond(
            f"I didn't understand. Try: Book ride from Howrah to New Town. Valid locations: {locations_list}",
            f"मैं समझ नहीं पाया। बोलिए: हावड़ा से न्यू टाउन राइड बुक करो। उपलब्ध लोकेशन: {locations_list}",
            f"আমি বুঝতে পারিনি। বলুন: হাওড়া থেকে নিউ টাউন রাইড বুক করুন। লোকেশনগুলো হলো: {locations_list}"
        )

    # ------------------ BOOKING ------------------

    def book_ride(self):

        if not self.pickup or not self.drop:
            self.respond("Incomplete booking details.", "बुकिंग की जानकारी अधूरी है।", "বুকিংয়ের তথ্য সম্পূর্ণ নয়।")
            self.respond(
                "Please tell me both the pickup location and destination before booking.",
                "बुकिंग से पहले पिकअप और डेस्टिनेशन दोनों बताइए।",
                "বুকিংয়ের আগে পিকআপ এবং গন্তব্য দুটোই বলুন।"
            )
            return

        print(f"\n📍 Booking: {self.pickup} → {self.drop}")
        if self.timing:
            print(f"⏰ Timing: {self.timing}\n")
        if self.travel_date:
            print(f"📅 Date: {self.travel_date}\n")

        self.respond("Great, I have all the booking details.", "ठीक है, बुकिंग की सारी जानकारी मिल गई है।", "ভালো, বুকিংয়ের সব তথ্য পেয়েছি।")
        self.respond(f"Pickup is {self.pickup}.", f"पिकअप {self.pickup} है।", f"পিকআপ হলো {self.pickup}।")
        self.respond(f"Destination is {self.drop}.", f"डेस्टिनेशन {self.drop} है।", f"গন্তব্য হলো {self.drop}।")
        self.respond(f"Travel date is {self.travel_date or 'your requested date'}.", f"यात्रा की तारीख {self.travel_date or 'आपकी बताई हुई तारीख'} है।", f"যাত্রার তারিখ {self.travel_date or 'আপনার বলা তারিখ'}।")
        self.respond(f"Travel timing is {self.timing or 'your requested time'}.", f"यात्रा का समय {self.timing or 'आपका बताया हुआ समय'} है।", f"যাত্রার সময় {self.timing or 'আপনার বলা সময়'}।")
        self.respond("I am filling the ride search form now.", "मैं अब राइड सर्च फॉर्म भर रहा हूं।", "আমি এখন রাইড সার্চ ফর্ম পূরণ করছি।")
        
        self.set_input("from", self.pickup)
        time.sleep(0.5)
        self.set_input("to", self.drop)
        time.sleep(0.5)

        print("Clicking search button...")
        self.respond("Searching for available rides.", "उपलब्ध राइड खोज रहा हूं।", "উপলব্ধ রাইড খুঁজছি।")
        self.click("searchBtn")
        time.sleep(2)

        print("Clicking book button to proceed to payment...")
        self.respond("I found an available ride.", "एक उपलब्ध राइड मिल गई है।", "একটি রাইড পাওয়া গেছে।")
        self.respond(
            f"Booking ride from {self.pickup} to {self.drop} on {self.travel_date or 'your requested date'} at {self.timing or 'requested time'}.",
            f"{self.pickup} से {self.drop} तक {self.travel_date or 'आपकी बताई हुई तारीख'} को {self.timing or 'आपके बताए हुए समय'} पर राइड बुक कर रहा हूं।",
            f"{self.pickup} থেকে {self.drop} পর্যন্ত {self.travel_date or 'আপনার বলা তারিখ'} তারিখে {self.timing or 'আপনার বলা সময়'} সময়ে রাইড বুক করছি।"
        )
        time.sleep(1)
        
        self.click("bookBtn")
        time.sleep(3)

        self.respond("Your ride booking is ready.", "आपकी राइड बुकिंग तैयार है।", "আপনার রাইড বুকিং প্রস্তুত।")
        self.respond("I have opened the payment page for you.", "मैंने आपके लिए पेमेंट पेज खोल दिया है।", "আমি আপনার জন্য পেমেন্ট পেজ খুলেছি।")
        self.respond("Please select the correct payment method to proceed.", "आगे बढ़ने के लिए सही पेमेंट मेथड चुनिए।", "এগিয়ে যেতে সঠিক পেমেন্ট পদ্ধতি নির্বাচন করুন।")
        time.sleep(2)
        self.respond(
            "You can enter your card details, choose the payment amount, and confirm your booking.",
            "कार्ड डिटेल डालिए, पेमेंट अमाउंट चुनिए, और बुकिंग कन्फर्म कीजिए।",
            "কার্ডের তথ্য দিন, পেমেন্ট অ্যামাউন্ট নির্বাচন করুন, তারপর বুকিং কনফার্ম করুন।"
        )
        self.respond(
            "After payment confirmation, your ride will be fully confirmed.",
            "पेमेंट कन्फर्म होने के बाद आपकी राइड पूरी तरह कन्फर्म हो जाएगी।",
            "পেমেন্ট কনফার্ম হলে আপনার রাইড পুরোপুরি নিশ্চিত হবে।"
        )

        # Reset for next booking
        self.pickup = None
        self.drop = None
        self.travel_date = None
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
