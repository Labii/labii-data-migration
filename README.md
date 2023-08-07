# labii-data-migration
The Labii Data Migration Toolkit is an open-source repository designed to assist users in seamlessly migrating their data to the Labii platform. Labii is a powerful and versatile research data management system, and this toolkit aims to simplify the process of transferring existing data from various sources to the Labii environment.

### Getting Started:
The repository's README file contains a detailed guide on how to get started with the Labii Data Migration Toolkit. Users will find instructions on installing dependencies, setting up their Labii account, and initiating the data migration process.
1. Init python virtual env: `python3 -m venv env`
2. Install the packages: `pip install -r requirements_env.txt`

### migrate_file_as_entry.py
The "migrate_file_as_entry.py" function is a versatile data import utility designed to streamline the process of importing files into a research data management system. With a user-friendly interface, this function allows users to effortlessly import each file as a separate experiment entry, ensuring seamless organization and retrieval of research data. The function intelligently extracts the file name and uses it as the experiment name, providing clear and descriptive titles for each entry. Additionally, the imported file is automatically treated as an attachment to the respective entry, eliminating the need for separate handling or linking. This efficient and time-saving feature enables researchers to efficiently manage and access their data, promoting a more productive and organized research workflow.
Support folder structure 1 (each file -> one experiment entry):
	- file 1
	- file 2 
Support folder structure 2 (each folder -> one experiment entry):
	- folder 1
		- file 1
		- file 2 
	- folder 2
		...

### migrate_excel_sheet_as_entry.py
The `migrate_excel_sheet_as_entry.py` function offers a powerful solution for seamlessly converting each sheet within a provided Excel file into individual experiment entries.

### migrate_benchling_entries.py
The `migrate_benchling_entries.py` function serves as a script to facilitate the seamless migration of data from Benchling to Labii. Specifically, it is designed to import Benchling entries, which encompass various forms of scientific data and documentation, into Labii's entry system.

### migrate_benchling_plasminds.py
Introducing `migrate_benchling_plasminds.py`: A seamless solution to streamline genetic data management, this Python function effortlessly associates GenBank (`*.gb`) files from Benchling with Labii plasmids, creating a harmonious bridge between genetic design and lab management. Through intelligent extraction of DNA sequences, annotations, and metadata, this tool automates the process, ensuring accurate and efficient integration. Researchers can now consolidate their genetic information within Labii's comprehensive platform, enhancing organization, accessibility, and collaboration in a single, user-friendly command-line interface. Say goodbye to manual data transfer, and embrace a new era of molecular biology research efficiency with `migrate_benchling_plasminds.py`.

* `copy_gb_files`. Utilize this function to gather all *.gb files within a designated folder, enabling their utilization by the "upload_gb_as_file_based_on_benchling_link" function.
* `upload_gb_as_file_based_on_benchling_link`. Utilize this function for the purpose of uploading the *gb files that have been exported from Benchling onto your Labii plasmid record as a file. To enable its functionality, it is essential to possess a Benchling link column containing a text widget, along with a files section equipped with the Files widget.
* `upload_gb_as_file_based_on_name`. Utilize this function for the purpose of uploading the *gb files that have been exported from Benchling onto your Labii plasmid record as a file.