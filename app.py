import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, time
from zoneinfo import ZoneInfo

st.set_page_config(page_title="IMO Tracker", page_icon="🫧", layout="centered")

APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzPaa18SkJAdojlklTUGTcnm5tUEnHQAsQUhN3gV5u2cC1TXdcpgid3Tp9iUFWw0rIR/exec"
LOCAL_TZ = ZoneInfo("Europe/Berlin")

BRISTOL = {
    1: "Separate hard lumps, like nuts — hard to pass",
    2: "Sausage-shaped but lumpy",
    3: "Like a sausage with cracks on the surface",
    4: "Like a smooth, soft sausage or snake",
    5: "Soft blobs with clear-cut edges",
    6: "Fluffy pieces with ragged edges; mushy",
    7: "Watery, no solid pieces"
}

SUPPLEMENTS = {
    "Magnesium citrate": {"default_amount": 1.0, "active_per_unit": 109.0, "active_label": "mg elemental Mg", "dose_label": "scoop(s)"},
    "Magnesium glycinate": {"default_amount": 1.0, "active_per_unit": 75.0, "active_label": "mg elemental Mg", "dose_label": "capsule(s)"},
    "Ginger extract": {"default_amount": 1.0, "active_per_unit": 25.0, "active_label": "mg gingerols", "dose_label": "capsule(s)", "extra": "500 mg extract per capsule"},
    "Allicin": {"default_amount": 1.0, "active_per_unit": 25.0, "active_label": "mg allicin", "dose_label": "capsule(s)"},
    "Toxaprevent": {"default_amount": 1.0, "active_per_unit": None, "active_label": "", "dose_label": "unit(s)"},
    "Electrolytes": {"default_amount": 1.0, "active_per_unit": None, "active_label": "", "dose_label": "serving(s)"},
    "Other": {"default_amount": 1.0, "active_per_unit": None, "active_label": "", "dose_label": "amount"},
}

SYMPTOMS = [
    "Brain fog", "Fatigue", "Histamine-type reaction", "Itchiness",
    "Congestion / nasal congestion", "Tinnitus", "Bubble over head", "NS glitch",
    "ADHD symptoms", "POTS / orthostatic symptoms", "Dizziness / lightheadedness",
    "Joint pain", "Headache", "Nausea", "Abdominal pain / ache", "Bloating / distension",
]

HISTAMINE_TAGS = [
    "Itching", "Flushing", "Nasal / sinus pressure", "Tinnitus / buzzing",
    "Skin reaction", "GI symptoms", "Heart-rate / POTS-type response", "Other"
]
ASSISTANCE = ["None", "Positioning", "Abdominal pressure / massage", "Manual assistance", "Other"]


def now_local():
    return datetime.now(LOCAL_TZ)


def get_secret():
    try:
        return st.secrets["app_secret"]
    except Exception:
        st.error("Missing Streamlit secret: app_secret")
        st.stop()


def save_event(event_type, subtype="", value_1="", value_2="", value_3="", details="", notes="", event_date=None, event_time=None):
    current = now_local()
    event_date = event_date or current.date()
    event_time = event_time or current.time().replace(microsecond=0)
    local_dt = datetime.combine(event_date, event_time, tzinfo=LOCAL_TZ)
    payload = {
        "secret": get_secret(),
        "timestamp": local_dt.isoformat(timespec="seconds"),
        "date": event_date.isoformat(),
        "time": event_time.strftime("%H:%M:%S"),
        "event_type": event_type,
        "subtype": subtype,
        "value_1": str(value_1),
        "value_2": str(value_2),
        "value_3": str(value_3),
        "details": details,
        "notes": notes,
    }
    r = requests.post(APPS_SCRIPT_URL, json=payload, timeout=20)
    r.raise_for_status()
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(data.get("error", "Unknown Apps Script error"))
    st.cache_data.clear()


@st.cache_data(ttl=30)
def load_events():
    r = requests.get(APPS_SCRIPT_URL, params={"secret": get_secret()}, timeout=20)
    r.raise_for_status()
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(data.get("error", "Unknown Apps Script error"))
    rows = data.get("events", [])
    if not rows:
        return pd.DataFrame(columns=["timestamp", "date", "time", "event_type", "subtype", "value_1", "value_2", "value_3", "details", "notes"])
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    return df


def timestamp_inputs(key_prefix):
    current = now_local()
    c1, c2 = st.columns(2)
    with c1:
        d = st.date_input("Date", value=current.date(), key=f"{key_prefix}_date")
    with c2:
        t = st.time_input("Time", value=current.time().replace(second=0, microsecond=0), key=f"{key_prefix}_time")
    return d, t


st.title("IMO Tracker")
st.caption("V1.2 — final logging build")

tab_today, tab_bm, tab_symptoms, tab_supps, tab_food, tab_morning, tab_data = st.tabs(
    ["Today", "Bowel", "Symptoms", "Supplements", "Meals", "Measurements", "Data"]
)

with tab_today:
    st.subheader("Today")
    try:
        df = load_events()
        today_str = now_local().date().isoformat()
        if df.empty:
            st.info("No entries yet.")
        else:
            today_df = df[df["date"].astype(str) == today_str].copy()
            st.metric("Entries today", len(today_df))
            if not today_df.empty:
                today_df = today_df.sort_values("timestamp", ascending=False)
                for _, r in today_df.head(12).iterrows():
                    st.write(f"**{r.get('time','')} · {r.get('event_type','')}** — {r.get('subtype','') or r.get('details','')}")
            else:
                st.caption("Nothing logged today yet.")
    except Exception as e:
        st.error("Could not read the Google Sheet.")
        st.code(str(e))

with tab_bm:
    st.subheader("Bowel movement")
    mode = st.radio("What happened?", ["Successful bowel movement", "Unsuccessful attempt"], horizontal=True)
    if mode == "Successful bowel movement":
        with st.form("bm_success", clear_on_submit=True):
            d, t = timestamp_inputs("bm_ok")
            bristol = st.multiselect("Bristol stool type", options=list(BRISTOL.keys()), format_func=lambda x: f"Type {x} — {BRISTOL[x]}", max_selections=2)
            amount = st.radio("Amount", ["Small", "Medium", "Large"], horizontal=True)
            ease = st.slider("Ease of passing (0 = extremely difficult, 10 = effortless)", 0, 10, 5)
            straining = st.radio("Straining", ["None", "Mild", "Moderate", "Significant"], horizontal=True)
            completeness = st.radio("Completeness", ["Complete", "Mostly complete", "Incomplete"], horizontal=True)
            urgency = st.radio("Urgency", ["None", "Normal urge", "Strong urgency", "Emergency"], horizontal=True)
            assistance = st.multiselect("Assistance", ASSISTANCE, default=["Positioning"])
            pain = st.slider("Pain", 0, 10, 0)
            gas = st.slider("Gas (0 = none, 10 = extreme)", 0, 10, 0)
            notes = st.text_area("Notes (optional)", placeholder="Colour, mucus, felt better afterwards…")
            submit = st.form_submit_button("Save bowel movement", type="primary")
            if submit:
                details = (f"Bristol={','.join(map(str, bristol)) or 'not recorded'}; amount={amount}; ease={ease}/10; "
                           f"straining={straining}; completeness={completeness}; urgency={urgency}; "
                           f"assistance={','.join(assistance) or 'none'}; pain={pain}/10; gas={gas}/10")
                try:
                    save_event("bowel_movement", "successful", value_1=','.join(map(str, bristol)), value_2=ease, value_3=pain,
                               details=details, notes=notes, event_date=d, event_time=t)
                    st.success("Saved to Google Sheets ✓")
                except Exception as e:
                    st.error("Could not save.")
                    st.code(str(e))
    else:
        with st.form("bm_failed", clear_on_submit=True):
            d, t = timestamp_inputs("bm_fail")
            urge = st.radio("Was there an urge?", ["Yes", "No", "Unsure"], horizontal=True)
            difficulty = st.slider("Difficulty / effort", 0, 10, 5)
            gas = st.slider("Gas (0 = none, 10 = extreme)", 0, 10, 0)
            assistance = st.multiselect("Assistance attempted", ASSISTANCE, default=["Positioning"])
            notes = st.text_area("Notes (optional)")
            submit = st.form_submit_button("Save unsuccessful attempt", type="primary")
            if submit:
                details = f"urge={urge}; difficulty={difficulty}/10; gas={gas}/10; assistance={','.join(assistance) or 'none'}"
                try:
                    save_event("bowel_attempt", "unsuccessful", value_1=urge, value_2=difficulty,
                               details=details, notes=notes, event_date=d, event_time=t)
                    st.success("Saved to Google Sheets ✓")
                except Exception as e:
                    st.error("Could not save.")
                    st.code(str(e))

with tab_symptoms:
    st.subheader("Daily symptom check-in")
    st.caption("Score every symptom 0–10. Zero means checked and absent.")
    with st.form("symptoms_form", clear_on_submit=False):
        d, t = timestamp_inputs("sym")
        overall = st.slider("Overall right now (0 = terrible, 10 = excellent)", 0, 10, 5)
        scores = {symptom: st.slider(symptom, 0, 10, 0, key=f"score_{symptom}") for symptom in SYMPTOMS}
        notes = st.text_area("Notes (optional)")
        if st.form_submit_button("Save symptom check-in", type="primary"):
            details = "; ".join([f"overall={overall}/10"] + [f"{k}={v}/10" for k,v in scores.items()])
            try:
                save_event("symptom_checkin","daily",value_1=overall,details=details,notes=notes,event_date=d,event_time=t)
                st.success("Saved to Google Sheets ✓")
            except Exception as e:
                st.error("Could not save."); st.code(str(e))

with tab_supps:
    st.subheader("Supplement / medication")
    d, t = timestamp_inputs("supp")
    name = st.selectbox("Item", list(SUPPLEMENTS.keys()), key="supp_item")
    preset = SUPPLEMENTS[name]
    if name == "Other":
        custom_name = st.text_input("Name")
        amount_text = st.text_input("Dose taken")
        active_text = st.text_input("Active amount / equivalent (optional)")
        notes = st.text_area("Notes (optional)", key="supp_notes_other")
        if st.button("Save supplement", type="primary", key="save_other_supp"):
            try:
                save_event("supplement", custom_name or "Other", value_1=amount_text, value_2=active_text,
                           details=f"dose={amount_text}; active={active_text}", notes=notes, event_date=d, event_time=t)
                st.success(f"{custom_name or 'Other'} saved.")
            except Exception as e:
                st.error("Could not save.")
                st.code(str(e))
    else:
        step = 0.5 if name == "Magnesium citrate" else 1.0
        amount = st.number_input(f"Amount ({preset['dose_label']})", min_value=0.0,
                                 value=float(preset["default_amount"]), step=step, key=f"amount_{name}")
        if preset["active_per_unit"] is not None:
            active_total = amount * preset["active_per_unit"]
            active_display = f"{active_total:g} {preset['active_label']}"
            st.info(f"Calculated active amount: **{active_display}**")
            if preset.get("extra"):
                st.caption(preset["extra"])
        else:
            active_display = st.text_input("Dose details (optional)", key=f"active_free_{name}")
        notes = st.text_area("Notes (optional)", key=f"supp_notes_{name}")
        if st.button("Save supplement", type="primary", key=f"save_{name}"):
            try:
                save_event("supplement", name, value_1=f"{amount:g} {preset['dose_label']}", value_2=active_display,
                           details=f"dose={amount:g} {preset['dose_label']}; active={active_display}", notes=notes,
                           event_date=d, event_time=t)
                st.success("Saved to Google Sheets ✓")
            except Exception as e:
                st.error("Could not save.")
                st.code(str(e))

with tab_food:
    st.subheader("Meal / exposure")
    with st.form("food_form", clear_on_submit=True):
        d, t = timestamp_inputs("food")
        kind = st.radio("Type", ["Meal", "Drink", "Exposure / trigger", "Other"], horizontal=True)
        what = st.text_area("What did you have?", placeholder="e.g. 3 eggs, butter, smoked salmon")
        tags = st.multiselect("Optional tags", ["Usual / safe", "Restaurant / unknown ingredients", "Possible trigger", "New food"])
        dao = st.checkbox("DAO enzyme taken with this meal / exposure")
        notes = st.text_area("Notes (optional)")
        submit = st.form_submit_button("Save meal / exposure", type="primary")
        if submit:
            details = f"tags={','.join(tags)}; DAO={'yes' if dao else 'no'}"
            try:
                save_event("food_exposure", kind, value_1=what, value_2="DAO" if dao else "", details=details, notes=notes,
                           event_date=d, event_time=t)
                st.success("Saved to Google Sheets ✓")
            except Exception as e:
                st.error("Could not save.")
                st.code(str(e))

with tab_morning:
    st.subheader("Measurements")
    mode = st.radio("What are you logging?", ["Sleep / HRV", "Bloods / ketosis"], horizontal=True)
    if mode == "Sleep / HRV":
        with st.form("sleep_hrv", clear_on_submit=True):
            d, t = timestamp_inputs("sleep")
            sleep = st.number_input("Sleep duration (hours, optional)",0.0,24.0,step=0.25)
            hrv = st.number_input("HRV (ms, optional)",min_value=0.0,step=1.0)
            rhr = st.number_input("Resting heart rate (bpm, optional)",min_value=0.0,step=1.0)
            quality = st.slider("Sleep quality (0–10)",0,10,5)
            notes=st.text_area("Notes (optional)")
            if st.form_submit_button("Save sleep / HRV",type="primary"):
                details=f"sleep={sleep or 'NA'}h; HRV={hrv or 'NA'}ms; RHR={rhr or 'NA'}bpm; quality={quality}/10"
                try:
                    save_event("sleep_hrv","measurement",sleep,hrv,rhr,details,notes,d,t); st.success("Saved to Google Sheets ✓")
                except Exception as e: st.error("Could not save."); st.code(str(e))
    else:
        with st.form("bloods", clear_on_submit=True):
            d,t=timestamp_inputs("blood")
            glucose=st.number_input("Glucose (mmol/L)",min_value=0.0,step=0.1,format="%.1f")
            ketones=st.number_input("Ketones (mmol/L)",min_value=0.0,step=0.1,format="%.1f")
            gki=glucose/ketones if glucose>0 and ketones>0 else None
            if gki is not None: st.info(f"Calculated GKI: **{gki:.2f}**")
            notes=st.text_area("Notes (optional)")
            if st.form_submit_button("Save bloods / ketosis",type="primary"):
                gt=f"{gki:.2f}" if gki is not None else "NA"
                details=f"glucose={glucose or 'NA'}mmol/L; ketones={ketones or 'NA'}mmol/L; GKI={gt}"
                try:
                    save_event("bloods_ketosis","measurement",glucose,ketones,gt,details,notes,d,t); st.success("Saved to Google Sheets ✓")
                except Exception as e: st.error("Could not save."); st.code(str(e))

with tab_data:
    st.subheader("Raw data")
    try:
        df = load_events()
        if df.empty:
            st.info("No data yet.")
        else:
            st.dataframe(df.sort_values("timestamp", ascending=False), width="stretch")
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("Download CSV backup", data=csv,
                               file_name=f"imo_tracker_backup_{now_local().date().isoformat()}.csv", mime="text/csv")
            st.caption("The Google Sheet is the primary persistent store. CSV is optional backup.")
    except Exception as e:
        st.error("Could not load data.")
        st.code(str(e))
