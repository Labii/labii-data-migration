"""
Script to migrate OneNote entries into Labii as entries.
Imports OneNote pages, including scientific data and documentation, into Labii's entry system.
"""

import os
import sys
import re
import mimetypes
import urllib.parse
import requests
import msal
import time
from typing import Dict, List, Tuple, Optional
from bs4 import BeautifulSoup
from labii_sdk.sdk import LabiiObject
from migrate_file_as_entry import collect_labii_settings
from labii_sdk_core.sdk import print_yellow, print_blue, print_green, print_red, input_yellow, print_section

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
RESOURCE_PATTERN = re.compile(r"/onenote/resources/([^/]+)/(?:content|\$value)", re.IGNORECASE)
WAITING_TIME = 1  # seconds between Graph API calls to avoid throttling

def get_token(TENANT_ID, CLIENT_ID, SCOPES):
	authority = f"https://login.microsoftonline.com/{TENANT_ID}"
	app = msal.PublicClientApplication(CLIENT_ID, authority=authority)
	# Try cached token first
	accounts = app.get_accounts()
	if accounts:
		result = app.acquire_token_silent(SCOPES, account=accounts[0])
		if result and "access_token" in result:
			return result["access_token"]
	# Device code (interactive once in terminal)
	flow = app.initiate_device_flow(scopes=SCOPES)
	if "user_code" not in flow:
		print("Failed to create device flow:", flow, file=sys.stderr)
		sys.exit(1)
	print(f"\n=== Device code ===\nGo to: {flow['verification_uri']}\nCode: {flow['user_code']}\n")
	result = app.acquire_token_by_device_flow(flow)  # blocks until the user finishes auth
	if "access_token" not in result:
		print("Token acquisition failed:", result, file=sys.stderr)
		sys.exit(1)
	return result["access_token"]

def get_site_id(token: str, hostname: str, site_path: str) -> str:
	"""Resolve SharePoint site ID from hostname and site path."""
	url = f"{GRAPH_BASE}/sites/{hostname}:/sites/{site_path}"
	headers = {"Authorization": f"Bearer {token}"}
	time.sleep(WAITING_TIME)  # Be nice to the Graph API
	r = requests.get(url, headers=headers, timeout=30)
	if r.status_code != 200:
		raise RuntimeError(f"Failed to resolve site: {r.status_code} {r.text}")
	return r.json()["id"]

def list_site_notebooks(token: str, site_id: str) -> List[Dict]:
	"""List all OneNote notebooks under a SharePoint site."""
	url = f"{GRAPH_BASE}/sites/{site_id}/onenote/notebooks?$top=200"
	headers = {"Authorization": f"Bearer {token}"}
	out = []
	while url:
		time.sleep(WAITING_TIME)
		r = requests.get(url, headers=headers, timeout=60)
		if r.status_code != 200:
			raise RuntimeError(f"List notebooks failed: {r.status_code} {r.text}")
		data = r.json()
		out.extend(data.get("value", []))
		url = data.get("@odata.nextLink")
	return out

def parse_hostname_sitepath_from_weburl(web_url: str) -> Tuple[str, str]:
	"""Extract hostname and site path from SharePoint web URL."""
	u = urllib.parse.urlparse(web_url)
	hostname = u.netloc
	parts = u.path.split("/")
	if "sites" in parts:
		i = parts.index("sites")
		if i + 1 < len(parts):
			return hostname, parts[i + 1]
	raise ValueError("Could not derive SharePoint site path; please pass hostname and site_path manually")

def enumerate_all_sections(token: str, notebook_id: str, site_id: str) -> List[Dict]:
	"""Walk the notebook tree and return sections with their full path."""
	out: List[Dict] = []
	# Sections directly under the notebook
	root_sections = _get_all_pages(token, f"{GRAPH_BASE}/sites/{site_id}/onenote/notebooks/{notebook_id}/sections?$top=200")
	for s in root_sections:
		out.append({
			"id": s.get("id"),
			"displayName": s.get("displayName"),
			"path": s.get("displayName") or ""
		})
	# Recurse through section groups
	def walk_group(group: Dict, prefix: str):
		group_name = group.get("displayName") or ""
		current_prefix = f"{prefix}{group_name}".strip()
		# sections under this group
		for s in _get_all_pages(token, f"{GRAPH_BASE}/sites/{site_id}/onenote/sectionGroups/{group.get('id')}/sections?$top=200"):
			out.append({
				"id": s.get("id"),
				"displayName": s.get("displayName"),
				"path": f"{current_prefix} / {s.get('displayName')}".strip(" /")
			})
		# child section groups
		for child in _get_all_pages(token, f"{GRAPH_BASE}/sites/{site_id}/onenote/sectionGroups/{group.get('id')}/sectionGroups?$top=200"):
			walk_group(child, f"{current_prefix} / " if current_prefix else "")
	for g in _get_all_pages(token, f"{GRAPH_BASE}/sites/{site_id}/onenote/notebooks/{notebook_id}/sectionGroups?$top=200"):
		walk_group(g, "")
	# De-dup
	seen = set()
	unique = []
	for item in out:
		key = item["id"]
		if key not in seen:
			seen.add(key)
			unique.append(item)
	return unique

def _get_all_pages(token: str, url: str, params: Optional[Dict[str, str]] = None) -> List[Dict]:
	"""
	Follow @odata.nextLink and return flattened value list.
	Adds retry handling for throttling/transient errors and uses odata.maxpagesize.
	"""
	headers = {
		"Authorization": f"Bearer {token}",
		"Accept": "application/json",
		# Ask the server to give us up to 100 items per page while still emitting nextLink.
		"Prefer": "odata.maxpagesize=100",
	}
	items: List[Dict] = []
	next_url = url
	next_params = params  # params only for the very first call
	while next_url:
		for attempt in range(5):
			time.sleep(WAITING_TIME)  # Be nice to the Graph API
			resp = requests.get(next_url, headers=headers, params=next_params, timeout=60)
			# After first request, ALWAYS let nextLink control the query string
			next_params = None
			if resp.status_code == 200:
				data = resp.json()
				items.extend(data.get("value", []))
				next_url = data.get("@odata.nextLink")
				break  # success; continue outer while
			elif resp.status_code in (429, 503, 502, 500):
				# Respect Retry-After when present; otherwise exponential backoff
				retry_after = resp.headers.get("Retry-After")
				delay = int(retry_after) if retry_after and retry_after.isdigit() else (2 ** attempt)
				time.sleep(min(delay, 30))
				continue
			else:
				raise RuntimeError(f"Graph GET failed {resp.status_code}: {resp.text}")
	return items

def list_pages_in_section_site(token: str, site_id: str, section_id: str) -> List[Dict]:
	"""
	List all pages for a section under a SharePoint site-hosted notebook,
	reliably following @odata.nextLink and using a sane page size.
	"""
	select = "id,title,createdDateTime,lastModifiedDateTime,links"
	order = "order asc"
	# Build only the FIRST request with params; the nextLink must be used verbatim.
	url = f"{GRAPH_BASE}/sites/{site_id}/onenote/sections/{section_id}/pages"
	params = {
		"$select": select,
		"$orderby": order,
		# Do NOT set $top for OneNote pages; prefer odata.maxpagesize instead to avoid nextLink bugs.
		# "$top": "100",
		# Optional: include page hierarchy info if you care about indentation/order within the section
		# "pagelevel": "true",
	}
	return _get_all_pages(token, url, params=params)

def get_page_html(token: str, site_id: str, page_id: str) -> bytes:
	"""Get raw HTML bytes for a OneNote page."""
	time.sleep(WAITING_TIME)  # Be nice to the Graph API
	url = f"{GRAPH_BASE}/sites/{site_id}/onenote/pages/{page_id}/content?includeIDs=true"
	r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=120)
	if r.status_code != 200:
		raise RuntimeError(f"Get page HTML failed {r.status_code}: {r.text[:400]}")
	return r.content

def extract_resource_urls(page_html: bytes) -> List[Dict[str, str]]:
	"""Parse OneNote HTML and collect possible resource URLs with file types and alt text."""
	soup = BeautifulSoup(page_html, "html.parser")
	url_info = {}
	for img in soup.find_all("img"):
		for attr in ("src", "data-src", "data-fullres-src"):
			v = img.get(attr)
			if v:
				file_type = img.get("data-src-type", "")
				alt_text = img.get("alt", "")
				url_info[v] = {"file_type": file_type, "alt_text": alt_text}
				break
	for obj in soup.find_all("object"):
		v = obj.get("data")
		if v:
			file_type = obj.get("type", "")
			alt_text = obj.get("data-attachment", "")
			url_info[v] = {"file_type": file_type, "alt_text": alt_text}
	for a in soup.find_all("a"):
		v = a.get("href")
		if v:
			file_type = a.get("data-src-type", "")
			alt_text = a.get("alt", "")
			url_info[v] = {"file_type": file_type, "alt_text": alt_text}
	filtered = [
		{"url": u, "file_type": url_info[u]["file_type"], "alt_text": url_info[u]["alt_text"]} 
		for u in url_info.keys()
		if "/onenote/resources/" in u and (u.endswith("/content") or u.endswith("/$value"))
	]
	return sorted(filtered, key=lambda x: x["url"])

def parse_resource_id(resource_url: str) -> str:
	"""Extract the resource-id from .../onenote/resources/{id}/content URL."""
	m = RESOURCE_PATTERN.search(resource_url)
	if not m:
		raise ValueError(f"Could not parse resource id from: {resource_url}")
	return m.group(1)

def download_resource(token: str, site_id: str, resource_id: str) -> Tuple[bytes, Dict[str, str]]:
	"""Download resource content from OneNote."""
	url = f"{GRAPH_BASE}/sites/{site_id}/onenote/resources/{resource_id}/content"
	time.sleep(WAITING_TIME)  # Be nice to the Graph API
	r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=180)
	if r.status_code != 200:
		raise RuntimeError(f"Download resource {resource_id} failed {r.status_code}: {r.text[:400]}")
	return r.content, r.headers

def clean_filename(alt_text: str) -> str:
	"""Extract a clean filename from alt text by removing newlines and extra content."""
	if not alt_text:
		return ""
	# Split by newlines and take the first meaningful line
	lines = alt_text.split('\n')
	for line in lines:
		line = line.strip()
		# Skip empty lines or lines that look like just numbers/timestamps
		if line and not line.replace(':', '').replace('.', '').replace(' ', '').isdigit():
			# Take only the first part if it looks like a title
			# Remove common separators and take the first meaningful part
			if any(sep in line for sep in ['(', ':', '\t']):
				# Extract text before common separators
				for sep in ['(', ':', '\t']:
					if sep in line:
						line = line.split(sep)[0].strip()
						break
			# Clean up the filename - remove invalid characters
			cleaned = re.sub(r'[<>:"/\\|?*\n\r\t]', ' ', line)
			cleaned = re.sub(r'\s+', ' ', cleaned).strip()
			
			if cleaned and len(cleaned) > 1:
				return cleaned
	return ""

def pick_filename(resource_id: str, headers: Dict[str, str], fallback_ext: str = "", file_type: str = "", alt_text: str = "", page_name: str = "", file_counter: int = 1) -> str:
	"""Choose a filename using Content-Disposition, alt text, page name, or fallback options."""
	cd = headers.get("Content-Disposition") or headers.get("content-disposition")
	ct = headers.get("Content-Type") or headers.get("content-type")
	# If we have a filename from Content-Disposition, use it
	if cd and "filename=" in cd:
		fn = cd.split("filename=")[-1].strip().strip('"; ')
		if fn:
			return fn
	# Determine extension from file_type, Content-Type, or fallback
	ext = ""
	if file_type:
		# Check if file_type is a MIME type (contains '/')
		if "/" in file_type:
			# Use mimetypes to get the correct extension from MIME type
			ext = mimetypes.guess_extension(file_type.split(";")[0].strip()) or ""
		else:
			# Use file_type as extension (add dot if not present)
			ext = f".{file_type}" if not file_type.startswith(".") else file_type
	elif ct:
		# Guess extension from Content-Type
		ext = mimetypes.guess_extension(ct.split(";")[0].strip()) or ""
	else:
		ext = fallback_ext or ""
	# Try to get a meaningful filename from alt text
	filename = clean_name(clean_filename(alt_text))
	if filename:
		if filename in ["Image", "Selected photo"]:
			filename = f"{clean_name(clean_filename(page_name))} {filename} {file_counter}"
		# Check if filename already has an extension
		if '.' in filename and len(filename.split('.')[-1]) <= 4:
			# Filename already has extension, use as is
			return filename
		else:
			# Add extension to filename
			return f"{filename}{ext}"
	# Fallback to page name + file counter
	if page_name:
		clean_page_name = clean_name(clean_filename(page_name)) or "file"
		return f"{clean_page_name} file {file_counter}{ext}"
	# Final fallback to resource ID
	return f"{resource_id}{ext}"

def clean_name(title: str) -> str:
	"""Clean the name by removing invalid characters."""
	if not title:
		return title
	# Replace invalid characters with spaces
	for item in ["&", "<", ">", "/", "\\", ":", "\"", "|", "?", "*"]:
		title = title.replace(item, " ")
	# Remove extra whitespace
	title = re.sub(r'\s+', ' ', title).strip()
	return title

def process_page_resources(page_html: bytes, resource_info: List[Dict[str, str]], access_token: str, site_id: str, labii, settings, page_name: str = "") -> str:
	"""Download resources, upload to Labii, and replace resource URLs in HTML."""
	soup = BeautifulSoup(page_html, "html.parser")
	file_counter = 1
	for info in resource_info:
		time.sleep(1)  # Be nice to the Graph API
		url = info["url"]
		file_type = info["file_type"]
		alt_text = info["alt_text"]
		try:
			rid = parse_resource_id(url)
			blob, headers = download_resource(access_token, site_id, rid)
			fname = pick_filename(rid, headers, file_type=file_type, alt_text=alt_text, page_name=page_name, file_counter=file_counter)
			fpath = os.path.join("./tmp/", fname)
			with open(fpath, "wb") as fh:
				fh.write(blob)
			file_counter += 1
			# Upload file to Labii
			response_file = labii.Record.list(query=f"table__sid={settings['labii_table_file_sid']}&name={fname}", serializer="version")
			if response_file["count"] > 0:
				response_file = response_file["results"][0]
				print_blue(f"File already exists in Labii: {response_file['name']} ({file_counter}/{len(resource_info)})")
			else:
				response_file = labii.upload(fpath, [{"sid": settings["labii_project_sid"]}])
				response_file["name"] = f"{response_file['uid']}: {response_file['name']}"
				print_blue(f"Uploaded file to Labii: {response_file['name']} ({file_counter}/{len(resource_info)})")
			# Replace resource URL in HTML
			for tag in soup.find_all(src=url):
				new_tag = soup.new_tag("section")
				new_tag["class"] = "labii-file"
				new_tag["sid"] = response_file["sid"]
				new_tag["name"] = response_file["name"]
				new_tag["version"] = response_file["version"]["sid"]
				new_tag["should_hide_preview"] = "false"
				tag.replace_with(new_tag)
			for tag in soup.find_all(**{"data-fullres-src": url}):
				new_tag = soup.new_tag("section")
				new_tag["class"] = "labii-file"
				new_tag["sid"] = response_file["sid"]
				new_tag["name"] = response_file["name"]
				new_tag["version"] = response_file["version"]["sid"]
				new_tag["should_hide_preview"] = "false"
				tag.replace_with(new_tag)
			for tag in soup.find_all(**{"data-src": url}):
				new_tag = soup.new_tag("section")
				new_tag["class"] = "labii-file"
				new_tag["sid"] = response_file["sid"]
				new_tag["name"] = response_file["name"]
				new_tag["version"] = response_file["version"]["sid"]
				new_tag["should_hide_preview"] = "false"
				tag.replace_with(new_tag)
			for tag in soup.find_all(data=url):
				new_tag = soup.new_tag("section")
				new_tag["class"] = "labii-file"
				new_tag["sid"] = response_file["sid"]
				new_tag["name"] = response_file["name"]
				new_tag["version"] = response_file["version"]["sid"]
				new_tag["should_hide_preview"] = "false"
				tag.replace_with(new_tag)
			for tag in soup.find_all(href=url):
				new_tag = soup.new_tag("section")
				new_tag["class"] = "labii-file"
				new_tag["sid"] = response_file["sid"]
				new_tag["name"] = response_file["name"]
				new_tag["version"] = response_file["version"]["sid"]
				new_tag["should_hide_preview"] = "false"
				tag.replace_with(new_tag)
		except Exception as e:
			print(f"Error processing resource {url}: {e}")
	return str(soup)

def process_section(section, settings, access_token, site_id, labii):
	"""Process all pages in a section and migrate them to Labii."""
	print_section(f" - {section.get('displayName')} (id: {section.get('id')})")
	pages = list_pages_in_section_site(access_token, site_id, section.get("id"))
	print(f"Found {len(pages)} pages in section {section.get('id')}:")
	index = 0
	for p in pages:
		index += 1
		print_section(f"{p.get('title')} | {index}/{len(pages)}")
		should_pass = False
		# clean the title to be used as entry name
		page_name = clean_name(p.get("title"))
		# Check if record exists
		response_record = labii.Record.list(query=f"table__sid={settings['labii_table_entry_sid']}&name={page_name}", serializer="name")
		if "count" in response_record and response_record["count"] == 0:
			# Create entry
			response_record = labii.Record.create(
				{
					"name": page_name,
					"projects": [{"sid": settings["labii_project_sid"]}],
					settings["labii_column_section_sid"]: section.get("displayName"),
					settings["labii_column_datetime_sid"]: {
						"date": p.get("lastModifiedDateTime").split("T")[0],
						"time": p.get("lastModifiedDateTime").split("T")[1].split("Z")[0]
					},
					settings["labii_column_url_sid"]: {
						"text": "Open in OneNote",
						"link": p.get("links", {}).get("oneNoteWebUrl", {}).get("href", "")
					}
				},
				query=f"table__sid={settings['labii_table_entry_sid']}"
			)
			if "uid" in response_record:
				print_yellow(f"Created entry {response_record['uid']}: {response_record['name']}")
			else:
				print_red(response_record)
		elif "count" in response_record and response_record["count"] > 0:
			response_record = response_record["results"][0]
			print_yellow(f"Entry already exists: {response_record['name']}")
			uid = response_record["name"].split(":")[0]
			if uid != "ONE380":
				should_pass = True
		else:
			print_red(response_record)
			sys.exit(1)
		if should_pass is False:
			# Get page content
			page_html = get_page_html(access_token, site_id, p.get("id"))
			# Find resources
			resource_info = extract_resource_urls(page_html)
			# Prepare tmp folder
			if os.path.isdir("./tmp/"):
				os.system("rm -rf ./tmp/*")
			else:
				os.system("mkdir -p ./tmp/")
			# Download/upload resources and update HTML
			#print(page_html)
			page_html = process_page_resources(page_html, resource_info, access_token, site_id, labii, settings, page_name=p.get("title", ""))
			# print(page_html)
			# Update Labii section with new HTML
			response_section = labii.Section.list(query=f"row__sid={response_record['sid']}&name=Notes")
			# extract the body of the html
			page_html = BeautifulSoup(page_html, "html.parser").body.decode_contents()
			if response_section["count"] > 0:
				response_section = response_section["results"][0]
				response = labii.Section.modify(
					sid=response_section["sid"],
					data={"data": {"html": page_html}}
				)
				# print(response)
				# print(page_html)
			else:
				print_red(response_section)
			# break  # For testing, process only one page per section

def main():
	"""Main migration logic."""
	print("Please install the eln_onenote table in your Labii account first.")
	# Collect settings
	settings = collect_labii_settings()
	settings["labii_column_section_sid"] = input_yellow("Provide the SID of the column section from the eln_onenote table. ")
	settings["labii_column_datetime_sid"] = input_yellow("Provide the SID of the column datetime from the eln_onenote table. ")
	settings["TENANT_ID"] = input_yellow("Provide the TENANT_ID of your Azure AD organization. ")
	settings["CLIENT_ID"] = input_yellow("Provide the CLIENT_ID of your Azure AD application. ")
	# settings["SCOPES"] = ["Notes.Read.All", "Files.Read.All", "Sites.Read.All"]
	settings["SCOPES"] = ["Notes.Read.All"]
	settings["SITE_URL"] = input_yellow("Provide the SITE_URL of your OneNote site. ")
	settings["NOTEBOOK"] = input_yellow("Provide the name of the OneNote notebook to be imported. ")
	settings["SECTIONS"] = input_yellow("Provide the name of the OneNote sections to be imported (comma-separated). Leave it empty to import all sections. ")
	debug = True
	if debug:
		# Debug settings
		settings["labii_base_url"] = "https://www.labii.dev"
		settings["LABII_API_KEY"] = "xxx"
		settings["labii_organization_sid"] = "xxx"
		settings["labii_project_sid"] = "xxx"
		settings["labii_table_entry_sid"] = "xxx"
		settings["labii_table_file_sid"] = "xxx"
		settings["labii_column_section_sid"] = "xxx"
		settings["labii_column_datetime_sid"] = "xxx"
		settings["labii_column_url_sid"] = "xxx"
		settings["TENANT_ID"] = "xxx"
		settings["CLIENT_ID"] = "xxx"
		settings["SITE_URL"] = "xxx"
		settings["NOTEBOOK"] = "xxx"
		settings["SECTIONS"] = ""
	settings["SECTIONS"] = [s.strip() for s in settings["SECTIONS"].split(",") if s.strip()]
	print(settings)
	settings["confirm"] = input_yellow("Enter to confirm the provide settings is correct. ")
	# Init Labii SDK
	labii = LabiiObject(
		base_url=settings["labii_base_url"],
		organization__sid=settings["labii_organization_sid"],
		api_key=settings.get("LABII_API_KEY", "")
	)
	# Use get access_token
	if "access_token" in settings and len(settings["access_token"]) > 0:
		access_token = settings["access_token"]
	else:
		access_token = get_token(settings["TENANT_ID"], settings["CLIENT_ID"], settings["SCOPES"])
		print(access_token)
	# Resolve site and notebook
	hostname, site_path = parse_hostname_sitepath_from_weburl(settings["SITE_URL"])
	site_id = get_site_id(access_token, hostname, site_path)
	print(f"\nResolved site id: {site_id}")
	notebooks = list_site_notebooks(access_token, site_id)
	notebook_id = None
	for nb in notebooks:
		if nb.get("displayName") == settings["NOTEBOOK"]:
			notebook_id = nb.get("id")
			break
	if not notebook_id:
		raise ValueError(f"Could not find notebook named {settings['NOTEBOOK']} on site {settings['SITE_URL']}")
	print(f"Found notebook id: {notebook_id}")
	# List sections in the notebook
	sections = enumerate_all_sections(access_token, notebook_id, site_id)
	print(f"Found {len(sections)} sections:")
	for section in sections:
		if len(settings["SECTIONS"]) == 0 or section.get("displayName") in settings["SECTIONS"]:
			process_section(section, settings, access_token, site_id, labii)

if __name__ == "__main__":
	main()
