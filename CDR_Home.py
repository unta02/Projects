import streamlit as st
st.set_page_config(
    page_title="Contract Draft Request Tracker",
    layout="wide"
)

# --- PAGE SETUP ---
CDR_page = st.Page(
    "HomeCDR.py",
    title="About Me",
    icon=":material/account_circle:",
   
)

CDR_page2 = st.Page(
    "CDR_dashboard.py",
    title="About Me2",
    icon=":material/dashboard:",
    
)


# --- NAVIGATION SETUP [WITHOUT SECTIONS] ---
# pg = st.navigation(pages=[about_page, project_1_page, project_2_page])

# --- NAVIGATION SETUP [WITH SECTIONS]---
pg = st.navigation(
    {
        "Info": [CDR_page],
       "Projects": [CDR_page2],
       #"Projects2": [CDR_page3],
    },
   position="hidden"
    
)


# --- SHARED ON ALL PAGES ---
#st.logo("https://media.wtwco.com/-/media/WTW/Logo/Logo_Desktop.svg?iar=0&modified=20220630202346&imgeng=meta_true&hash=56F49BEC51919C8E565A890FBF0C1B85")
#st.sidebar.markdown("Made with ❤️ by [Sven](https://youtube.com/@codingisfun)")


# --- RUN NAVIGATION ---
pg.run()