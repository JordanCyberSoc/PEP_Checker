import asyncio,tempfile, requests, json, aiohttp,pandas as pd, sys,os.path,re


BASE_URL = None
ACCESS_TOKEN = None
REQ_SOLVES=4
GOOGLE_FORM_PATH=None

def change_all_entr_col_df_lowercase(df:pd.DataFrame,column:str):
    for i,m in df.iterrows():
        df.loc[i,column] = df.loc[i,column].lower()

def get_data_from_ctfd(): 
    # Send request to ctfd server to get user data
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

        change_all_entr_col_df_lowercase(users,'email')

        return users
    
def get_user_stats(users:pd.DataFrame):
    async def fetch_data(session, url):
        # Send asynchronous request to url
        headers = {
            "Authorization": f"Token {ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }
        async with session.get(url,headers=headers) as response:
            data = await response.json()
            return data

    async def main():
        #setup asynchronous request pool that gets all users
        urls = [f"{BASE_URL}/api/v1/users/{row['id']}/solves" for i,row in users.iterrows()]
        
        async with aiohttp.ClientSession() as session:
            tasks = [fetch_data(session, url) for url in urls]
            results = await asyncio.gather(*tasks)
            
            results_dict = {}
            count =0
            for i,row in users.iterrows():
                if not results[count]['success']:
                    continue

                results_dict[row['id']]=results[count]['meta']['count']
                count+=1

        return results_dict

    return asyncio.run(main())

def get_data_from_google_form():
    # Convert Google form with columns Full Name, UniKey, Student Number and Email to pandas dataframe
    df = pd.read_csv(GOOGLE_FORM_PATH)

    unikey_email_re=r"((?:[A-Za-z]{4}[0-9]{4})(?:@uni\.sydney\.edu\.au)?)$" 
    matches =df[df['UniKey'].str.match(unikey_email_re,case=False)]
    """
        For a user John Smith, Check if a unikey is case insensitive and is written in the forms:
        jsmit1234, jsmit1234@uni.sydney.edu.au

    """
    unikey_re = r"([a-zA-Z]{4}[0-9]{4})"
    for i,m in matches.iterrows():
        matches.loc[i,'UniKey']=re.search(unikey_re,matches.loc[i,'UniKey']).group(0)

    change_all_entr_col_df_lowercase(matches,'Email')

    # Deletes any entry with a duplicate email
    return matches.drop_duplicates(subset=['Email'],keep=False)


def main(): 
    ctfd_users = get_data_from_ctfd()

    ctfd_user_solves = get_user_stats(ctfd_users)

    pep_form = get_data_from_google_form()

    """
        Iterate through all entries of the google form and only write the users with valid accounts in ctfd 
        that have at least <REQ_SOLVES>
    """
    new_df = pd.DataFrame(columns=["Name","UniKey","Student Number"])
    count =0
    for index, row in pep_form.iterrows():
        user:pd.DataFrame = ctfd_users[ctfd_users["email"] == row["Email"]]
        if len(user) ==1:
            id = user.iloc[0]["id"]
            if not (id in ctfd_user_solves):
                continue
            if ctfd_user_solves[id] >= REQ_SOLVES:
                new_df.loc[count] = [row['Full Name'],row["UniKey"],row['Student Number']]
                count+=1
    
    
    new_df.to_csv('PEP.csv',index=False)
    print("Done! Saved as PEP.csv")

if __name__ =="__main__":
    # Setup environment

    if len(sys.argv) !=5:
        raise RuntimeError("Must be in the form:\n\r\t" \
        "python3 CTFD_sol.py <URL_TO_CTF> <PATH_OF_TOKEN> <PATH_OF_GOOGLE_FORM> <NO_SOLVES>")

    BASE_URL = sys.argv[1] if sys.argv[1][-1] =='/' else sys.argv[1]+'/'

    if not os.path.exists(sys.argv[2]):
        raise FileNotFoundError("Token File doesn't exist")
    
    with open(sys.argv[2],"r") as f:
        ACCESS_TOKEN = f.readline()

    if not os.path.exists(sys.argv[3]):
        raise FileNotFoundError("Google form file doesn't exist")
    GOOGLE_FORM_PATH = sys.argv[3]    

    if not sys.argv[4].isdigit():
        raise ValueError("<NO_SOLVES> needs to be an integer")
    
    REQ_SOLVES=int(sys.argv[4])
    main()