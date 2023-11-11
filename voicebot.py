import streamlit as st
from bokeh.models.widgets import Button
from bokeh.models import CustomJS

from apiclient.discovery import build
import pickle
import datetime

from streamlit_bokeh_events import streamlit_bokeh_events

from gtts import gTTS
from io import BytesIO
import openai

credentials = pickle.load(open("token.pickle", "rb"))
service = build("calendar", "v3", credentials=credentials)

calendar_user = service.calendarList().list().execute()
timeZone = calendar_user['items'][1]['timeZone']
calendar_id = calendar_user['items'][1]['id']

result = service.events().list(calendarId=calendar_id, timeZone=timeZone).execute()

events = []
for event in result['items']:
    dic = {}
    if 'summary' in event.keys():
        dic['summary'] = event['summary']
        dic['start'] = event['start']
        dic['end'] = event['end']
        events.append(dic)

openai.organization = "Your organization"
openai.api_key = 'Your key'

current_time = datetime.datetime.now()
sample_event = {
  'summary': 'Dentist Appointment',
  'location': 'Arlington',
  'description': 'Appointment with Dr.Schmidt',
  'start': {
    'dateTime': datetime.datetime(2023, 8, 14, 16, 30, 0).strftime("%Y-%m-%dT%H:%M:%S"),
    'timeZone': 'America/New_York',
  },
  'end': {
    'dateTime': datetime.datetime(2023, 8, 14, 19, 30, 0).strftime("%Y-%m-%dT%H:%M:%S"),
    'timeZone': 'America/New_York',
  },
  'reminders': {
    'useDefault': False,
    'overrides': [
      {'method': 'email', 'minutes': 24 * 60},
      {'method': 'popup', 'minutes': 10},
    ],
  },
}
HLT_prompt = [
    {'role':'system', 'content':
     f"""
     The current time is {current_time}. \
     The user's time zone is {timeZone}. \
     You are a chatbot assistant who helps user arrange their schedules and help the system create events in Google Calendar. \
     Remember, location and description are optional. \
     Do not ask for unnecessary information that the user did not mention. \
     When you have made decisions, ask the user to confirm. \
     After the user's approval, generate dictionaries for each event in the format of the following example, and output them in a python list format: \
     
     ```
     {sample_event}
     ```
     The output should be a list even if there is only one event. \
     The code in the output should be in the python code format which starts with "```python".
     
     """
    },
    {'role':'system', 'content':
     f"""
     Here are the user's events on the calendar:
     
     ```
     {events}
     ```
     """
    }
]

if 'prompts' not in st.session_state:
    st.session_state['prompts'] = HLT_prompt

def generate_response(prompt):

    st.session_state['prompts'].append({"role": "user", "content":prompt})
    completion=openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages = st.session_state['prompts']
    )
    
    message=completion.choices[0].message.content
    return message

sound = BytesIO()

placeholder = st.container()

placeholder.title("HLT ChatBot")
stt_button = Button(label='SPEAK', button_type='success', margin = (5, 5, 5, 5), width=200)


stt_button.js_on_event("button_click", CustomJS(code="""
    var value = "";
    var rand = 0;
    var recognition = new webkitSpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = 'en';

    document.dispatchEvent(new CustomEvent("GET_ONREC", {detail: 'start'}));
    
    recognition.onspeechstart = function () {
        document.dispatchEvent(new CustomEvent("GET_ONREC", {detail: 'running'}));
    }
    recognition.onsoundend = function () {
        document.dispatchEvent(new CustomEvent("GET_ONREC", {detail: 'stop'}));
    }
    recognition.onresult = function (e) {
        var value2 = "";
        for (var i = e.resultIndex; i < e.results.length; ++i) {
            if (e.results[i].isFinal) {
                value += e.results[i][0].transcript;
                rand = Math.random();
                
            } else {
                value2 += e.results[i][0].transcript;
            }
        }
        document.dispatchEvent(new CustomEvent("GET_TEXT", {detail: {t:value, s:rand}}));
        document.dispatchEvent(new CustomEvent("GET_INTRM", {detail: value2}));

    }
    recognition.onerror = function(e) {
        document.dispatchEvent(new CustomEvent("GET_ONREC", {detail: 'stop'}));
    }
    recognition.start();
    """))

def extract(text):
    start_index = text.find("```python") + len("```python")
    end_index = text.find("```", start_index)

    code = text[start_index:end_index]
    code = code.replace("\n", "")
    return code

result = streamlit_bokeh_events(
    bokeh_plot = stt_button,
    events="GET_TEXT,GET_ONREC,GET_INTRM",
    key="listen",
    refresh_on_update=False,
    override_height=75,
    debounce_time=0)

tr = st.empty()

if 'input' not in st.session_state:
    st.session_state['input'] = dict(text='', session=0)

tr.text_area("**Your input**", value=st.session_state['input']['text'])

if result:
    if "GET_TEXT" in result:
        if result.get("GET_TEXT")["t"] != '' and result.get("GET_TEXT")["s"] != st.session_state['input']['session'] :
            st.session_state['input']['text'] = result.get("GET_TEXT")["t"]
            tr.text_area("**Your input**", value=st.session_state['input']['text'])
            st.session_state['input']['session'] = result.get("GET_TEXT")["s"]

    if "GET_INTRM" in result:
        if result.get("GET_INTRM") != '':
            tr.text_area("**Your input**", value=st.session_state['input']['text']+' '+result.get("GET_INTRM"))

    if "GET_ONREC" in result:
        if result.get("GET_ONREC") == 'start':
            placeholder.image("Ikari.jpg", width=80)
            st.session_state['input']['text'] = ''
        elif result.get("GET_ONREC") == 'running':
            placeholder.image("Ikari.jpg", width=80)
        elif result.get("GET_ONREC") == 'stop':
            placeholder.image("Ikari.jpg", width=80)
            if st.session_state['input']['text'] != '':
                input = st.session_state['input']['text']
                output = generate_response(input)
                if "```python" in output:
                    list_of_events = extract(output)
                    eventlist = eval(list_of_events)
                    if type(eventlist) == dict:
                        service.events().insert(calendarId=calendar_id, body=eventlist).execute()
                    else:
                        for event in eventlist:
                            service.events().insert(calendarId=calendar_id, body=event).execute()
                    output = "You're all set!"
                st.write("**ChatBot:**")
                st.write(output)
                st.session_state['input']['text'] = ''

                tts = gTTS(output, lang='en', tld='com')
                tts.write_to_fp(sound)
                st.audio(sound)

                st.session_state['prompts'].append({"role": "user", "content":input})
                st.session_state['prompts'].append({"role": "assistant", "content":output})
