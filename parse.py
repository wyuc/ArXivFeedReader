import feedparser
import pytz
from datetime import datetime
from bs4 import BeautifulSoup
from mongo import arxiv_db
import html
import re
import time
from tqdm import tqdm
import schedule
import logging
from requests.exceptions import RequestException

def clean_html(html_content):
	"""Remove HTML tags and return plain text."""
	soup = BeautifulSoup(html_content, "html.parser")
	return html.unescape(soup.get_text())


def clean_entry(feed_entry):
	cleaned_entry = dict()
	cleaned_entry["title"] = clean_html(feed_entry.title)
	cleaned_entry['authors'] = clean_html(feed_entry.author_detail["name"])
	summary_header, abstract = feed_entry.summary.split("\n")[0], "\n".join(feed_entry.summary.split("\n")[1:])
	cleaned_entry['abstract'] = abstract
	cleaned_entry["link"] = feed_entry.link
	cleaned_entry["tag"] = [tag["term"] for tag in feed_entry.tags]
	cleaned_entry["id"] = feed_entry.id.split("arXiv.org:")[-1]
	cleaned_entry["status"] = summary_header.split("Announce Type: ")[-1].strip()
	# feed_entry["title"], feed_entry["tag"] = convert_title_string(feed_entry.title)
	# del feed_entry["summary_detail"], feed_entry["links"], feed_entry["title_detail"], feed_entry["author_detail"], feed_entry["authors"]
	return cleaned_entry

def convert_data(source_data):
	target_data = {}
	
	target_data['link'] = source_data['link']
	target_data['abstract'] = source_data['abstract']
	target_data['authors'] = source_data['authors']
	
	# Convert the tags into the desired format
	for tag in source_data['tag']:
		target_data[tag] = True
	# target_data['cs'] = {source_data['tag']: True}
	
	# Convert the time.struct_time into the desired string format
	updated_date = time.strftime('%a, %d %b %Y %H:%M:%S GMT', source_data['date'])
	target_data['date'] = updated_date
	
	email_date = time.strftime('%Y-%m-%d', source_data['email_date'])
	target_data['email_date'] = email_date
	
	# Transform the id into the desired format
	arxiv_id = source_data['id']
	target_data['id'] = f"arXiv:{arxiv_id}"
	
	target_data['title'] = source_data['title']
	
	return target_data


# Parse the RSS feed
rss_feed_urls = ['https://rss.arxiv.org/rss/cs.CL']
def parse():
	logging.info("Parsing RSS feeds...")
	for rss_feed_url in rss_feed_urls:
		retry_count = 0
		max_retries = 10
		while retry_count < max_retries:
			try:
				feed = feedparser.parse(rss_feed_url)
				if feed.entries:
					break
				logging.warning(f"Feed is empty. Retry {retry_count + 1} of {max_retries}...")
				time.sleep(60)
				retry_count += 1
			except RequestException as e:
				logging.error(f"Network error occurred: {e}. Retry {retry_count + 1} of {max_retries}...")
				time.sleep(60)
				retry_count += 1

		if retry_count == max_retries:
			logging.error(f"Failed to fetch feed after {max_retries} attempts. Skipping this URL.")
			continue

		updated_parsed = feed.feed.get('updated_parsed')
		if updated_parsed is None:
			# Fallback to current time if 'updated_parsed' is not available
			updated_parsed = datetime.now().timetuple()
		for entry in tqdm(feed.entries):
			try:
				entry = clean_entry(entry)
				entry["date"] = updated_parsed
				entry["email_date"] = updated_parsed
				entry = convert_data(entry)
				entry["ParserVer"] = "2.1"
				
				# Use update_one with $setOnInsert to avoid changing existing fields
				arxiv_db.update_one(
					{"id": entry["id"]},
					{"$setOnInsert": entry},
					upsert=True
				)
			except Exception as e:
				print(e)

def job():
	try:
		parse()
	except Exception as e:
		logging.exception(f"Error occurred during parsing: {e}")

def is_weekday():
	return datetime.now(pytz.timezone('US/Eastern')).weekday() < 5

def run_schedule():
	while True:
		schedule.run_pending()
		time.sleep(1)

if __name__ == "__main__":
	logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
	
	# Schedule the job to run at NST +10 minutes on weekdays
	job_schedule = schedule.every().day.at("13:10").do(job)
	if is_weekday():
		job_schedule

	# Run the scheduled job
	run_schedule()
