"""
The "migrate_file_as_entry.py" function is a versatile data import utility designed to streamline the process of importing files into a research data management system. With a user-friendly interface, this function allows users to effortlessly import each file as a separate experiment entry, ensuring seamless organization and retrieval of research data. The function intelligently extracts the file name and uses it as the experiment name, providing clear and descriptive titles for each entry. Additionally, the imported file is automatically treated as an attachment to the respective entry, eliminating the need for separate handling or linking. This efficient and time-saving feature enables researchers to efficiently manage and access their data, promoting a more productive and organized research workflow.
"""
import os
import glob
import datetime
from labii_sdk.sdk import LabiiObject

def main():
	""" import benchling entry to labii entry """
	# collect the settings
	settings = {}
	settings["labii_base_url"] = input("What is the base url [https://www.labii.dev]? ")
	if settings["labii_base_url"] == "":
		settings["labii_base_url"] = "https://www.labii.dev"
	settings["labii_organization_sid"] = input("What is your Labii organizaiton sid (Settings -> Organization -> SID)? ")
	settings["labii_project_sid"] = input("What is your Labii project sid? ")
	settings["labii_table_entry_sid"] = input("What is your Labii entry table sid (Settings -> Tables -> Entry -> SID)? ")
	settings["labii_table_file_sid"] = input("What is your Labii file table sid (Settings -> Tables -> Entry -> SID)? ")
	settings["file_path"] = input("Provide the full path of folder that contains the files to be uploaed. ")
	debug = True
	if debug:
		settings["labii_base_url"] = "http://127.0.0.1:8000"
		settings["labii_organization_sid"] = "TWZ30a40x24bcV16afkpu"
		settings["labii_project_sid"] = "HKNQ0a40x271cJOTY49di"
		settings["labii_table_entry_sid"] = "69be0a40xfff68chmrwBG"
		settings["labii_table_file_sid"] = "58ad0a40xfff57bglqvAF"
		settings["file_path"] = "/Users/yongganwu/Downloads/replacex/Darwin Yang"
	print(settings)
	settings["confirm"] = input("Enter to confirm the provide settings is correct. ")
	# collect the files
	files = glob.glob(f"{settings['file_path']}/*")
	# init the labii sdk
	labii = LabiiObject(
		base_url=settings["labii_base_url"],
		organization__sid=settings["labii_organization_sid"]
	)
	labii.api.login()
	# process the files
	for current_file in files:
		file_name = os.path.basename(current_file)
		print(f"Processing {file_name}...")
		# create a file record
		file_record = labii.upload(current_file, [{"sid": settings["labii_project_sid"]}])
		# create a entry
		entry_name = file_name.split(".")[0]
		timestamp = os.path.getmtime(current_file)
		last_modified_time = datetime.datetime.fromtimestamp(timestamp)
		formatted_time = last_modified_time.strftime("%A, %Y-%m-%d")
		response = labii.Record.create(
			{
				"name": entry_name,
				"projects": [{"sid": settings["labii_project_sid"]}],
				"data": f"""<div class="labii-day"><span class="labii-day-label">{formatted_time}</span></div><section class="labii-file" sid="{file_record['sid']}" name="{file_record['name']}" version="{file_record['version']['sid']}" should_hide_preview="false"></section><p>&nbsp;</p>"""
			},
			query=f"table__sid={settings['labii_table_entry_sid']}"
		)
		break


if __name__ == "__main__":
    main()