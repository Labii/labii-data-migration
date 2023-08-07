"""
The `migrate_benchling_entries.py` function serves as a script to facilitate the seamless migration of data from Benchling to Labii. Specifically, it is designed to import Benchling entries, which encompass various forms of scientific data and documentation, into Labii's entry system.
"""
import os
import shlex
import glob
import sys
import datetime
from bs4 import BeautifulSoup
from labii_sdk.sdk import LabiiObject
from migrate_file_as_entry import collect_labii_settings

def update_day_separator(soup):
	""" update the day separator with labii day """
	# Find all <div> tags with class "daySeparator"
	day_separator_divs = soup.find_all('div', class_='daySeparator')
	# Define the replacement HTML
	replacement_html = '<div class="labii-day"><span class="labii-day-label">{date}</span></div>'
	# Loop through the found <div> tags and replace them
	for day_div in day_separator_divs:
		date_span = day_div.find('span', class_='daySeparator-date')
		if date_span:
			date = date_span.text.strip()
			parsed_date = datetime.datetime.strptime(date, "%A, %m/%d/%Y")
			formatted_date = parsed_date.strftime("%A, %Y-%m-%d")
			# Create the replacement HTML with the modified date
			replacement = replacement_html.format(date=formatted_date)
			# Replace the current <div> with the replacement HTML
			day_div.replace_with(BeautifulSoup(replacement, 'html.parser'))
	return soup

def update_text_item(soup):
	""" update the text item with p """
	# Find all text <div>
	text_divs = soup.find_all('div', class_='mediocre-item is-text')
	# Define the replacement HTML
	replacement_html = '<p>{text}</p>'
	# Loop through the found <div> tags and replace them
	for text_div in text_divs:
		text = text_div.text.strip()
		# Create the replacement HTML with the modified date
		replacement = replacement_html.format(text=text)
		# Replace the current <div> with the replacement HTML
		text_div.replace_with(BeautifulSoup(replacement, 'html.parser'))
	return soup

def update_code_item(soup):
	""" update the text item with p """
	# Find all text <div>
	text_divs = soup.find_all('div', class_='mediocre-item is-code')
	# Define the replacement HTML
	replacement_html = '<pre data-language="Plain text" spellcheck="false" xpath="1"><code class="language-plaintext">{text}</code></pre>'
	# Loop through the found <div> tags and replace them
	for text_div in text_divs:
		text = text_div.text.strip()
		# Create the replacement HTML with the modified date
		replacement = replacement_html.format(text=text)
		# Replace the current <div> with the replacement HTML
		text_div.replace_with(BeautifulSoup(replacement, 'html.parser'))
	return soup

def update_file(soup, labii, current_file, settings):
	""" update the file with labii file """
	# Find all <div> tags with class "daySeparator"
	file_divs = soup.find_all('div', class_='mediocre-item')
	# Define the replacement HTML
	replacement_html = '<section class="labii-file" sid="{file_sid}" name="{file_name}" version="{version_sid}" should_hide_preview="false"></section>'
	# Loop through the found <div> tags and replace them
	name_index = {} # incase the same name used multiple times
	for file_div in file_divs:
		name_div = file_div.find('div', class_='note-itemName')
		if name_div:
			file_name = name_div.text.strip()
			# update name index
			if not file_name in name_index:
				name_index[file_name] = 1
			else:
				name_index[file_name] += 1
			# upload file
			file_path = current_file.replace(".html", f" {file_name}")
			name_parts = os.path.splitext(file_name)
			if name_index[file_name] > 1:
				file_path = current_file.replace(".html", f" {name_parts[0]} {name_index[file_name]}{name_parts[1]}")
			if os.path.exists(file_path):
				file_record = labii.upload(file_path, [{"sid": settings["labii_project_sid"]}])
				# Create the replacement HTML with the modified date
				replacement = replacement_html.format(file_sid=file_record['sid'], file_name=f"{file_record['uid']}: {file_record['name']}", version_sid=file_record['version']['sid'])
				# Replace the current <div> with the replacement HTML
				file_div.replace_with(BeautifulSoup(replacement, 'html.parser'))
			else:
				print(f"Error: File ({file_path}) not exists!")
				sys.exit()
	return soup

def update_td_content(soup):
	""" benchling table headers disable the same value twice, use this function to only keep one version """
	# Find all <td> tags
	td_tags = soup.find_all('td')
	# Loop through the <td> tags
	for td in td_tags:#pylint: disable=invalid-name
		# find the label wrapper
		wrapper_div = td.find('div', class_='mediocre-tableEditable-axisCell-labelWrapper')
		if wrapper_div:
			# Find the first element inside the <td> tag
			first_element = wrapper_div.find(True, recursive=False)
			if first_element:
				# Replace the inner HTML of the <td> tag with the text from the first element
				td.string = first_element.get_text()
	return soup

def remove_style_tags(soup):
	""" remove the inline style tags """
	style_tags = soup.find_all('style')
	for style_tag in style_tags:
		style_tag.extract()
	return soup

def remove_table_wrapper_div(soup):
	""" for each table, benchling comes with a table wrapper """
	wrappers = soup.find_all('div', class_='mediocre-tableEditable-fillerTableWrapper')
	for tag in wrappers:
		tag.extract()
	return soup

def remove_empty_table_tr(soup):
	""" some of table contains a lot of empty rows, these need to be removed to save space """
	rows = soup.find_all('tr')
	total_rows = len(rows)
	if total_rows > 500:# only delete big tables
		for row in rows:
			should_delete = True
			cells = row.find_all('td')[1:]
			for cell in cells:
				if any(cell.stripped_strings):
					should_delete = False
					break
			if should_delete:
				row.extract()
		rows = soup.find_all('tr')
		deleted_rows = total_rows - len(rows)
		if deleted_rows > 0:
			print(f"Deleted rows {deleted_rows}")
	return soup

def main():
	""" import benchling entry to labii entry """
	# collect the settings
	settings = collect_labii_settings()
	settings["folder_path"] = input("Provide the full path of folder that contains the files to be uploaed. ")
	debug = True
	if debug:
		settings["labii_base_url"] = "http://127.0.0.1:8000"
		settings["labii_organization_sid"] = "TWZ30a40x24bcV16afkpu"
		settings["labii_project_sid"] = "HKNQ0a40x271cJOTY49di"
		settings["labii_table_entry_sid"] = "69be0a40xfff68chmrwBG"
		settings["labii_table_file_sid"] = "58ad0a40xfff57bglqvAF"
		settings["folder_path"] = "xxx"
	settings["folder_path"] = settings["folder_path"].rstrip("/")
	settings["folder_path_escape"] = shlex.quote(settings["folder_path"])
	print(settings)
	settings["confirm"] = input("Enter to confirm the provide settings is correct. ")
	# init the labii sdk
	labii = LabiiObject(
		base_url=settings["labii_base_url"],
		organization__sid=settings["labii_organization_sid"]
	)
	labii.api.login()
	# collect the files
	files = glob.glob(f"{settings['folder_path']}/*.html")
	# create a migrated folder
	if not os.path.isdir(f"{settings['folder_path']}/migrated/"):
		os.system(f"mkdir -p {settings['folder_path_escape']}/migrated/")
	# process the files
	index = 1
	for current_file in files:
		print(f"{index}/{len(files)}...")
		index += 1
		if not "/migrated" in current_file and "etr_" in current_file:
			file_name = os.path.basename(current_file)
			print(f"Processing {file_name}...")
			# read the content
			with open(current_file, 'r', encoding='utf-8') as file:
				html_content = file.read()
			soup = BeautifulSoup(html_content, 'html.parser')
			# update the date
			soup = update_day_separator(soup)
			# update the text
			soup = update_text_item(soup)
			# update the code
			soup = update_code_item(soup)
			# update the file
			soup = update_file(soup, labii, current_file, settings)
			# update the td content
			soup = update_td_content(soup)
			# rm the style tag
			soup = remove_style_tags(soup)
			# rm table wrappers
			soup = remove_table_wrapper_div(soup)
			# rm the empty table row
			soup = remove_empty_table_tr(soup)
			# create entry
			body_tag = soup.find('body')
			body_html = str(body_tag)
			entry_name = os.path.splitext(file_name)[0]
			# create entry
			response = labii.Record.create(
				{
					"name": entry_name,
					"projects": [{"sid": settings["labii_project_sid"]}],
					"data": body_html
				},
				query=f"table__sid={settings['labii_table_entry_sid']}"
			)
			if "uid" in response:
				print(f"{response['uid']}: {response['name']}")
			else:
				print(response)
			current_file_escape = shlex.quote(current_file).replace(".html", "")
			os.system(f'mv {current_file_escape}* {settings["folder_path"]}/migrated/')

if __name__ == "__main__":
	main()
