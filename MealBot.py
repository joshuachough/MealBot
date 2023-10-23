# ------------- YSC MEAL BOT -------------
# This script randomly groups students to get a meal together and
# sends an email to each group to inform them. As the user of this script, you have a
# solemn responsibility; misusing this script could send out a lot of mistaken, unwanted
# emails.
#
# Usage:
# `python MealBot.py`
#   Runs the script with the default arguments. This will randomly group students who have filled out the Google Form
#   with SignupFormID while trying to avoid previous groups stored in the Google Sheet with GroupsSheetID, send an
#   email to each group with the body of the email in Message.txt, and save the groups to the Google Sheet with
#   GroupsSheetID.
#
# Important Arguments:
# --SignupFormID:
#   The ID of the Google Form that students fill out to sign up. The form must have
#   the following questions:
#       - First Name (short answer)
#       - Last Name (short answer)
#       - Email (short answer)
#       - Year (short answer)
#       - College (short answer)
# --GroupsSheetID:
#   The ID of the Google Sheet that stores previous groups. The sheet must have
#   the following columns:
#       - Week: The week of the group (e.g. "Week 1 | 08/30/21 - 09/05/21")
#       - Group: The list of names in the group, separated by commas (e.g. "Alex Schurman, Bonnie Schurman")
# --GroupsRange:
#   The range of the Google Sheet that stores previous groups. Defaults to Sheet1!A2:B
# --Message.txt:
#   A file with the body of the email you want sent out to each group. The string
#   '{GroupList}' should appear exactly once in this file; in the sent emails, '{GroupList}'
#   will be replaced with the list of names in the group, separated by a new line (\n)

import random
import argparse
import httplib2
import itertools
from tqdm import tqdm
from datetime import date, timedelta
from httplib2 import Http
from oauth2client import client, tools, file
import base64
from email.message import EmailMessage
from apiclient import errors, discovery

from utils import *

SCOPES = ['https://www.googleapis.com/auth/gmail.send', 'https://www.googleapis.com/auth/forms.responses.readonly', 'https://www.googleapis.com/auth/spreadsheets']
DISCOVERY_DOC = 'https://forms.googleapis.com/$discovery/rest?version=v1'
FIRST_NAME_QID = '76e2ebcf'
LAST_NAME_QID = '3b64eca4'
YEAR_QID = '32825110'
COLLEGE_QID = '555d65c7'
OPT_IN_QID = '15019bbd'
OPT_IN_YES = 'Yes!'
OPT_IN_NO = 'No.. I want to be taken off the list for now.'
GROUP_SIZE = 2

# Defaults - can be overridden with arguments.
DEFAULT_APPLICATION_NAME    = 'YSC MEALBOT'
DEFAULT_SIGNUP_FORM_ID      = '1gyiAJszs2akMHrpErmb_ABPzbKIJU5Pd4OUhVXWNj9Y'
DEFAULT_GROUPS_SHEET_ID     = '15HGJf3WPPFcvcVXvpOw1puazJxxR8SJBX0wk_lpd82g'
DEFAULT_GROUPS_RANGE        = 'Sheet1!A2:B'
DEFAULT_MESSAGE_FILE        = 'Message.txt'
DEFAULT_BOT_EMAIL_ADDRESS   = 'YSC Mealbot <josh.chough@yale.edu>'
DEFAULT_SUBJECT             = "[YSC MealBot] {BiWeek} | Your biweekly meal group!"
DEFAULT_CREDENTIALS_FILE    = 'client_secret.json'
DEFAULT_TOKEN_FILE          = 'token.json'

class Student:
    def __init__(self, d):
        try:
            self.firstname = d['firstname']
            self.lastname = d['lastname']
            self.year = d['year']
            self.college = d['college']
            self.name = self.firstname + ' ' + self.lastname
            self.email = d['email']
        except KeyError as err:
            print('Error: You must have a key for '+err.args[0]+' in your JSON file.')
            print(d)
            raise

# Function to generate all possible combinations of k-groups from a list of students
def generate_combinations(students):
    print('Generating all possible combinations...', end='')
    combinations = list(itertools.combinations(students, GROUP_SIZE))
    print('Done')
    return combinations

# Function to filter out combinations that have been used before
def filter_combinations(combinations, prevGroups):
    print('Filtering out previously used combinations...', end='')
    new_groups = []
    for grp in combinations:
        if frozenset([student.name for student in grp]) not in prevGroups:
            new_groups.append(grp)
    print('Done')
    return new_groups

# Breaks the list l into chunks of size n. Assume that len(l) % n == 0.
# Returns a list of lists.
# EX. l = [0, 1, 2, 3]; n = 2. Returns [[0, 1], [2, 3]]
def chunk(l):
    # First break into chunks. Groups is a list of list of Students
    n = max(1, GROUP_SIZE)
    groups = [l[i:i + n] for i in range(0, len(l), n)]
    return groups

def print_header(header, length):
    if length == 0:
        print('\n{}: None'.format(header))
        return
    else:
        print('\n{} [{}]:'.format(header, length))

def print_groups(header, groups, student=True, emails=False):
    print_header(header, len(groups))
    for grp in groups:
        if not student:
            print('\t{}'.format(', '.join([name for name in grp])))
        elif emails:
            print('\t{}'.format(', '.join(['{} ({})'.format(student.name, student.email) for student in grp])))
        else:
            print('\t{}'.format(', '.join([student.name for student in grp])))

def print_students(header, students):
    print_header(header, len(students))
    for student in students:
        print('\t{}'.format(student.name))

def getMessage(messageFilename):
    print('Reading message file...', end='')
    messageFile = open(messageFilename, 'r')
    message = messageFile.read()
    messageFile.close()
    print('Done')
    return message

def getCredentials(credentialFilename, tokenFilename, user_agent):
    print('Getting credentials...', end='')
    store = file.Storage(tokenFilename)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(credentialFilename, SCOPES)
        flow.user_agent = user_agent
        credentials = tools.run_flow(flow, store)
        print('Storing credentials to ' + tokenFilename)
    print('Done')
    return credentials

def getStudents(credentials, signupFormId):
    print('Getting students...', end='')
    students, opted_out = [], []
    service = discovery.build('forms', 'v1', http=credentials.authorize(
    Http()), discoveryServiceUrl=DISCOVERY_DOC, static_discovery=False)
    result = service.forms().responses().list(formId=signupFormId).execute()
    for response in result['responses']:
        if OPT_IN_QID in response['answers'].keys():
            opt_in = response['answers'][OPT_IN_QID]['textAnswers']['answers'][0]['value']
            if opt_in == OPT_IN_NO:
                opted_out.append(response['respondentEmail'].strip())
                continue
        students.append(Student({
            'firstname': response['answers'][FIRST_NAME_QID]['textAnswers']['answers'][0]['value'].strip(),
            'lastname': response['answers'][LAST_NAME_QID]['textAnswers']['answers'][0]['value'].strip(),
            'year': response['answers'][YEAR_QID]['textAnswers']['answers'][0]['value'],
            'college': response['answers'][COLLEGE_QID]['textAnswers']['answers'][0]['value'],
            'email': response['respondentEmail'].strip()
        }))
    print('Done ({} students, {} opted out)'.format(len(students), len(opted_out)))
    return students

def getPrevGroups(credentials, spreadsheetId, range):
    print('\nGetting previous groups...', end='')
    prevGroups = set()
    sheet = None
    try:
        service = discovery.build('sheets', 'v4', credentials=credentials)
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=spreadsheetId, range=range).execute()
        values = result.get('values', [])
        for row in values:
            prevGroups.add(frozenset(row[1].split(', ')))
        print('Done')
    except errors.HttpError as error:
        print('Failed')
        print('Error: %s' % error)
    return prevGroups, sheet

def findGroups(students, prevGroups, customGroupings):
    groups = []

    if customGroupings:
        numGroups = len(students)/2
        odd = True if len(students) % GROUP_SIZE == 1 else False
        if odd:
            print('\nYou will need to enter {} groups of {} students each and 1 group of {} students.'.format(numGroups-1, GROUP_SIZE, GROUP_SIZE+1))
        else:
            print('\nYou will need to enter {} groups of {} students each.'.format(numGroups, GROUP_SIZE))

        # Get custom groupings from file
        customGroupingsFile = open(input('\nWhich custom groupings file would you like to use?\n > '), 'r')
        customGroupings = customGroupingsFile.read().splitlines()
        customGroupingsFile.close()

        while (len(customGroupings) > 0):
            # Get next group
            group = customGroupings.pop(0).split(', ')
            group = [name.strip() for name in group]
            group = [student for student in students if student.name in group]
            if len(group) < GROUP_SIZE:
                print('Error: You must have at least {} students in a group.'.format(GROUP_SIZE))
                continue
            if group[0].name == group[1].name:
                print('Error: You cannot have the same student in a group twice.')
                continue
            for g in groups:
                if len(set(g).intersection(set(group))) > 0:
                    print('Error: You cannot have the same student ({}) in multiple groups.'.format(g[0].name))
                    continue
            groups.append(group)

        print_groups('Tentative custom groups', groups)
        if (len(groups) != numGroups):
            print('Error: You must have {} groups of students.'.format(numGroups))
            exit()
        numStudents = sum([len(group) for group in groups])
        if (numStudents != len(students)):
            print('Error: You must have {} students in total.'.format(len(students)))
            exit()
    else:
        # Randomize the list of students
        print('\nShuffling students...', end='')
        random.shuffle(students)
        print('Done')

        # Handle odd number of students
        odd = False
        odd_student = None
        if len(students) % GROUP_SIZE == 1:
            print('\nOdd number of students detected! Saving the odd student for later...', end='')
            odd = True
            odd_student = students.pop()
            print('Done\n')

        # Generate all possible combinations of groups
        combinations = generate_combinations(students)
        new_groups = filter_combinations(combinations, prevGroups)
        print('Total new combinations: {}/{}'.format(len(new_groups), len(combinations)))

        # Find the set of groups that maximizes the number of new groups
        participants = []
        for i, ngrp in enumerate(new_groups):
            temp_students = [student for student in ngrp]
            temp_groups = [ngrp]
            for j in range(i+1, len(new_groups)):
                mgrp = new_groups[j]
                if len(set(mgrp).intersection(set(temp_students))) == 0:
                    temp_students.extend(mgrp)
                    temp_groups.append(mgrp)
            if len(temp_groups) > len(groups):
                groups = temp_groups
                participants = temp_students
        print_groups('New groups', groups)

        # Group the remaining students that were not in the optimal set of groups
        if len(participants) != len(students):
            remaining_students = [student for student in students if student not in participants]
            print_students('Remaining students', remaining_students)
            old = chunk(remaining_students)
            print_groups('Old groups', old)
            groups.extend(old)

        groups = [list(grp) for grp in groups]

        # Add the odd student to the first group
        if odd:
            print('\nAdding odd student ({}) to the first group...'.format(odd_student.name), end='')
            groups[0].append(odd_student)
            print('Done')
    
    return groups

def getWeekString(n, thisWeek=False, withNums=False):
    today = date.today()
    start = today + timedelta(days=(6 - today.weekday()))
    if thisWeek:
        start = start - timedelta(days=7)
    weekGroupLength = 7 * n - 1
    end = start + timedelta(days=weekGroupLength)
    monday = start + timedelta(days=1)
    if withNums:
        return f"Week {monday.strftime('%W')} & {int(monday.strftime('%W'))+1} | {start.strftime('%m/%d/%y')} - {end.strftime('%m/%d/%y')}"
    else:
        return f"{start.strftime('%m/%d/%y')} - {end.strftime('%m/%d/%y')}"

def saveGroups(groups, sheet, spreadsheetId, range, week):
    currRow = len(sheet.values().get(spreadsheetId=spreadsheetId, range=range).execute().get('values', [])) + 2
    sheet.values().update(spreadsheetId=spreadsheetId, range=f"Sheet1!A{currRow}:B", valueInputOption='USER_ENTERED', body={
        'values': [[week, ', '.join([student.name for student in grp])] for grp in groups]
    }).execute()

def createMessage(toEmails, sender, subject, plaintext):
    message = EmailMessage()

    message.set_content(plaintext)
    message['To'] = toEmails
    message['From'] = sender
    message['Subject'] = subject

    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    body = {
        'raw': encoded_message
    }
    return body

def sendMessage(service, userID, message):
    try:
        message = (service.users().messages().send(userId=userID, body=message).execute())
        return message
    except errors.HttpError as error:
        print('Error: %s' % error)

def sendEmails(groups, sender, subject, rawBody, credentials):
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('gmail', 'v1', http=http)
    
    groups = tqdm(groups, desc='Sending emails')
    for grp in groups:
        namesLst = [student.name for student in grp]
        emailsLst = [student.email for student in grp]
        body = rawBody.replace('{GroupList}', '\n'.join(namesLst))
        emails = ', '.join(emailsLst)
        message = createMessage(emails, sender, subject, body)
        sendMessage(service, "me", message)

def mealBot(args):
    # Read the message file
    message = getMessage(args.message_file)

    # Get credentials
    credentials = getCredentials(args.credentials_file, args.token_file, args.application_name)
    
    # Get a list of students
    students = getStudents(credentials, args.signup_form_id)
    print_students('Students', students)
    
    if len(students) == 1:
        print('Error: You must have more than 1 student.')
        return
    
    # Get previous groups
    prevGroups, sheet = getPrevGroups(credentials, args.groups_sheet_id, args.groups_range)
    if sheet is None:
        print('Error: Could not get previous groups.')
        return
    print_groups('Previous groups', prevGroups, student=False)
    
    # Find optimal groups
    groups = findGroups(students, prevGroups, args.custom_groupings)
    print_groups('Final groups', groups, emails=True)

    # Confirm groups?
    if input('\nContinue? (Y/n)\n> ').lower() != 'y':
        print('Exiting...')
        return
    
    # Get the week string
    week = getWeekString(args.week_group_frequency, args.this_week_group)

    # Print the email template
    print('\n ~~~~ EMAIL START ~~~~')
    print('\nFrom: {}'.format(args.email))
    args.subject = args.subject.replace('{BiWeek}', week)
    print('Subject: {}'.format(args.subject))
    print('\nBody:\n{}'.format(message))
    print('\n ~~~~ EMAIL END ~~~~')
    
    # Send email?
    if input('\nSend emails? (Y/n)\n> ').lower() != 'y':
        print('Exiting...')
        return

    sendEmails(groups, args.email, args.subject, message, credentials)
    print('Sending emails...Done')

    # Save the groups
    print('Saving groups...', end='')
    week = getWeekString(args.week_group_frequency, args.this_week_group, withNums=True)
    saveGroups(groups, sheet, args.groups_sheet_id, args.groups_range, week)
    print('Done')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='''Randomly group students to get a meal together and 
                                                    send an email to each group to inform them.''')
    parser.add_argument('-a', '--application-name',
                        help='Name of the application. Defaults to "'+DEFAULT_APPLICATION_NAME+'"',
                        default=DEFAULT_APPLICATION_NAME)
    parser.add_argument('-c', '--credentials-file',
                        help='''JSON file containing the credentials provided by Google API. 
                                Defaults to '''+DEFAULT_CREDENTIALS_FILE,
                        default=DEFAULT_CREDENTIALS_FILE)
    parser.add_argument('-t', '--token-file',
                        help='''JSON file that will contain the token provided by Google API. 
                                Defaults to '''+DEFAULT_TOKEN_FILE,
                        default=DEFAULT_TOKEN_FILE)
    parser.add_argument('-f', '--signup-form-id',
                        help='''ID of the Google Form that students fill out to sign up.
                                Defaults to '''+DEFAULT_SIGNUP_FORM_ID,
                        default=DEFAULT_SIGNUP_FORM_ID)
    parser.add_argument('-g', '--groups-sheet-id',
                        help='''ID of the Google Sheet that stores previous groups.
                                Defaults to '''+DEFAULT_GROUPS_SHEET_ID,
                        default=DEFAULT_GROUPS_SHEET_ID)
    parser.add_argument('-r', '--groups-range',
                        help='''Range of the Google Sheet that stores previous groups.
                                Defaults to '''+DEFAULT_GROUPS_RANGE,
                        default=DEFAULT_GROUPS_RANGE)
    parser.add_argument('-e', '--email',
                        help='Gmail address from which to send emails. Defaults to '+DEFAULT_BOT_EMAIL_ADDRESS,
                        default=DEFAULT_BOT_EMAIL_ADDRESS)
    parser.add_argument('-s', '--subject',
                        help='Subject line for the emails. Defaults to "'+DEFAULT_SUBJECT+'"',
                        default=DEFAULT_SUBJECT)
    parser.add_argument('-m', '--message-file',
                        help='''File containing the email body ({GroupList} in the file will be replaced 
                                with the list of students in the group). Defaults to '''+DEFAULT_MESSAGE_FILE,
                        default=DEFAULT_MESSAGE_FILE)
    parser.add_argument('--custom-groupings',
                        help='''Use custom groupings instead of random groupings. Defaults to False.''',
                        default=False, const=True,
                        type=str2bool,
                        nargs='?')
    parser.add_argument('--this-week-group',
                        help='''Send emails for this week group instead of next week group. A week group is the
                                group of weeks that MealBot sends out groupings (i.e. every 1 week, 2 weeks,
                                3 weeks, etc). Defaults to False.''',
                        default=False, const=True,
                        type=str2bool,
                        nargs='?')
    parser.add_argument('--week-group-frequency',
                        help='''Frequency of week groups (1-52). Defaults to 2 (i.e. every other week).''',
                        default=2,
                        type=int,
                        choices=range(1, 53))

    args = parser.parse_args()

    mealBot(args)