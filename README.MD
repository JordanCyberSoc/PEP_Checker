# CTF PEP Checker

## How to Use
### Setting up the Environment
1. Clone the repository using:
  `git clone `
2. Change into the repository's directory
3. Create and activate a virtual environment
    a. You can find more information about this [here](https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/)
4. Install the script's dependencies using
    `pip install -r requirements.txt`
### Setting up the Google Form for Processing
5. In google forms, create a spreadsheet of the data collected by clicking on *Link to sheets* in the form's settings.
6. In the spreadsheet change the respective column names for Full Name, UniKey, Student Number and Email to Full Name, UniKey, Student Number and Email
7. Export the spreadsheet as a csv.
### Getting a REST API KEY from CTFD
8. Get a CTFD API key by following these [steps](https://docs.ctfd.io/docs/api/getting-started/#generating-an-admin-access-token
9. Once you have received the key save it in a file
### Running the program
10. Run the program with the following arguments:
    `python3 CTFD_sol.py <URL_TO_CTF> <PATH_OF_TOKEN> <PATH_OF_GOOGLE_FORM> <NO_SOLVES> <EXP_TEAM_POINTS>`

11. If ran successfully a file called PEP.csv will be generated
