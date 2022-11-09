# ------------- YSC MEAL BOT -------------
# This script randomly groups students to get a meal together and
# sends an email to each group to inform them. As the user of this script, you have a
# solemn responsibility; misusing this script could send out a lot of mistaken, unwanted
# emails.
#
# USAGE:
# --PersonList.txt (default name for this can be redefined below):
#   A tab-delimited (by default, but that's configurable) csv file of students.
#   Each student must have 'Name' and 'Email'. Additional columns are OK, too.
# --Message.txt:
#   Create a file with the body of the email you want sent out to each pair. The string
#   '{GroupList}' should appear exactly once in this file; in the sent emails, '{GroupList}'
#   will be replaced with the list of names in the group, separated by a new line (\n)
#
# -- In the simplest case, run MealBot without arguments. It'll randomly pair people from PersonList.txt,
#    print the pairings, and then ask if you want to send the email to them all.

import random
import argparse
import csv
import httplib2
import os
import oauth2client
from oauth2client import client, tools, file
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from apiclient import errors, discovery

# Defaults - can be overridden with arguments.
PERSON_FILE_DELIMITER     = '\t'
DEFAULT_PERSON_FILE       = 'PersonList.txt'
DEFAULT_MESSAGE_FILE      = 'Message.txt'
DEFAULT_GROUP_SIZE        = 2
DEFAULT_BOT_EMAIL_ADDRESS = 'ysc.meal.bot@gmail.com'
DEFAULT_SUBJECT           = "[YSC MealBot] This week's meal group!"
DEFAULT_CREDENTIAL_FILE   = 'client_secret.json'

SCOPES = 'https://www.googleapis.com/auth/gmail.send'
APPLICATION_NAME = 'Gmail API Python Send Email'

def main():
    parser = argparse.ArgumentParser(description='''Randomly group students to get a meal together and 
                                                    send an email to each group to inform them.''')
    parser.add_argument('-p', '--person-file',
                        help='''File containing the list of people to group. This must be a csv file, by 
                                default delimited by tabs (but that's configurable in the script). 
                                The columns 'Name' and 'Email' must be present. 
                                Defaults to '''+DEFAULT_PERSON_FILE,
                        default=DEFAULT_PERSON_FILE)
    parser.add_argument('-m', '--message-file',
                        help='''File containing the email body ({GroupList} in the file will be replaced 
                                with the list of people in the group). Defaults to '''+DEFAULT_MESSAGE_FILE,
                        default=DEFAULT_MESSAGE_FILE)
    parser.add_argument('-g', '--group-size',
                        help='How large each random group should be. Defaults to '+str(DEFAULT_GROUP_SIZE),
                        default=DEFAULT_GROUP_SIZE)
    parser.add_argument('-e', '--email',
                        help='Gmail address from which to send emails. Defaults to '+DEFAULT_BOT_EMAIL_ADDRESS,
                        default=DEFAULT_BOT_EMAIL_ADDRESS)
    parser.add_argument('-s', '--subject',
                        help='Subject line for the emails. Defaults to "'+DEFAULT_SUBJECT+'"',
                        default=DEFAULT_SUBJECT)
    parser.add_argument('-c', '--credential-file',
                        help='''JSON file containing the credential provided by Google API. 
                                Defaults to '''+DEFAULT_CREDENTIAL_FILE,
                        default=DEFAULT_CREDENTIAL_FILE)
    args = parser.parse_args()
    mealBot(args.person_file, args.message_file, args.group_size, args.email, args.subject, args.credential_file)

def mealBot(personFilename, messageFilename, groupSize, sender, subject, credentialFilename):
    messageFile = open(messageFilename, 'r')
    message = messageFile.read()
    messageFile.close()
    
    # Get a random list of Students
    personList = formPersonList(personFilename)
    
    if len(personList) == 1:
        print('You must have more than 1 student.')
        return
    
    # Divide into groups
    groups = chunk(personList, groupSize)
    
    # Print the groups
    print('Randomized groups:\n')
    for grp in groups:
        for person in grp:
            print(person.name, person.email, sep='\t')
        print()
    
    print('Subject: '+subject)
    print('\nBody:\n'+message)
    
    # Send email?
    if input('Send emails? (Y/n) =>') == 'Y':
        print('Sending emails...')
        sendEmails(groups, sender, subject, message, credentialFilename)
        print('Emails away!')
    else:
        print('Not sending emails.')

class Person:
    def __init__(self, d):
        try:
            self.name = d['Name']
            self.email = d['Email']
        except KeyError as err:
            print('Your person list file must have columns titled "Name" and "Email"')
            print(d)
            raise
        self.fields = d
        self.paired = False
    
    def __getitem__(self, key):
        return self.fields[key]

def formPersonList(person_file):
    # Initialize list to hold persons
    personList = []
    with open(person_file, newline='') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=PERSON_FILE_DELIMITER)
        for row in reader:
            personList.append(Person(row))
    
    # Return randomized list
    random.shuffle(personList)
    return personList

# Breaks the list l into chunks of size n. Remainders are distributed to other chunks.
# Returns a list of lists.
# EX. l = [0, 1, 2, 3]; n = 2. Returns [[0, 1], [2, 3]]
def chunk(l, n):
    # First break into chunks. Groups is a list of list of Students
    n = max(1, n)
    groups = [l[i:i + n] for i in range(0, len(l), n)]
    
    # Now if there are any singletons (they'll be at the end of the list), add them to other groups
    while len(groups[-1]) == 1:
        groups[-2].append(groups[-1].pop())
        groups.pop()
    return groups

def sendEmails(groups, sender, subject, rawBody, credentialFilename):
    credentials = getCredentials(credentialFilename)
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('gmail', 'v1', http=http)
    
    for grp in groups:
        namesLst = [person.name for person in grp]
        emailsLst = [person.email for person in grp]
        body = rawBody.replace('{GroupList}', '\n'.join(namesLst))
        emails = ', '.join(emailsLst)
        message = createMessage(emails, sender, subject, body)
        sendMessage(service, "me", message)

def createMessage(toEmails, sender, subject, plaintext):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = toEmails
    msg.attach(MIMEText(plaintext, 'plain'))
    raw = base64.urlsafe_b64encode(msg.as_bytes())
    raw = raw.decode()
    body = {'raw': raw}
    return body

def getCredentials(credentialFilename):
    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir, 'gmail-python-email-send.json')
    store = oauth2client.file.Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(credentialFilename, SCOPES)
        flow.user_agent = APPLICATION_NAME
        credentials = tools.run_flow(flow, store)
        print('Storing credentials to ' + credential_path)
    return credentials

def sendMessage(service, userID, message):
    try:
        message = (service.users().messages().send(userId=userID, body=message).execute())
        return message
    except errors.HttpError as error:
        print('An error occurred: %s' % error)

if __name__ == '__main__':
    main()
