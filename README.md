Randomly group people together to get a meal together, and send an email to everyone to tell them what their group is!

1. (Optional) Install miniconda and create a new environment for this project:

    ```
    conda create -n mealbot python=3.10
    conda activate mealbot
    ```

1. Install Python 3.10.7 or later.

1. Go through the Google Workspace [Python quickstart](https://developers.google.com/gmail/api/quickstart/python) for Gmail

    In this guide, you should [set up a Google Cloud project](https://developers.google.com/workspace/guides/create-project), enable the Gmail API, configure the OAuth consent screen, and create credentials for a desktop application. Store the credentials JSON file as `client_secret.json` in your working directory.

    > Note: Whichever test user you add when configuring the OAuth consent screen will be the account that sends the emails. If you want to use a different account, then add that account as a test user. When running `MealBot.py` for the first time, you will be prompted to log in to the account that you added as a test user.

1. Create a Google Form for signups

    Make sure there is at least questions for `First Name`, `Last Name`, `Year`, `College`, and `Opt in?`. The `Opt in?` question should be a multiple choice question with the options `Yes` and `No`.

    The form should be set to collect email addresses. To do this, go to the `Settings` tab at the top and hit the dropdown next to `Responses`. Next to `Collect email addresses`, select either `Responder input` (manual input) or `Verified` (forced to log in to Google).

    Also in the `Responses` dropdown, it is useful to enable `Allow response editing` and `Limit to 1 response`. This will allow people to change their response if they change their mind, and will prevent people from submitting multiple responses for the same person.

    (Optional) I also disabled `Restrict to users in <my domain> and its trusted organizations` to allow people to use their non domain email addresses.

1. Create a Google Sheet to track previous groupings

    Make sure to label the first row of column A `Week` and column B `Grouping`. This will be used to keep track of who has been grouped together in the past, so that the same people don't get grouped together again. `MealBot.py` will automatically update this sheet after sending out the emails to reflect the new groupings, filling in the columns starting at row 2.

1. Find IDs for the Google Form and Google Sheet

    To get the ID for the Google Form/Sheet, open up the form/sheet in editing mode and get the string of characters in the URL before `/edit` (e.g. `1gyiAJszs2akMHrpErmb_ABPzbKIJU5Pd4OUhVXWNj9Z` from `https://docs.google.com/forms/d/1gyiAJszs2akMHrpErmb_ABPzbKIJU5Pd4OUhVXWNj9Z/edit`).
    
    To [get the IDs for the questions in the Google Form](https://stackoverflow.com/a/67221337/10084882), open up the form in preview mode (click the eye icon in the top right) and [open the web inspector](https://blog.hubspot.com/website/how-to-inspect). In the `Elements` tab, click on the search icon and search `CP1oW`. Go to the section of the search results that has the term `viewform` and click on each  search result that should look like this:

    ```html
    <div jsmodel="CP1oW" data-params="%.@.[2030661291,&quot;First Name&quot;,null,0,[[1994582991,null,true,null,null,null,null,null,null,null,[]]],null,null,null,null,null,null,[null,&quot;First Name&quot;]],&quot;i5&quot;,&quot;i6&quot;,&quot;i7&quot;,false]">
    ```

    For the example above, we can see that this is the `First Name` question. There are two numbers in the `data-params` attribute: `2030661291` and `1994582991`. The first number is the ID for the question, and the second number is the ID for the question's response. The second number is the one we want. Make sure to convert this decimal number to hexadecimal. Repeat this process for each question in the form.

    Put all these IDs in the file `ids.json`.

1. Set up other values

    In `ids.json`, set the `APPLICATION_NAME` to the name of your project, `OPT_IN_YES` to the string that corresponds to the `Yes` option in the `Opt in?` question, and `OPT_IN_NO` to the string that corresponds to the `No` option in the `Opt in?` question.

1. Set up `message.txt`.

    This is the body of the email that will be sent to each person in `PersonList.txt`. The string `{GroupList}` must appear exactly once in the file; it will be replaced with the list of people that were randomly grouped together.

1. Run `python MealBot.py`.

    There are a number of options (run `MealBot.py -h` to see them).
