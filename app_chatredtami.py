import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# 1. Setup Google Sheets Connection
def get_google_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    return client.open("Web Chat Red TAMI Data")

sheet = get_google_sheet()
questions_tab = sheet.worksheet("Questions")
answers_tab = sheet.worksheet("Answers")

# 2. Fetch questions dynamically
questions = questions_tab.col_values(1)[1:]  # Column A, skipping row 1 header
jump_logics = questions_tab.col_values(2)[1:]  # Column B, skipping row 1 header

# 3. Helper Function to Parse Jump Logic
def get_next_index(current_index, user_answer):
    if current_index >= len(jump_logics):
        return current_index + 1
        
    logic_string = str(jump_logics[current_index]).strip()
    if not logic_string or logic_string.lower() == "none":
        return current_index + 1  # Advance normally
        
    clean_answer = user_answer.strip().lower()
    rules = logic_string.split(";")
    for rule in rules:
        if "->" in rule:
            trigger, target = rule.split("->")
            if trigger.strip().lower() == clean_answer:
                return int(target.strip()) - 1  # Row to 0-based Python index
                
    return current_index + 1  # Fallback

# Helper to extract available options from JumpLogic string (e.g., "Yes->3; No->4" -> ["Yes", "No"])
def get_options_for_question(index):
    if index >= len(jump_logics) or index < 0:
        return []
    logic_string = str(jump_logics[index]).strip()
    if not logic_string or "->" not in logic_string:
        return []
    
    options = []
    rules = logic_string.split(";")
    for rule in rules:
        if "->" in rule:
            trigger, _ = rule.split("->")
            options.append(trigger.strip())
    return options

# 4. Initialize Session States
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_q_index" not in st.session_state:
    st.session_state.current_q_index = -1  # Waiting for User ID
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}  # Map index -> Answer string
if "survey_complete" not in st.session_state:
    st.session_state.survey_complete = False

st.title("💬 Google Sheets Survey Chatbot")

# Show initial greeting asking for ID
if not st.session_state.messages:
    st.session_state.messages.append({"role": "assistant", "content": "Welcome to the Red TAMI Chat. Please enter your **User ID** or **Name** to begin:"})

# Render existing chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# Variable to hold input from either source
incoming_input = None

# 5. Render Dynamic Buttons if applicable
if not st.session_state.survey_complete and st.session_state.current_q_index != -1:
    options = get_options_for_question(st.session_state.current_q_index)
    if options:
        st.write("---")
        # Display options side-by-side using Streamlit columns
        cols = st.columns(len(options))
        for idx, option in enumerate(options):
            if cols[idx].button(option, use_container_width=True):
                incoming_input = option  # Set input via button click

# 6. Handle User Input (either from Chat Bar or Buttons)
if not st.session_state.survey_complete:
    chat_bar_input = st.chat_input("Type here...")
    
    # Prioritize button inputs over the text entry box
    user_input = incoming_input if incoming_input else chat_bar_input

    if user_input:
        with st.chat_message("user"):
            st.write(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        # PHASE 1: Capture User ID
        if st.session_state.current_q_index == -1:
            st.session_state.user_id = user_input
            st.session_state.current_q_index = 0
            
            first_q = questions[0]
            bot_response = f"Thank you, **{st.session_state.user_id}**. Your ID has been securely registered.\n\n**Question 1:** {first_q}"
            
            with st.chat_message("assistant"):
                st.write(bot_response)
            st.session_state.messages.append({"role": "assistant", "content": bot_response})
            st.rerun()
            
        # PHASE 2: Capture Survey Answers
        else:
            # Save the answer mapped directly to its sequential index position
            st.session_state.user_answers[st.session_state.current_q_index] = user_input
            
            # Determine next destination question index
            next_index = get_next_index(st.session_state.current_q_index, user_input)
            st.session_state.current_q_index = next_index
            
            # Check if there are more questions remaining
            if st.session_state.current_q_index < len(questions):
                next_q = questions[st.session_state.current_q_index]
                bot_response = f"Got it, **{st.session_state.user_id}**.\n\n**Question {st.session_state.current_q_index + 1}:** {next_q}"
                
                with st.chat_message("assistant"):
                    st.write(bot_response)
                st.session_state.messages.append({"role": "assistant", "content": bot_response})
                st.rerun()
            else:
                # SURVEY FINISHED: Build and write final row instantly
                st.session_state.survey_complete = True
                
                final_row = [st.session_state.user_id]
                for i in range(len(questions)):
                    final_row.append(st.session_state.user_answers.get(i, ""))
                
                try:
                    answers_tab.append_row(final_row)
                    bot_response = f"Thank you, **{st.session_state.user_id}**! You have successfully completed the survey. Your profile data has been logged."
                except Exception as gspread_err:
                    bot_response = f"Survey ended, but Google Sheets API rejected the save: {gspread_err}"
                
                with st.chat_message("assistant"):
                    st.write(bot_response)
                st.session_state.messages.append({"role": "assistant", "content": bot_response})
                st.rerun()
else:
    st.success("Survey finished! Refresh the page to submit another user response.")