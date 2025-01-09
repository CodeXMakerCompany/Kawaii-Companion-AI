from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

class SeleniumAutomation:
    
    def open_browser(self):
        try:
            options = Options()
            options.binary_location = "C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe"  # Path to Brave browser

            # Create a Service object with the path to chromedriver
            service = Service("C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe")
            
            # Pass the options and service to webdriver.Chrome()
            self.driver = webdriver.Chrome(service=service, options=options)
        except Exception as e:
            print(f"Failed to opeb web browser: {e}")
            return 
        
    def navigate_to_url(self, url):
        """
        Navigate to the specified URL.

        Args:
            url (str): The URL to navigate to.
        """
        self.driver.get(url)
        print(f"Navigated to {url}") 