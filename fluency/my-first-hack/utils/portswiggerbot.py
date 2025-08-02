#BOT 
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
import time
import random
import json
from pathlib import Path



class Bot():


    def __init__(self,headless=True):
        """
        Initializes the MyBrowser instance.
        Sets up Chrome WebDriver with headless mode and necessary arguments
        for a minimal and secure browsing session. Also defines login and labs URLs.
        """
        self.LOGIN_URL = 'https://portswigger.net/users'
        self.LABS_URL = 'https://portswigger.net/web-security/all-labs#'
        self.prefixes_filename = 'topics_prefixes.json'
        self.options = Options()
        
        if headless:
            args = ['--headless','--disable-gpu', '--no-sandbox']
        else:
            args = ['--disable-gpu', '--no-sandbox']
            
        for arg in args:
            self.options.add_argument(arg)
        
        self.driver = webdriver.Chrome(options=self.options)


    def __wait_random_time(self,min_seconds=3, max_seconds=5):
        """
        Waits for a random amount of time between min_seconds and max_seconds.

        Args:
            min_seconds (int, optional): Minimum number of seconds to wait. Defaults to 3.
            max_seconds (int, optional): Maximum number of seconds to wait. Defaults to 5.
        """
        duration = random.uniform(min_seconds, max_seconds)
        time.sleep(duration)

    
    def login(self,username,password):
        """
        Logs in to the PortSwigger user portal using the given credentials.

        Args:
            username (str): The email address or username for login.
            password (str): The corresponding password for the user account.

        Opens the login page, waits a random time, then fills and submits the login form.
        """

        #Open the login page
        self.driver.get(self.LOGIN_URL)

        #Wait for the page to load
        self.__wait_random_time()

        #Find and fill in the email field
        email_input = self.driver.find_element(By.ID, "EmailAddress")
        email_input.send_keys(username)

        #Find and fill in the password field
        password_input = self.driver.find_element(By.ID, "Password")
        password_input.send_keys(password)

        #Submit the login form
        password_input.send_keys(Keys.RETURN)

        #Wait for the page to load
        self.__wait_random_time()



    def choose_topic(self,topic_name='cross-site-scripting',level=None):
        """
        Extract urls of each of the labs in the selected section.

        Args:
            topic_name (str): the name of the topic.

        Read topic prefixes files, extract links of labs based by topic section (topic_name) and returns a list of lab urls.
        """

        #Read topic prefixes json file and get prefix for topic_name
        current_folder = Path(__file__).parent
        available_topics = json.loads(open(f'{current_folder}/{self.prefixes_filename}').read())

        #If topic_name does not exists then returns empty list
        try:
            topic_prefix = available_topics[topic_name]
        except KeyError:
            print(f"Topic '{topic_name}' not found")
            return []
        
        #Go to sections urls
        self.driver.get(f'{self.LABS_URL}{topic_name}')
        self.__wait_random_time(min_seconds=5, max_seconds=7)
        
        links = WebDriverWait(self.driver, 10).until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, 'widgetcontainer-lab-link'))
        )
        

    
        
        #Find all <a> elements that have the topic prefix in the href
        links = self.driver.find_elements(By.CLASS_NAME, 'widgetcontainer-lab-link')
   
        
        #Extract the href attributes
        if level:
            extracted_links = [link.find_element(By.TAG_NAME, 'a').get_attribute('href') for link in links if link.find_element(By.TAG_NAME, 'span').text == level]
        else:
            extracted_links = [link.find_element(By.TAG_NAME, 'a').get_attribute('href') for link in links]
        
        #Filter links that contain the topic prefix
        return [link for link in extracted_links if topic_prefix == link.split('/')[4]]

    def obtain_lab_information(self,lab_url):
        """
        Extract the information associated to a lab url.

        Args:
            lab_url (str): the url of the lab.

        Extract the information associated to the lab such as Title, Description, Solution and Environment url.
        """
        
        #Go to lab url
        self.driver.get(lab_url)
        
        #Extract type of lab from url
        labtype = lab_url.split('/')[4]

        #Extract title of the lab
        title = self.driver.find_element(By.CLASS_NAME, 'heading-2').text

        #Extract description of the lab
        description_section = self.driver.find_element(By.CLASS_NAME, "section.theme-white")
        paragraphs = description_section.find_elements(By.XPATH, ".//p[following-sibling::div[@class='container-buttons-left']]")

        #Extract solution of the lab
        solution_sections = self.driver.find_elements(By.CLASS_NAME, "component-solution")
        if len(solution_sections) <=2:
            #when there are no Hint section
            solution_sections[0].find_element(By.TAG_NAME, 'details').click()
            solution = solution_sections[0].find_element(By.CLASS_NAME, 'content').text
        else:
            #when there are Hint section
            solution_sections[1].find_element(By.TAG_NAME, 'details').click()
            solution = solution_sections[1].find_element(By.CLASS_NAME, 'content').text
            
        
        #Extract url to access the lab environment
        ##Find the "Start lab" button and click it
        start_button = self.driver.find_element(By.CLASS_NAME, 'button-orange')
        start_button.click()
        
        ##Get the current tab and switch to the new tab
        main_tab = self.driver.current_window_handle
        lab_tab = [handle for handle in self.driver.window_handles if handle != main_tab][0]
        self.driver.switch_to.window(lab_tab)
        
        ##Get the URL of the lab environment
        environment_url  = self.driver.current_url
        
        ##Close the new tab
        self.driver.close()

        ##Switch back to the main tab
        self.driver.switch_to.window(main_tab)
    
        lab_info = {
            'type': labtype,
            'url': lab_url,
            'title': title,
            'description': "\n".join([p.text for p in paragraphs]),
            'solution': solution,
            'environment_url': environment_url
            }
            
        return lab_info

    def check_solved_lab(self,lab_url):
        """
        Check if lab was solved.

        Args:
            lab_url (str): the url of the lab.

        Go to the lab url and check if status "Solved or Not Solved".
        """
        #Go to lab url
        self.driver.get(lab_url)
        #get  text of status container
        lab_status = self.driver.find_element(By.CLASS_NAME, 'lab-status-icon').text
        return lab_status


        
        
        
        