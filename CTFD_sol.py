import asyncio,tempfile, requests, json, aiohttp,pandas as pd, sys,os.path,re,numpy
from halo import Halo

BASE_URL = None
ACCESS_TOKEN = None
TEAM_REQ_SOLVES=float('inf')
INDIVIDUAL_REQ_SOLVES=float('inf')
GOOGLE_FORM_PATH=None
EXPECTED_TEAM_POINTS=float('inf')

def change_all_entr_col_df_lowercase(df:pd.DataFrame,column:str):
    for i,m in df.iterrows():
        df.loc[i,column] = df.loc[i,column].lower()

def get_data_from_ctfd(): 
    # Send request to ctfd server to get user data
    spinner_user = Halo(text=f'Getting users from {BASE_URL}', spinner='dots')
    spinner_user.start()
    api_endpoint = "/api/v1/exports/raw"
    url = f"{BASE_URL}{api_endpoint}"

    headers = {
        "Authorization": f"Token {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {"type": "csv", "args": {"table": "users"}}
    response = requests.post(url, headers=headers, data=json.dumps(payload))

    # Raise an exception for bad status codes (4xx or 5xx)
    response.raise_for_status()   

    # Create temporary file to read data into the program
    with tempfile.NamedTemporaryFile(delete=False) as fp:
        fp.write(response.content)
        fp.close()
        df = pd.read_csv(fp.name)
        users =df[df["type"]=="user"]
        spinner_user.stop()

        spinner_emails = Halo(text='Lower casing User Emails', spinner='dots')
        spinner_emails.start()
        change_all_entr_col_df_lowercase(users,'email')
        spinner_emails.stop()

        return users
    
def get_user_team_stats(users:pd.DataFrame):
    teams = users['team_id'].unique()
    teams = [int(x) for x in teams if not numpy.isnan(x)]
    async def fetch_data(session, url):
        # Send asynchronous request to url
        headers = {
            "Authorization": f"Token {ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }
        async with session.get(url,headers=headers) as response:
            try:
                data = await response.json()
                return data
            except:
                return {'success':False}

    async def main():
        spinner_user = Halo(text='Fetching user solves', spinner='dots')
        spinner_user.start()
        #setup asynchronous request pool that gets all users
        url_users = [f"{BASE_URL}api/v1/users/{row['id']}/solves" for i,row in users.iterrows()]
        results_user_dict = {}
        results_team_dict = {}

        async with aiohttp.ClientSession() as session:
            task_teams = [fetch_data(session, url) for url in url_users]
            result_users = await asyncio.gather(*task_teams)
            
            count =0
            for i,row in users.iterrows():
                if not result_users[count]['success']:
                    count+=1
                    continue

                results_user_dict[row['id']]=result_users[count]['meta']['count']
                count+=1

        #setup asynchronous request pool that gets all team scores
        spinner_user.stop()

        spinner_teams =Halo(text='Fetching team solves', spinner='dots')
        spinner_teams.start()
        url_teams = [f"{BASE_URL}api/v1/teams/{int(team_id)}" for team_id in teams]
        
        async with aiohttp.ClientSession() as session:
            task_teams = [fetch_data(session, url) for url in url_teams]
            results_teams = await asyncio.gather(*task_teams)
            
            for count,team in enumerate(teams):
                if not results_teams[count]['success']:
                    continue

                results_team_dict[int(team)]={'score':results_teams[count]['data']['score'],'no_teammates':len(results_teams[count]['data']['members'])}
        spinner_teams.stop()

        return results_user_dict, results_team_dict

    return asyncio.run(main())

def get_data_from_google_form():
    # Convert Google form with columns Full Name, UniKey, Student Number and Email to pandas dataframe
    spinner_forms =Halo(text='Reading in google form', spinner='dots')
    spinner_forms.start()
    df = pd.read_csv(GOOGLE_FORM_PATH)

    unikey_email_re=r"^((?:[A-Za-z]{4}[0-9]{4})(?:@uni\.sydney\.edu\.au)?)$" 
    matches =df[df['UniKey'].str.match(unikey_email_re,case=False)]
    """
        For a user John Smith, Check if a unikey is case insensitive and is written in the forms:
        jsmit1234, jsmit1234@uni.sydney.edu.au

    """
    unikey_re = r"([a-zA-Z]{4}[0-9]{4})"
    for i,m in matches.iterrows():
        matches.loc[i,'UniKey']=re.search(unikey_re,matches.loc[i,'UniKey']).group(0)
    spinner_forms.stop()
    change_all_entr_col_df_lowercase(matches,'Email')
    change_all_entr_col_df_lowercase(matches,'UniKey')

    spinner_forms =Halo(text='Cleaning results', spinner='dots')
    spinner_forms.start()
    # Keeps the latest entry based on a user's unikey and deletes any entry with a duplicate email
    keep_latest_unikey= matches.drop_duplicates(subset=['UniKey'],keep='last')
    emails = keep_latest_unikey.drop_duplicates(subset=['Email'],keep=False)
    spinner.stop()
    return emails


def main(): 
    ctfd_users = get_data_from_ctfd()
    ctfd_user_solves, ctfd_team_solves = get_user_team_stats(ctfd_users)
    pep_form = get_data_from_google_form()

    """
        Iterate through all entries of the google form and only write the users with valid accounts in ctfd 
        that have at least <REQ_SOLVES>, with a team score of at least <EXPECTED_TEAM_POINTS>
    """
    new_df = pd.DataFrame(columns=["Name","UniKey","Student Number"])
    count =0
    spinner_filter = Halo(text='Filtering users', spinner='dots')
    spinner_filter.start()
    for index, row in pep_form.iterrows():
        user:pd.DataFrame = ctfd_users[ctfd_users["email"] == row["Email"]]
        if len(user) ==1:
            team_id =user.iloc[0]['team_id']
            if not (team_id in ctfd_team_solves):
                continue

            if ctfd_team_solves[team_id]['no_teammates'] == 1:

                user_id = user.iloc[0]["id"]
                if not (user_id in ctfd_user_solves):
                    continue
                if ctfd_user_solves[user_id] < INDIVIDUAL_REQ_SOLVES:
                    continue
            else:
                if ctfd_team_solves[team_id]['score'] < EXPECTED_TEAM_POINTS:
                    continue

                user_id = user.iloc[0]["id"]
                if not (user_id in ctfd_user_solves):
                    continue
                if ctfd_user_solves[user_id] < TEAM_REQ_SOLVES:
                    continue


            new_df.loc[count] = [row['Full Name'],row["UniKey"],row['Student Number']]
            count+=1
    spinner_filter.stop()
    spinner = Halo(text='Saving files..', spinner='dots')
    spinner.start()
    new_df.to_csv('PEP.csv',index=False)
    new_df.to_excel('PEP.xlsx',index=False)
    spinner.stop()
    print("Done! Saved as PEP.csv and PEP.xlsx")

if __name__ =="__main__":
    spinner = Halo(text='Setting up environment Variables', spinner='dots')
    spinner.start()
    # Setup environment

    if len(sys.argv) !=7:
        raise RuntimeError("Must be in the form:\n\r\t" \
        "python3 CTFD_sol.py <URL_TO_CTF> <PATH_OF_TOKEN> <PATH_OF_GOOGLE_FORM> <NO_TEAM_SOLVES> <EXP_TEAM_POINTS> <NO_INDIVIDUAL_SOLVES> ")

    BASE_URL = sys.argv[1] if sys.argv[1][-1] =='/' else sys.argv[1]+'/'

    if not os.path.exists(sys.argv[2]):
        raise FileNotFoundError("Token File doesn't exist")
    
    with open(sys.argv[2],"r") as f:
        ACCESS_TOKEN = f.readline()

    if not os.path.exists(sys.argv[3]):
        raise FileNotFoundError("Google form file doesn't exist")
    GOOGLE_FORM_PATH = sys.argv[3]    

    if not sys.argv[4].isdigit():
        raise ValueError("<NO_TEAM_SOLVES> needs to be an integer")
    TEAM_REQ_SOLVES=int(sys.argv[4])
    
    if not sys.argv[5].isdigit():
        raise ValueError("<EXP_TEAM_POINTS> needs to be an integer")
    EXPECTED_TEAM_POINTS=int(sys.argv[5])

    if not sys.argv[6].isdigit():
        raise ValueError("<NO_INDIVIDUAL_SOLVES> needs to be an integer")
    INDIVIDUAL_REQ_SOLVES=int(sys.argv[6])
    spinner.stop()

    main()