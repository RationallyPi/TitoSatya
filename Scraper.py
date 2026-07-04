from selenium import webdriver
import time

driver = webdriver.Firefox()


start_date = ''
driver.get("https://www.example.com")
time.sleep(5)  
driver.quit()
