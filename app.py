import nltk
nltk.download('punkt_tab')

import streamlit as st
import json
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import csv
from nltk import sent_tokenize
import re
from fuzzywuzzy import fuzz
import string

REJECTION_FUZZ_THRESHOLD=85
REJECTION_FLAG="I apologize, but I couldn't find an answer"

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

def load_raw_data():
    with open('human_eval_asqa_mix.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

def save_responses_to_firestore(responses, form_number, code, name):
    collection_ref = db.collection(f'{name}_{code}')
    for question, response in responses.items():
        doc_ref = collection_ref.document()
        doc_ref.set({
            'timestamp': datetime.now().isoformat(),
            'question_set': code,
            'rater': name,
            'question': question,
            'response': response
        })

def normalize_answer(s):
    def remove_articles(text):
        return re.sub(r"\b(a|an|the)\b", " ", text)

    def white_space_fix(text):
        return " ".join(text.split())

    def remove_punc(text):
        exclude = set(string.punctuation)
        return "".join(ch for ch in text if ch not in exclude)

    def lower(text):
        return text.lower()

    return white_space_fix(remove_articles(remove_punc(lower(s))))

# Define codes that map to each form
code_to_form = { "1": 1, "2": 2, "3": 3, "4": 4}

def main():
    st.set_page_config(page_icon="🔬",
                       layout="wide",
                       initial_sidebar_state="expanded")
    st.title("Hallucination Human Evaluation")

    multi = """
    Thank you for participating in this human evaluation! Please review the instructions before beginning:

    1. This survey includes 25 samples. It should take no more than 60 minutes to complete.
    2. For each sample, you will see two different responses to the question. Your task is to rate each answer based on how well it addresses the question using the provided documents.
    3. The answer should be based on the information provided in the documents. If the documents do not have enough information to answer the question, a refusal is a valid response.
    4. Full support: all of the information in the statement is supported by the citation. Partial support: some of the information in the statement is supported by the citation, but other parts are not supported (e.g., missing or contradictory). No support: the citation does not support any part of the statement (e.g., the cited webpage is completely irrelevant or contradictory).
    4. Please enter your name and the access code provided in the fields below.

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
            st.success(f"Access granted to set #{form_number}")
            display_form(form_number, code, name)
        else:
            st.error("Invalid code. Please enter a valid access code.")
    else:
        st.info("Please enter your access code to access the survey.")

def get_data(form_number, chunk_size=25):
    raw_data = load_raw_data()

    def split_into_chunks(lst, chunk_size):
        for i in range(0, len(lst), chunk_size):
            yield lst[i:i + chunk_size]
    forms = list(split_into_chunks(raw_data, chunk_size))  # List of 4 lists

    # Retrieve questions for the selected form
    form_index = form_number - 1  # Adjust for zero-based indexing
    form_questions = forms[form_index]  # List of 15 questions for the selected form
    return form_questions

# Display the specific form based on form_number
def display_form(form_number, code, name):
    st.header(f"Set #{form_number}")

    data = get_data(form_number, chunk_size=25)
    
    with st.form(key=f'form_{form_number}'):
        responses = {}
        for i, sample in enumerate(data):
            st.subheader(f"Sample {i + 1}: ")
            
            st.markdown(f"**Question:** \"{escape_markdown(sample['question'])}\"")
            for idx, doc in enumerate(sample['docs']):
                st.markdown(f"- **Document [{idx + 1}]** (Title: {escape_markdown(doc['title'])}): {escape_markdown(doc['text'])}")

            # likert_options = ["5 - Strongly Agree", "4 - Agree", "3 - Neutral", "2 - Disagree", "1 - Strongly Disagree"]
            correctness_options = ["Correct", "Wrong", "Not sure"]
            citation_recall_options = ["Full support", "No support"]
            citation_precision_options = ["Full support", "Partial support", "No support"]

            resps = [sample['GAns'], sample['output']]
            resps_type = ['pos', 'neg']
            
            output = {}
            for resp, resp_type in zip(resps, resps_type):
                output_temp = {}
                st.markdown(f"**Response :** \"{resp}\"")

                correctness_rating = st.radio(f"Given the documents, the response is a correct answer to the question. You should read all five documents first to see if the response could be derived from the documents given. If the response cannot be derived, then it is necessarily also wrong. If it can be derived, then rate whether the response correctly answers the question.", correctness_options, index=None, key=f"correctness_{resp_type}_{i}")
                output_temp['correctness'] = correctness_rating

                is_rejection = fuzz.partial_ratio(normalize_answer(REJECTION_FLAG), normalize_answer(resp)) > REJECTION_FUZZ_THRESHOLD
                if not is_rejection:
                    sentences = sent_tokenize(resp)
                    for sentence in sentences:
                        citation_recall_rating = st.radio(f"{sentence} Does the set of citations support the claim?", citation_recall_options, index=None, key=f"rec_{resp_type}_{i}")
                        output_temp['citation_recall'] = citation_recall_rating
                        citations = re.findall(r"\[\d+\]", sentence)

                        if len(citations) > 1:
                            cleaned_sentence = re.sub(r"\[\d+\]", "", sentence).strip()
                            cleaned_sentence = cleaned_sentence[:-1]
                            idx = 0
                            for cite in citations:
                                citation_prec_rating = st.radio(f"{cleaned_sentence} {cite}. Does this INDIVIDUAL citation support the claim?", citation_precision_options, index=None, key=f"prec_{resp_type}_{idx}_{i}")
                                output_temp[f'citation_prec_{idx}'] = citation_prec_rating
                                idx += 1
                output[resp_type] = output_temp

            st.write("---")  # Separator between samples
            responses[f"{sample['question']}"] = output

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
