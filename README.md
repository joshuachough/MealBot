Randomly group people together to get a meal together, and send an email to everyone to tell them what their group is!

1. As described [here](https://developers.google.com/gmail/api/quickstart/python), set up a Google Cloud project, enable the Gmail API, and create credentials for a desktop application. Store the credentials JSON file as `client_secret.json` in your working directory as you run `MealBot.py`.

2. You will also need to use pip to install a couple of modules that may not already be installed on your machine:

```
pip install --upgrade google-api-python-client
pip install --upgrade oauth2client
```

3. Set up `PersonList.txt`. This is a tab-delimited csv file with the columns Name and Email. (Delimiting it by tabs means that you can copy-paste directly from a Google sheet into a text file, and it will work.) MealBot will randomly group these people together.

4. Set up `Message.txt`. This is the body of the email that will be sent to each person in `PersonList.txt`. The string `{GroupList}` must appear exactly once in the file; it will be replaced with the list of people that were randomly grouped together.

5. Run `MealBot.py`. There are a number of options (run `MealBot.py -h` to see them), but if you don't change any file names then they probably won't be needed.
