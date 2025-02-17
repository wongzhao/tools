from utils.google import perform_oauth
from googleapiclient.discovery import build
import time
import json

# Get started (Gmail): https://developers.google.com/gmail/api/quickstart/python
# Get started (People): https://developers.google.com/people/quickstart/python

# Gmail documentation: https://developers.google.com/resources/api-libraries/documentation/gmail/v1/python/latest/gmail_v1.users.messages.html
# People groups docs: https://developers.google.com/resources/api-libraries/documentation/people/v1/python/latest/people_v1.contactGroups.html

QUERY = "from:mailer-daemon@googlemail.com"


def find_messages(gm, max_msgs):
    page_token = None
    messages = []

    while len(messages) < max_msgs:
        results = gm.users().messages().list(userId="me", q=QUERY, pageToken=page_token).execute()
        messages += results["messages"]

        if "nextPageToken" in results:
            page_token = results["nextPageToken"]
        else:
            break

    return messages[:max_msgs]


def find_failed_emails(gm, messages):
    failed = {}

    def handle_message(req_id, response, exception):
        if exception is not None:
            print("Exception:", exception)
            return

        headers = response["payload"]["headers"]

        header_res = [h for h in headers if h["name"] == "X-Failed-Recipients"]
        if len(header_res) == 0:
            return

        emails = map(lambda e: e.strip(), header_res[0]["value"].split(","))
        for e in emails:
            print(f"Found bounced email to {e}.")
            if e in failed:
                failed[e] += 1
            else:
                failed[e] = 1

    BATCH_SIZE = 10
    batch = gm.new_batch_http_request(callback=handle_message)
    batch_len = 0
    for message in messages:
        batch.add(gm.users().messages().get(userId="me", id=message["id"], format="metadata"), handle_message)
        batch_len += 1

        if batch_len >= BATCH_SIZE:
            batch.execute()
            batch = gm.new_batch_http_request(callback=handle_message)
            batch_len = 0

    batch.execute()

    return failed


creds = perform_oauth(
	"files/token_mailing-list-cleanup.json",
	"files/credentials.json",
	[
		"https://www.googleapis.com/auth/contacts",
		"https://www.googleapis.com/auth/gmail.readonly"
	])

############
# API INIT #
############

gmail = build("gmail", "v1", credentials=creds)
people = build("people", "v1", credentials=creds)

##########
# Inputs #
##########

max_msgs = int(input("Maximum number of messages to search: "))
min_bounces = int(input("Minimum number of bounces to remove member: "))

#################
# Find messages #
#################

messages = find_messages(gmail, max_msgs)
print(f"Found {len(messages)} messages matching query {QUERY}.")

#######################
# Find bounced emails #
#######################

emails = find_failed_emails(gmail, messages)

emails_to_remove = set()
for email in emails:
    if emails[email] >= min_bounces:
        emails_to_remove.add(email)

if len(emails_to_remove) == 0:
    print("No emails to remove.")

print("\nEmails to remove:")
for e in emails_to_remove:
    print("-", e)

#################
# Find contacts #
#################

contacts_req = people.people().connections().list(resourceName="people/me", pageSize=2000, personFields="emailAddresses")
contacts_res = contacts_req.execute()
contacts = contacts_res["connections"]

while True:
    contacts_req = people.people().connections().list_next(previous_request=contacts_req, previous_response=contacts_res)
    if contacts_req is None:
        break
    else:
        contacts_res = contacts_req.execute()
        contacts += contacts_res["connections"]

contacts_to_remove = set()

print("\nContacts to remove:")
for c in contacts:
    emails = [e for e in c["emailAddresses"] if e["value"] in emails_to_remove]
    if len(emails) > 0:
        contacts_to_remove.add(c["resourceName"])
        print(f"- {emails[0]['value']} ({c['resourceName']})")

time.sleep(1)

groups_req = people.contactGroups().list()
groups_res = groups_req.execute()
groups = groups_res["contactGroups"]

while True:
    print("")
    for i, group in enumerate(groups):
        print(f"{i + 1}. {group['name']}")

    print("""
Enter a group number to filter the group.
Or, enter 'n' to fetch the next page or 'q' to quit.
""")

    inp = input("group number, n, or q: ")

    if inp == "n":
        groups_req = people.contactGroups().list_next(previous_request=groups_req, previous_response=groups_res)
        if groups_req is None:
            print("No more groups.")
            time.sleep(1)
        else:
            groups_res = groups_req.execute()
            groups += groups_res["contactGroups"]
    elif inp == "q":
        break
    elif inp.isdigit():
        group = groups[int(inp) - 1]
        group_res = people.contactGroups().get(resourceName=group["resourceName"], maxMembers=500).execute()

        to_remove = [r for r in group_res["memberResourceNames"] if r in contacts_to_remove]

        print("\nThe following members will be removed:")
        for rn in to_remove:
            print("-", rn)

        ok = input("\nOK? (y/n) ")
        if ok == "y":
            group_backup = {
                "data": group_res,
                "removed": to_remove
            }

            backup_filename = f"files/{int(time.time())}_{group['name']}_BACKUP.json"
            with open(backup_filename, "w") as backup_file:
                backup_file.write(json.dumps(group_backup))

            print(f"\nPrevious contact group data backed up to {backup_filename}.")

            res = people.contactGroups().members().modify(resourceName=group_res["resourceName"], body={
                "resourceNamesToRemove": to_remove
            }).execute()
        else:
            print("Canceled.")
    else:
        print("Invalid input.")
