""" core manage function """
import sys
import os
from labii_sdk_core.sdk import print_red, print_blue, print_green, prepare_usage, merge_requests
from labii_sdk_core.whl import install_whl

def main():
	""" main handle function """
	# update here for name of the function
	actions = []

	# update here for arguments
	usage = prepare_usage(actions)
	usage = f"{usage}\ntest, the test job"

	if len(sys.argv) < 2:
		print_blue(usage)
		sys.exit()

	# get action
	action = sys.argv[1]
	# if len(sys.argv) >= 3:
	#     para = sys.argv[2]

	if action == "merge":
		merge_requests()
	elif action == "install_whl":
		install_whl("labii_sdk_core")
	elif action == "test":
		os.system("python -m unittest tests")
	else:
		print_red(f"Error: Action ({action}) is not recognizable!")
		print(usage)
		sys.exit()
	print_green("Done!")

if __name__ == "__main__":
	main()
