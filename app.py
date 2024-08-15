import streamlit as st
import json
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import csv

# Initialize Firebase Admin SDK
def initialize_firebase():
    # cred = credentials.Certificate("/home/maojia/work/hallucination_app/hallucination-human-eval-firebase-adminsdk-u77sb-82eeb9f363.json")
    service_account_info = {
        "type": st.secrets["firebase"]["type"],
        "project_id": st.secrets["firebase"]["project_id"],
        "private_key_id": st.secrets["firebase"]["private_key_id"],
        "private_key": st.secrets["firebase"]["private_key"].replace("\\n", "\n"),
        "client_email": st.secrets["firebase"]["client_email"],
        "client_id": st.secrets["firebase"]["client_id"],
        "auth_uri": st.secrets["firebase"]["auth_uri"],
        "token_uri": st.secrets["firebase"]["token_uri"],
        "auth_provider_x509_cert_url": st.secrets["firebase"]["auth_provider_x509_cert_url"],
        "client_x509_cert_url": st.secrets["firebase"]["client_x509_cert_url"]
    }
    if not firebase_admin._apps:
        cred = credentials.Certificate(service_account_info)
        firebase_admin.initialize_app(cred)
    return firestore.client()

# Initialize Firestore
db = initialize_firebase()

def escape_markdown(text):
    import re
    escape_chars = r'([\[\](){}*+?.\\^$|#])'
    return re.sub(escape_chars, r'\\\1', text)

def load_data():
    with open('output.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

def split_into_chunks(lst, chunk_size):
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]

def save_responses_to_firestore(responses, form_number, code, name):
    collection_ref = db.collection(f'form_{name}_responses')
    for question, response in responses.items():
        doc_ref = collection_ref.document()
        doc_ref.set({
            'timestamp': datetime.now().isoformat(),
            'question_set': code,
            'rater': name,
            'question': question,
            'response': response
        })


# Define codes that map to each form
code_to_form = {
    "1": 1,
    "2": 2,
    "3": 3,
    "4": 4
}

def main():
    st.set_page_config(
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)
    st.title("Hallucination Human Evaluation")

    multi = """
    Thank you for participating in this human evaluation! Please review the instructions before beginning:

    1. This survey includes 8 samples. It should take no more than 30 minutes to complete.
    2. For each sample, you will see 2 answers from different models. Your task is to rate each answer based on how well it addresses the question using the provided documents.
    3. Use the following scale to rate each item:
    
        **5** – Strongly Agree  
        **4** – Agree  
        **3** – Neutral  
        **2** – Disagree  
        **1** – Strongly Disagree
    4. The answer should be based on the information provided in the documents. If the documents do not have enough information to answer the question, a refusal is a valid response.
    5. Please enter your name and the access code provided by Shang Hong in the fields below.

    Thank you for your participation!
    """
    st.markdown(multi)


    # Prompt the user to enter their code
    name = st.text_input("Enter your name:")
    code = st.text_input("Enter your access code:")

    if code:
        # Validate the code
        form_number = code_to_form.get(code.upper())

        if form_number:
            st.success(f"Access granted to Form {form_number}")
            display_form(form_number, code, name)
        else:
            st.error("Invalid code. Please enter a valid access code.")
    else:
        st.info("Please enter your access code to access the survey.")

def display_form(form_number, code, name):
    # Display the specific form based on form_number
    st.header(f"Set {form_number}")

    data = load_data()
    chunk_size = 8
    forms = list(split_into_chunks(data, chunk_size))  # List of 4 lists

    # Retrieve questions for the selected form
    form_index = form_number - 1  # Adjust for zero-based indexing
    form_questions = forms[form_index]  # List of 15 questions for the selected form
    with st.form(key=f'form_{form_number}'):
        responses = {}
        for i, sample in enumerate(form_questions):
            st.subheader(f"Sample {i + 1}: Please read the sample and answer the following questions carefully.")
            st.markdown(f"**Question:** \"{escape_markdown(sample['question'])}\"")
            st.markdown("**Documents:**")
            for idx, doc in enumerate(sample['docs']):
                st.markdown(f"- **Document [{idx + 1}]** (Title: {escape_markdown(doc['title'])}): {escape_markdown(doc['text'])}")

            likert_options = ["5 - Strongly Disagree", "4 - Disagree", "3 - Neutral", "2 - Agree", "1 - Strongly Agree"]

            # First question
            st.markdown(f"**Answer 1:** \"{sample['llama3_answer']}\"")
            # st.markdown("To what extent do you agree that the answer addresses the question using the given documents? The answer should follow the information provided in the documents. Note that if the documents do not contain sufficient information to answer the question, a refusal is a valid response. Please rate your answer on a scale of 1-5:")
            llama3_answer = st.radio(f"To what extent do you agree that the answer addresses the question using the given documents? The answer should follow the information provided in the documents. Note that if the documents do not contain sufficient information to answer the question, a refusal is a valid response. Please rate your answer on a scale of 1-5:", likert_options, index=None, key=f"response1_{i}")

            # Second question
            st.markdown(f"**Answer 2:** \"{sample['gpt35_answer']}\"")
            # st.markdown("")
            gpt35_answer = st.radio(f"To what extent do you agree that the answer addresses the question using the given documents? The answer should follow the information provided in the documents. Note that if the documents do not contain sufficient information to answer the question, a refusal is a valid response. Please rate your answer on a scale of 1-5:", likert_options, index=None, key=f"response2_{i}")

            st.write("---")  # Separator between samples
            responses[f"{sample['label']}"] = {"llama3_answer": llama3_answer, "gpt35_answer": gpt35_answer}

        # Submit button
        submitted = st.form_submit_button("Submit")

        if submitted:
            # Check for unanswered questions
            unanswered_questions = [q for q, r in responses.items() if r is None]
            if unanswered_questions:
                st.error("Please answer all questions before submitting the form.")
            else:
                st.success("Thank you for completing the survey!")
                save_responses_to_firestore(responses, form_number, code, name)
                # Display responses (for demonstration purposes)
                st.write("Your responses:")
                for q, r in responses.items():
                    st.write(f"{q}: {r}")

if __name__ == "__main__":
    main()
