from google_auth_oauthlib.flow import InstalledAppFlow
import pickle

scopes = ['https://www.googleapis.com/auth/calendar', 'https://www.googleapis.com/auth/calendar.readonly', 'https://www.googleapis.com/auth/calendar.events', 'https://www.googleapis.com/auth/calendar.events.readonly']

flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", scopes=scopes)

credentials = flow.run_local_server()

pickle.dump(credentials, open("token.pickle", "wb"))
