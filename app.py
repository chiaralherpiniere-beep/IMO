import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, time

st.set_page_config(page_title='IMO Tracker', page_icon='🫧', layout='centered')
API_URL='https://script.google.com/macros/s/AKfycbzPaa18SkJAdojlklTUGTcnm5tUEnHQAsQUhN3gV5u2cC1TXdcpgid3Tp9iUFWw0rIR/exec'
BRISTOL={1:'Separate hard lumps — hard to pass',2:'Sausage-shaped but lumpy',3:'Sausage with cracks',4:'Smooth, soft sausage/snake',5:'Soft blobs with clear-cut edges',6:'Fluffy/ragged, mushy',7:'Watery, no solid pieces'}
SUPPS={
 'Magnesium citrate':('1 scoop','109 mg elemental Mg'),
 'Magnesium glycinate':('1 capsule','75 mg elemental Mg'),
 'Ginger extract':('1 capsule','500 mg extract / 25 mg gingerols'),
 'Allicin':('1 capsule','25 mg allicin'),
 'Other':('','')}
SYMPTOMS=['Brain fog','Fatigue','Histamine-type reaction','POTS / orthostatic symptoms','Dizziness / lightheadedness','Joint pain','Headache','Nausea','Abdominal pain / ache','Bloating / distension']
HIST=['Itching','Flushing','Nasal / sinus pressure','Tinnitus / buzzing','Skin reaction','GI symptoms','Heart-rate / POTS-type response','Other']
ASSIST=['None','Positioning','Abdominal pressure / massage','Manual assistance','Other']

def secret():
    try: return st.secrets['app_secret']
    except Exception:
        st.error('Missing Streamlit secret: app_secret')
        st.stop()

def save_event(event_type, subtype='', value_1='', value_2='', value_3='', details='', notes='', d=None, t=None):
    d=d or date.today(); t=t or datetime.now().time().replace(microsecond=0)
    payload={'secret':secret(),'timestamp':datetime.combine(d,t).isoformat(timespec='seconds'),'date':d.isoformat(),'time':t.strftime('%H:%M:%S'),'event_type':event_type,'subtype':subtype,'value_1':str(value_1),'value_2':str(value_2),'value_3':str(value_3),'details':details,'notes':notes}
    r=requests.post(API_URL,json=payload,timeout=20); r.raise_for_status(); data=r.json()
    if not data.get('ok'): raise RuntimeError(data.get('error','Unknown Apps Script error'))
    st.cache_data.clear()

@st.cache_data(ttl=30)
def load_events():
    r=requests.get(API_URL,params={'secret':secret()},timeout=20); r.raise_for_status(); data=r.json()
    if not data.get('ok'): raise RuntimeError(data.get('error','Unknown Apps Script error'))
    df=pd.DataFrame(data.get('events',[]))
    if not df.empty and 'timestamp' in df: df['timestamp']=pd.to_datetime(df['timestamp'],errors='coerce')
    return df

def dt_inputs(k):
    c1,c2=st.columns(2)
    with c1: d=st.date_input('Date',date.today(),key=k+'d')
    with c2: t=st.time_input('Time',datetime.now().time().replace(second=0,microsecond=0),key=k+'t')
    return d,t

def safe_save(*args,**kwargs):
    try:
        save_event(*args,**kwargs); st.success('Saved to Google Sheets.')
    except Exception as e:
        st.error('Could not save.'); st.code(str(e))

st.title('IMO Tracker')
st.caption('V1 — quick logging, saved directly to Google Sheets')

today,bowel,symptoms,supps,food,sleep,data=st.tabs(['Today','Bowel','Symptoms','Supplements','Meals','Sleep / HRV','Data'])

with today:
    st.subheader('Today')
    try:
        df=load_events(); td=df[df['date'].astype(str)==date.today().isoformat()] if not df.empty and 'date' in df else pd.DataFrame()
        st.metric('Entries today',len(td))
        if len(td):
            for _,r in td.sort_values('timestamp',ascending=False).head(10).iterrows():
                st.write(f"**{r.get('time','')} · {r.get('event_type','')}** — {r.get('subtype','') or r.get('details','')}")
        else: st.info('Nothing logged today yet.')
    except Exception as e: st.error('Could not read Google Sheets.'); st.code(str(e))

with bowel:
    mode=st.radio('What happened?',['Successful bowel movement','Unsuccessful attempt'],horizontal=True)
    if mode.startswith('Successful'):
        d,t=dt_inputs('bm')
        br=st.multiselect('Bristol stool type',list(BRISTOL),format_func=lambda x:f'Type {x} — {BRISTOL[x]}',max_selections=2)
        amount=st.radio('Amount',['Small','Medium','Large'],horizontal=True)
        ease=st.slider('Ease of passing (0 = extremely difficult, 10 = effortless)',0,10,5)
        strain=st.radio('Straining',['None','Mild','Moderate','Significant'],horizontal=True)
        complete=st.radio('Completeness',['Complete','Mostly complete','Incomplete'],horizontal=True)
        urgency=st.radio('Urgency',['None','Normal urge','Strong urgency','Emergency'],horizontal=True)
        assist=st.multiselect('Assistance',ASSIST,default=['None'])
        pain=st.slider('Pain',0,10,0)
        notes=st.text_area('Notes (optional)',key='bmnotes')
        if st.button('Save bowel movement',type='primary'):
            details=f"Bristol={','.join(map(str,br)) or 'NA'}; amount={amount}; ease={ease}/10; straining={strain}; completeness={complete}; urgency={urgency}; assistance={','.join(assist) or 'none'}; pain={pain}/10"
            safe_save('bowel_movement','successful',','.join(map(str,br)),ease,pain,details,notes,d,t)
        with st.expander('Bristol stool chart reminder'):
            for n,v in BRISTOL.items(): st.markdown(f'**Type {n}:** {v}')
    else:
        d,t=dt_inputs('fail')
        urge=st.radio('Was there an urge?',['Yes','No','Unsure'],horizontal=True)
        difficulty=st.slider('Difficulty / effort',0,10,5)
        assist=st.multiselect('Assistance attempted',ASSIST,key='failassist')
        notes=st.text_area('Notes (optional)',key='failnotes')
        if st.button('Save unsuccessful attempt',type='primary'):
            safe_save('bowel_attempt','unsuccessful',urge,difficulty,'',f"urge={urge}; difficulty={difficulty}/10; assistance={','.join(assist) or 'none'}",notes,d,t)

with symptoms:
    st.caption('Unchecked = not assessed. 0 = checked and absent.')
    d,t=dt_inputs('sym')
    overall=st.slider('Overall right now (0 = terrible, 10 = excellent)',0,10,5)
    scores={}
    for s in SYMPTOMS:
        if st.checkbox('Log '+s,key='log_'+s): scores[s]=st.slider(s,0,10,0,key='score_'+s)
    hist=[]
    if 'Histamine-type reaction' in scores: hist=st.multiselect('Histamine-type features',HIST)
    notes=st.text_area('Notes (optional)',key='symnotes')
    if st.button('Save symptom check-in',type='primary'):
        parts=[f'overall={overall}/10']+[f'{k}={v}/10' for k,v in scores.items()]
        if hist: parts.append('histamine_features='+','.join(hist))
        safe_save('symptom_checkin','general',overall,'','', '; '.join(parts),notes,d,t)

with supps:
    d,t=dt_inputs('supp')
    name=st.selectbox('Item',list(SUPPS))
    dose_default,active_default=SUPPS[name]
    dose=st.text_input('Dose taken',value=dose_default,key='dose_'+name)
    active=st.text_input('Active amount / equivalent',value=active_default,key='active_'+name)
    notes=st.text_area('Notes (optional)',key='suppnotes')
    if st.button('Save supplement',type='primary'):
        safe_save('supplement',name,dose,active,'',f'dose={dose}; active={active}',notes,d,t)

with food:
    d,t=dt_inputs('food')
    kind=st.radio('Type',['Meal','Drink','Exposure / trigger','Other'],horizontal=True)
    what=st.text_area('What did you have?',placeholder='e.g. 3 eggs, butter, smoked salmon')
    tags=st.multiselect('Optional tags',['Usual / safe','Restaurant / unknown ingredients','Possible trigger','New food'])
    notes=st.text_area('Notes (optional)',key='foodnotes')
    if st.button('Save meal / exposure',type='primary'):
        safe_save('food_exposure',kind,what,'','',f"tags={','.join(tags)}",notes,d,t)

with sleep:
    d=st.date_input('Date (morning of)',date.today(),key='sleepd')
    hrs=st.number_input('Sleep duration (hours)',0.0,24.0,0.0,0.25)
    hrv=st.number_input('HRV (ms, optional)',0.0,step=1.0)
    rhr=st.number_input('Resting heart rate (bpm, optional)',0.0,step=1.0)
    quality=st.slider('Sleep quality (0–10)',0,10,5)
    notes=st.text_area('Notes (optional)',key='sleepnotes')
    if st.button('Save sleep / HRV',type='primary'):
        safe_save('sleep','morning',hrs,hrv,rhr,f'sleep={hrs}h; HRV={hrv or "NA"}ms; RHR={rhr or "NA"}bpm; quality={quality}/10',notes,d,time(8,0))

with data:
    try:
        df=load_events()
        if df.empty: st.info('No data yet.')
        else:
            st.dataframe(df.sort_values('timestamp',ascending=False),width='stretch')
            st.download_button('Download CSV backup',df.to_csv(index=False).encode('utf-8'),f'imo_tracker_backup_{date.today().isoformat()}.csv','text/csv')
    except Exception as e: st.error('Could not load data.'); st.code(str(e))
