from utils import save_json, get_file_name
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import ElementClickInterceptedException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import os
import argparse
import time
import json
import re

def modify(text):
    # get rid of "\u"
    text = text.encode('ascii', errors='ignore').strip().decode('ascii')

    return text

# quickly scroll down to bottom of the page
def quick_scroll_to_bottom(driver):

    js = "return action=document.body.scrollHeight"

    #initilize the current height = 0
    height = 0

    #get the height of the current window
    new_height = driver.execute_script(js)

    while height < new_height:

        for i in range(height, new_height, 400):
            driver.execute_script('window.scrollTo(0, {})'.format(i))
            time.sleep(0.2)
            height = new_height
            time.sleep(0.2)
            new_height = driver.execute_script(js)

    time.sleep(2)

# slowly scroll down to the bottom of the page
def slow_scroll_to_bottom(driver):

    temp_height=0

    while True:

        driver.execute_script("window.scrollBy(0,800)")

        time.sleep(4)

        check_height = driver.execute_script("return document.documentElement.scrollTop || window.pageYOffset || document.body.scrollTop;")

        if check_height==temp_height:

            break

        temp_height=check_height

def extract_additional_details_reviews(driver, data, pre_order):
    REVIEWS_PER_PAGE = 5

    # wd.find_element(By.CSS_SELECTOR, 'h1>span')
    details = driver.find_element(By.CLASS_NAME, 'app-details__header')
    driver.execute_script("arguments[0].scrollIntoView();",details)

    time.sleep(2)

    #store information in dictionary
    row_left = driver.find_element(By.CLASS_NAME, "app-details-row__left")
    row_right = driver.find_element(By.CLASS_NAME, "app-details-row__right")

    for index in range(len(row_left)):

        left_name = row_left[index].get_attribute("innerText")
        left_name = re.sub(r'[\s]+', '_', left_name)

        if (left_name == "Developer_Privacy_Policy") or (left_name == "Developer_Terms_of_Service"):

            try:

                parent = row_right[index]

                link = parent.find_element(By.CSS_SELECTOR, "a.app-details-row__link.link.link--clickable")

                link.click()

                # this will open a new tab.Thus, there are total two tabs: app's webpage and privacy's webpage
                app_webpage = 0
                privacy_webpage = 1

                windows = driver.window_handles
                driver.switch_to.window(windows[privacy_webpage])

                data[left_name] = driver.current_url

                # close the new tab and switch to the previous tab
                driver.close()
                driver.switch_to.window(windows[app_webpage])

                time.sleep(2)

            except NoSuchElementException:

                data[left_name] = ''

        else:

            data[left_name] = row_right[index].get_attribute("innerText")

    if pre_order:
        data['Reviews_Stats'] = ""
        data['Review_Count'] = 0
    else:
        # extract star ratings
        star_ratings = driver.find_element(By.CLASS_NAME, 'app-ratings-histogram').get_attribute('innerText')
        data['Reviews_Stats'] = modify(star_ratings)

        try:
            review_pages = driver.find_element(By.CSS_SELECTOR, "div.app-review-pager__number")
            total_page_number = int(review_pages[-1].get_attribute('innerText'))
            review_pages[-1].click()
            time.sleep(2)
            data['Review_Count'] = len(driver.find_element(By.CLASS_NAME, 'app-review')) + (REVIEWS_PER_PAGE * (total_page_number - 1))

            if data['Review_Count'] % 5 == 0 and len(driver.find_element(By.CLASS_NAME, 'app-review')) != 5:
                print("ERROR: something went wrong")

        except IndexError:  # only one page of reviews
            data['Review_Count'] = len(driver.find_element(By.CLASS_NAME, 'app-review'))


def test_extraction_python_org(driver, output_dir, url_list):
    MAX_STAR_VAL = 24

    # access urls on the current webpage
    for url in url_list:
        driver.get(url)

        wait = WebDriverWait(driver, 5)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div.app-description__title')))

        driver.execute_script("window.scrollBy(0,200)")

        # define a dictionary to store an app's information
        data = {}
        data["Oculus_url"] = url

        #extract the title
        data['App_Title'] = driver.find_element(By.CLASS_NAME, "app-description__title").get_attribute("innerText")

        # print (url +  data['App_Title'])
        # exit()

        banner = driver.find_element(By.CLASS_NAME, "div.app__banner").get_attribute("innerHTML") #originally, "text"
        print ("Banner is "+banner)
        if len(banner) > 0 and re.search("Pre-Order", banner):
            pre_order = True
            data['Rating_Count'] = 0
            data['Average_Rating'] = 0
        else:
            pre_order = False
            review_count = driver.find_element(By.CSS_SELECTOR, "div.app-description__review-count").text
            review_count = re.split(r'\s', review_count)[0]
            data['Rating_Count'] = int(re.sub(r',', '', review_count))

            rating_section = driver.find_element(By.CSS_SELECTOR, "a.app-description__star-section")
            average_rating = rating_section.find_element(By.CSS_SELECTOR, "i.bxStars.bxStars--white")
            try:
                fraction = rating_section.find_element(By.CSS_SELECTOR, "div.bxStars.bxStars--white.bxStars--overlay").get_attribute("style")
                data['Average_Rating'] = len(average_rating) + (int(re.search("[\d]+",fraction).group(0)) / MAX_STAR_VAL )
            except:
                data['Average_Rating'] = len(average_rating)

        #extract the description
        text = driver.find_element(By.CLASS_NAME,'store-item-detail-page-description__content').get_attribute("innerText")
        text = modify(text)
        data['App_Description'] = text

        #extract from the purchase section
        text = driver.find_element(By.CLASS_NAME, 'app-purchase').get_attribute("innerText")
        if text.find('$') == -1:
            data['Price'] = 0

        else:
            split_text = re.split(r'[a-zA-z]+', text, 1)
            try:
                data['Price'] = float(split_text[0][1:])
            except:
                split_text = split_text[0].split("$")
                data['Price'] = float(split_text[-1])

        data['Purchase_Section'] = modify(text)

        #scroll up to find "Additional Details & Reviews" section
        extract_additional_details_reviews(driver, data, pre_order)

        # save data as a json file
        # print(data)
        file_name = os.path.join(output_dir, get_file_name(data['App_Title']))
        save_json(file_name, data)

        time.sleep(2)

def get_urls(driver):
    url_list= []

    # scroll to the bottom of the page to obtain all elements
    driver.get('https://www.oculus.com/experiences/quest/section/1888816384764129/')
    slow_scroll_to_bottom(driver)

    # a list of items on the webpage
    for item in driver.find_elements(By.CSS_SELECTOR,'a.store-section-item-tile'):
        url = item.get_attribute("href")
        url_list.append(url)
    # print (url_list)
    # get_attribute("href")
    # print("I am printing items")
    # print (items)
    # exit()
    # for item in items:
    #     url = item.get_attribute("href")
    #     url_list.append(url)
    # print (url_list)

    return url_list

def main(path, output_dir, url_file, links_only):
    if not os.path.exists(path):
        print("ERROR: Invalid driver path given")
        return

    if url_file and not os.path.exists(url_file):
        print("ERROR: Invalid path for url file given")
        return

    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

    # set English as chromedriver's default language
    options = webdriver.ChromeOptions()
    options.add_argument('--lang=en')
    driver = webdriver.Chrome(executable_path = path, options=options)

    if not url_file or links_only:
        url_list = get_urls(driver)
        save_json("oculus_links", url_list)
        print("json object saved with urls")
    else:
        url_list = json.load(open(url_file, "r"))

    if not links_only:
        time.sleep(2)
        # extract data from the website
        test_extraction_python_org(driver, output_dir, url_list)

    driver.quit()

if __name__ == "__main__":
    parser = argparse.ArgumentParser("configure the driver & pass the URL of the oculus app store")
    parser.add_argument("path", help = "your driver's path", type = str)
    parser.add_argument("output_dir", help = "Output directory", type = str)
    parser.add_argument("-url_file", help = "Path to url list file", type = str)
    parser.add_argument("--links_only", help = "Only create a url list file", action="store_true", default=False)

    args = parser.parse_args()

    main(args.path, args.output_dir, args.url_file, args.links_only)

# https://stackoverflow.com/questions/72854116/selenium-attributeerror-webdriver-object-has-no-attribute-find-element-by-cs
# wd.find_element(By.CSS_SELECTOR, 'h1>span')
