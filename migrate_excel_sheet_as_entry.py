"""
The `migrate_excel_sheet_as_entry.py` function offers a powerful solution for seamlessly converting each sheet within a provided Excel file into individual experiment entries.
"""
import re
import os
import datetime
import pandas as pd
from labii_sdk.sdk import LabiiObject
from migrate_file_as_entry import collect_labii_settings, upload_file_as_labii_entry

def main():
	""" separate one excel file into multiple files based on sheet name """
	# collect the settings
	settings = collect_labii_settings()
	settings["file_path"] = input("Provide the full path of the excel file. ")
	debug = True
	if debug:
		settings["labii_base_url"] = "http://127.0.0.1:8000"
		settings["labii_organization_sid"] = "TWZ30a40x24bcV16afkpu"
		settings["labii_project_sid"] = "HKNQ0a40x271cJOTY49di"
		settings["labii_table_entry_sid"] = "69be0a40xfff68chmrwBG"
		settings["labii_table_file_sid"] = "58ad0a40xfff57bglqvAF"
		settings["file_path"] = "xxx.xlsx"
	print(settings)
	settings["confirm"] = input("Enter to confirm the provide settings is correct. ")
	# init the labii sdk
	labii = LabiiObject(
		base_url=settings["labii_base_url"],
		organization__sid=settings["labii_organization_sid"]
	)
	labii.api.login()
	# get excels
	xls = pd.ExcelFile(settings["file_path"])
	index = 1
	for sheet_name in xls.sheet_names:
		print(f"{index}/{len(xls.sheet_names)}...")
		index += 1
		sheet_df = xls.parse(sheet_name)
		new_excel_file_path = settings["file_path"].replace(".xlsx", f" - {sheet_name}.xlsx")
		sheet_df.to_excel(new_excel_file_path, index=False)
		# time stamps
		# use the modified time if no time stamp
		timestamps = re.findall(r'\d{6}', sheet_name)
		timestamp = ""
		if len(timestamps) > 0:
			datetime_obj = datetime.datetime.strptime(timestamps[0], '%m%d%y')
			timestamp = datetime_obj.timestamp()
		else:
			timestamp = os.path.getmtime(settings["file_path"])
		upload_file_as_labii_entry(labii, new_excel_file_path, settings, timestamp=timestamp)
		# remove
		file_escape = new_excel_file_path.replace(' ', '\ ')#pylint: disable=anomalous-backslash-in-string
		os.system(f"rm {file_escape}")

if __name__ == "__main__":
	main()
