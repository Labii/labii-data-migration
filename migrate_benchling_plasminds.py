"""
The "migrate_file_as_entry.py" function is a versatile data import utility designed to streamline the process of importing files into a research data management system. With a user-friendly interface, this function allows users to effortlessly import each file as a separate experiment entry, ensuring seamless organization and retrieval of research data. The function intelligently extracts the file name and uses it as the experiment name, providing clear and descriptive titles for each entry. Additionally, the imported file is automatically treated as an attachment to the respective entry, eliminating the need for separate handling or linking. This efficient and time-saving feature enables researchers to efficiently manage and access their data, promoting a more productive and organized research workflow.
"""
import os
import shutil
import glob
from labii_sdk.sdk import LabiiObject
from migrate_file_as_entry import collect_labii_settings

def copy_gb_files(source_folder, destination_folder):
	""" Utilize this function to gather all *.gb files within a designated folder, enabling their utilization by the "upload_gb_as_file_based_on_benchling_link" function. """
	# Create the destination folder if it doesn't exist
	if not os.path.exists(destination_folder):
		os.makedirs(destination_folder)
	# Walk through the source folder and its subfolders
	for root, _, files in os.walk(source_folder):
		for file in files:
			if file.endswith(".gb"):
				source_path = os.path.join(root, file)
				destination_path = os.path.join(destination_folder, file)
				shutil.copy2(source_path, destination_path)
				print(f"Copied {source_path} to {destination_path}")

def upload_gb_as_file_based_on_benchling_link():
	""" Utilize this function for the purpose of uploading the *gb files that have been exported from Benchling onto your Labii plasmid record as a file. To enable its functionality, it is essential to possess a Benchling link column containing a text widget, along with a files section equipped with the Files widget. """
	settings = collect_labii_settings(skip=["labii_project_sid", "labii_table_entry_sid"])
	settings["labii_table_plasmid_sid"] = input("What is your Labii plasmid table sid (Settings -> Tables -> Plasmid -> SID)? ")
	settings["labii_column_benchling_sid"] = input("What is your Labii column benchling link sid (Settings -> Tables -> Plasmid -> Columns -> Benchling Link -> SID)? ")
	settings["folder_path_gb"] = input("Provide the full path of folder that contains the *.gb files to be uploaed. ")
	debug = True
	if debug:
		settings["labii_base_url"] = "http://127.0.0.1:8000"
		settings["labii_organization_sid"] = "TWZ30a40x24bcV16afkpu"
		settings["labii_project_sid"] = "HKNQ0a40x271cJOTY49di"
		settings["labii_table_entry_sid"] = "69be0a40xfff68chmrwBG"
		settings["labii_table_file_sid"] = "58ad0a40xfff57bglqvAF"
		settings["folder_path"] = "xxx"
	settings["folder_path_gb"] = settings["folder_path_gb"].rstrip("/")
	print(settings)
	settings["confirm"] = input("Enter to confirm the provide settings is correct. ")
	# init the labii sdk
	labii = LabiiObject(
		base_url=settings["labii_base_url"],
		organization__sid=settings["labii_organization_sid"]
	)
	labii.api.login()
	# find all plasmids
	plasmids = labii.Record.list(
		all_pages=False,
		serializer="detail",
		query=f"table__sid={settings['labii_table_plasmid_sid']}"
	)
	# check each plasmid
	should_break = False
	for plasmid in plasmids["results"]:
		if not plasmid['uid'] in ["PM1", "PM152", "PM150", "PM151"]:
			cell_benchling = ""
			log = f"{plasmid['uid']}: {plasmid['name']}"
			for cell in plasmid["column_set"]:
				if cell["column"]["sid"] == settings["labii_column_benchling_sid"]:
					cell_benchling = cell.copy()
					break
			if cell_benchling != "":
				if "benchling" in cell_benchling["data"]:# if the cell have the data
					seqid = cell_benchling["data"].split("seq_")[1].split("-")[0]
					seqid = f"seq_{seqid}"
					files = glob.glob(f"{settings['folder_path_gb']}/*{seqid}*.gb")
					if len(files) > 0:
						file_record = labii.upload(files[0], plasmid["projects"])
						# find the files section
						for section in plasmid["section_set"]:
							if section["name"] == "Files":
								data = {"data": [{'file': {'sid': file_record["sid"], 'name': f'{file_record["uid"]}: {file_record["name"]}'}, 'should_hide_preview': False, 'should_hide_column_data': True}]}
								labii.Section.modify(
									section["sid"],
									data
								)
								log = f"{log} SUCCESS: uploaded {seqid}"
								should_break = True
								break
					else:
						log = f"{log} FAILED: not found the *.gb file ({seqid})"
				else:
					log = f"{log} FAILED: not benchling link available"
			else:
				log = f"{log} FAILED: not found benchling column ({settings['labii_column_benchling_sid']})"
			print(log)

def upload_gb_as_file_based_on_name():
	""" Utilize this function for the purpose of uploading the *gb files that have been exported from Benchling onto your Labii plasmid record as a file. """
	settings = collect_labii_settings(skip=["labii_project_sid", "labii_table_entry_sid"])
	settings["labii_table_plasmid_sid"] = input("What is your Labii plasmid table sid (Settings -> Tables -> Plasmid -> SID)? ")
	settings["folder_path_gb"] = input("Provide the full path of folder that contains the *.gb files to be uploaed. ")
	debug = True
	if debug:
		settings["labii_base_url"] = "http://127.0.0.1:8000"
		settings["labii_organization_sid"] = "TWZ30a40x24bcV16afkpu"
		settings["labii_project_sid"] = "HKNQ0a40x271cJOTY49di"
		settings["labii_table_entry_sid"] = "69be0a40xfff68chmrwBG"
		settings["labii_table_file_sid"] = "58ad0a40xfff57bglqvAF"
		settings["folder_path"] = "xxx"
	settings["folder_path_gb"] = settings["folder_path_gb"].rstrip("/")
	print(settings)
	settings["confirm"] = input("Enter to confirm the provide settings is correct. ")
	# init the labii sdk
	labii = LabiiObject(
		base_url=settings["labii_base_url"],
		organization__sid=settings["labii_organization_sid"]
	)
	labii.api.login()
	# find all plasmids
	plasmids = labii.Record.list(
		all_pages=True,
		serializer="detail",
		query=f"table__sid={settings['labii_table_plasmid_sid']}"
	)
	# check each plasmid
	should_break = False
	for plasmid in plasmids["results"]:
		if not plasmid['uid'] in ["PM141", "PM142", "PM143", "PM146", "PM147", "PM148", "PM150", "PM1", "PM144", "PM149", "PM145"]:
			log = f"{plasmid['uid']}: {plasmid['name']}"
			files = glob.glob(f"{settings['folder_path_gb']}/*{plasmid['name']}*.gb")
			if len(files) > 0:
				file_record = labii.upload(files[0], plasmid["projects"])
				# find the files section
				for section in plasmid["section_set"]:
					if section["name"] == "Files":
						data = {"data": [{'file': {'sid': file_record["sid"], 'name': f'{file_record["uid"]}: {file_record["name"]}'}, 'should_hide_preview': False, 'should_hide_column_data': True}]}
						labii.Section.modify(
							section["sid"],
							data
						)
						log = f"{log} SUCCESS: uploaded {plasmid['name']}"
						should_break = True
						break
			else:
				log = f"{log} FAILED: not found the *.gb file ({plasmid['name']})"
			print(log)

def main():
	""" Depending on the configuration of your Labii plasmid table, the methods for migrating your *gb files will vary. You have the flexibility to select or adapt the functions according to your specific requirements. """
	upload_gb_as_file_based_on_name()


if __name__ == "__main__":
	main()
