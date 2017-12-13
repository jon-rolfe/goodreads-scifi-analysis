#!/usr/bin/env python
# coding=utf-8

"""
Usage TBD.

hey, don't actually commit the following:
TODO: hey, analysis -- Non-negative matrix factorization?
(github.com/duhaime/nmf)
LDA: pip install lda
scikit-learn
coreNLP
"""

import random
import re
import signal
import sys
import time

import unicodedata
from langdetect import detect

from database import *

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(levelname)s: %(message)s')  # TODO: file logging
logger = logging.getLogger('__name__')


# # set paths for selenium and a shared browser
# browser_driver_path = '{}\geckodriver.exe'.format(sys.path[0])
#
# try:
#     # default: try to use Windows exe
#     browser = webdriver.Firefox(executable_path=browser_driver_path)
#
# # TODO: narrow the scope of the except statements (it's good form)
# except:
#     # if the exe doesn't work, strip that part off and try again (e.g. for macOS)
#     try:
#         browser_driver_path = browser_driver_path[:4]
#         browser = webdriver.Firefox(executable_path=browser_driver_path)
#     except:
#         logger.error(
#             'Could not initialize Firefox. Is Firefox installed and the geckodriver in the same directory as the script?')


# TODO: move main function to a different file, searcher + db to subfolder
def main():
    """Goodreads searcher main script. Execution logic flow director."""

    # init_database()

    # search_scraper()

    # review_scraper()

    text_cleaning()


def search_scraper():
    """Scrapes books from a goodreads search and sends them to be added to the DB"""

    # initiate search; get starting locations
    search_term = 'science-fiction'
    browser.get('https://www.goodreads.com/search?q={}&search_type=books&search%5Bfield%5D=genre'.format(search_term))

    # xpath definitions
    book_root_location = '/html/body/div[1]/div[2]/div[1]/div[1]/div[2]/table/tbody/tr[{}]/'
    book_title_location = book_root_location + 'td[1]/a'
    book_url_location = book_root_location + 'td[1]/a'
    book_author_location = book_root_location + 'td[2]/span[2]/a'
    book_publish_year_location = book_root_location + 'td[2]/span[3]'

    page = 1
    # iterate through first 100 search pages (GR will not display past p 100)
    while page < 101:

        # iterate through each book on the page
        book_on_page = 1
        while book_on_page < 21:
            book_title = browser.find_element_by_xpath(book_title_location.format(book_on_page)).get_attribute(
                'title').encode('ascii', 'ignore')
            book_url = browser.find_element_by_xpath(
                book_url_location.format(book_on_page)).get_attribute('href').encode('ascii', 'ignore')
            book_author = browser.find_element_by_xpath(book_author_location.format(book_on_page)).text.encode('ascii',
                                                                                                               'ignore')
            try:  # every once in a while, goodreads doesn't list the publish date in search
                book_publish_year = int(
                    browser.find_element_by_xpath(book_publish_year_location.format(book_on_page)).text.split(
                        'published ', 1)[1][:4].encode('ascii', 'ignore'))
            except IndexError:
                logger.error('No publish year listed for {} - please fill manually in DB'.format(book_title))
                book_publish_year = '0'  # (dummy value for when no date listed)

            logger.debug('title: {}'.format(book_title))
            logger.debug('author: {}'.format(book_author))
            logger.debug('publish year: {}'.format(book_publish_year))
            logger.debug('url: {}'.format(book_url))

            # add to DB
            add_book(book_title, book_author, book_publish_year, book_url)
            logger.info('ADDED: {}'.format(book_title))  # TODO: only display this if it's a unique entry

            book_on_page += 1

        # have it click "next" rather than iterate the page field of URL to make it vaguely less obviously a crawler
        browser.find_element_by_class_name('next_page').click()
        page += 1


def review_scraper():
    """Using the preexisting book_list database, scape reviews."""

    book_number = 2510

    while book_number < book_list_size():

        book_to_scrape = call_book(book_number)
        logger.debug('scraping reviews for: {}'.format(book_to_scrape[2]))

        browser.get(book_to_scrape[1])

        total_book_review_count = 0
        page_number = 0

        # get up to 10 pages of reviews (a couple hundred per book)
        while total_book_review_count < 100 and page_number < 10:  # TODO: CLEAN UP THIS CODE!
            # reset review count per book
            reviews = browser.find_elements_by_css_selector(".reviewText [style='display:none']")
            logger.debug('{} reviews'.format(len(reviews)))
            review_count = 0
            while review_count < len(reviews):
                try:
                    review_text = reviews[review_count].get_attribute("textContent")
                    lang_detect = detect(review_text)
                    if lang_detect == 'en':
                        add_review(book_number, review_text, False)
                        total_book_review_count += 1

                except:
                    logger.info('faulty review: #{} on {}'.format(review_count, book_to_scrape[2]))

                review_count += 1

            try:
                browser.find_element_by_css_selector(".next_page").click()
            except:
                # if there's no next button, continue to next book
                break

            # sleep to let the next page of reviews load. (randomness added for anti-anti-scraping)
            time.sleep(3 + (random.random() * 2))
            page_number += 1

        book_number += 1


def text_cleaning():
    """Our raw data has issues that impacts NLP and must be cleaned. THIS FUNCTION IS VERY REDUNDANT FOR CLARITY"""

    review_id = 1
    target_review = call_review(review_id, False)
    review_book_id = target_review[1]
    review_text = target_review[2]

    # Unicode will play merry hell with cleaning/NLP processing, so normalize then encode as ASCII.
    # Source data should be in English, so this shouldn't introduce bias into analysis.
    review_text = unicodedata.normalize('NFKD', review_text).encode('ascii', 'ignore')

    # strip links and * characters using regex
    review_text = re.sub(r'(http\S+|\*)', '', review_text)
    # add a space after digits/break characters - random whitespace didn't make it from the scraper.
    review_text = re.sub(r'(\d\D|[\.!\?/\\;:])', '\g<1> ', review_text)
    # strip extra whitespaces
    review_text = re.sub(r'\s\s+', ' ', review_text)

    add_review(review_book_id, review_text, True, review_id)

def close(*args):
    """Handles sigint/unexpected program exit"""
    sys.exit(1)


if __name__ == "__main__":
    # make a SIGINT handler for ctrl-c, etc
    signal.signal(signal.SIGINT, close)
    # call main
    main()
