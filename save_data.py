import asyncio,tempfile, requests, json, aiohttp,pandas as pd, sys,os.path,re,numpy

BASE_URL = None
ACCESS_TOKEN = None

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
        url_teams = [f"{BASE_URL}api/v1/teams/{int(team_id)}" for team_id in teams]
        
        async with aiohttp.ClientSession() as session:
            task_teams = [fetch_data(session, url) for url in url_teams]
            results_teams = await asyncio.gather(*task_teams)
            
            for count,team in enumerate(teams):
                if not results_teams[count]['success']:
                    continue

                results_team_dict[int(team)]={'score':results_teams[count]['data']['score'],'no_teammates':len(results_teams[count]['data']['members'])}

        return results_user_dict, results_team_dict

    return asyncio.run(main())


def main(): 
    ctfd_users = get_data_from_ctfd()
    ctfd_user_solves, ctfd_team_solves = get_user_team_stats(ctfd_users)

    ctfd_users.to_csv("users.csv",index=False)
    
    with open("user_solves.json",'w') as f:
        f.write(json.dumps(ctfd_user_solves))
        f.close()

    with open('ctf_team_solves.json','w') as f:
        f.write(json.dumps(ctfd_team_solves))
        f.close()

    print("Done! Saved as users.csv, user_solves.json and ctf_team_solves.json")

if __name__ =="__main__":
    # Setup environment

    if len(sys.argv) !=3:
        raise RuntimeError("Must be in the form:\n\r\t" \
        "python3 save_data.py <URL_TO_CTF> <PATH_OF_TOKEN>")

    BASE_URL = sys.argv[1] if sys.argv[1][-1] =='/' else sys.argv[1]+'/'

    if not os.path.exists(sys.argv[2]):
        raise FileNotFoundError("Token File doesn't exist")
    
    with open(sys.argv[2],"r") as f:
        ACCESS_TOKEN = f.readline()

    main()