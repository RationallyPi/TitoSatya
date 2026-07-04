from selenium import webdriver
import time

driver = webdriver.Firefox()
driver.get("https://www.example.com")
time.sleep(5)  
driver.quit()
