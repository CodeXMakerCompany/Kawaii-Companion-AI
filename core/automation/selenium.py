from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time

class Open:
    def __init__(self):
        # try:
            # Set up ChromeOptions to point to the Brave browser binary
            options = Options()
            options.binary_location = "C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe"  # Path to Brave browser

            # Create a Service object with the path to chromedriver
            service = Service("C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe")
            
            # Pass the options and service to webdriver.Chrome()
            self.driver = webdriver.Chrome(service=service, options=options)