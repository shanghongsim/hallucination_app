import streamlit as st

# Initialize Firebase Admin SDK
def initialize_firebase():
    import firebase_admin
    from firebase_admin import credentials, firestore
    from datetime import datetime
    cred = credentials.Certificate("/home/maojia/work/hallucination_app/hallucination-human-eval-firebase-adminsdk-u77sb-82eeb9f363.json")
    if not firebase_admin._apps:
        # Path to the service account key JSON file
        firebase_admin.initialize_app(cred)

    # Initialize Firestore
    return firestore.client()

# Initialize Firestore
db = initialize_firebase()

def escape_markdown(text):
    import re
    # Define the characters to escape
    escape_chars = r'([\[\](){}*+?.\\^$|#])'
    
    # Use regex to escape all the special characters
    return re.sub(escape_chars, r'\\\1', text)

def load_data():
    import json
    # Load the data from JSON
    with open('human_eval_data.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

def save_responses_to_firestore(responses, form_number, code, name):
    import csv
    from datetime import datetime
    
    # Reference to the Firestore collection
    collection_ref = db.collection(f'form_{name}_responses')

    # Save each response as a document
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
    st.title("Human Evaluation: Appropriateness of Rejection")

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


    # Example: 60 questions divided into 4 forms
    data = load_data()

    # Split questions into 4 chunks of 15 questions each
    def split_into_chunks(lst, chunk_size):
        for i in range(0, len(lst), chunk_size):
            yield lst[i:i + chunk_size]

    chunk_size = 5
    forms = list(split_into_chunks(data, chunk_size))  # List of 4 lists

    # Retrieve questions for the selected form
    form_index = form_number - 1  # Adjust for zero-based indexing
    form_questions = forms[form_index]  # List of 15 questions for the selected form

    # Define Likert scale options
    likert_options = ["Strongly Disagree", "Disagree", "Neutral", "Agree", "Strongly Agree"]

   
    # Create a form in Streamlit
    with st.form(key=f'form_{form_number}'):
        responses = {}
         # Loop through each sample in the data
        for i, sample in enumerate(form_questions):
            st.subheader(f"Sample {i + 1}:")
            
            # Display the question
            st.markdown(f"**Question:** \"{escape_markdown(sample['question'])}\"")

            # Display the documents
            st.markdown("**Documents:**")
            for idx, doc in enumerate(sample['docs']):
                st.markdown(f"- **Document [{idx + 1}]** (Title: {escape_markdown(doc['title'])}): {escape_markdown(doc['text'])}")

            # Display the model output
            st.markdown(f"**Model Output:** \"{escape_markdown(sample['output'])}\"")

            # Likert scale question
            st.subheader(f"Do you think that the rejection is appropriate for Sample {i + 1}?")
            likert_options = ["Strongly Agree", "Agree", "Neutral", "Disagree", "Strongly Disagree"]
            response = st.radio(f"Please select your answer for Sample {i + 1}:", likert_options, index=None, key=f"response_{i}")

            st.write("---")  # Separator between samples
            responses[i] = response

        # Submit button
        submitted = st.form_submit_button("Submit")

        if submitted:
            # Check for unanswered questions
            unanswered_questions = [q for q, r in responses.items() if r not in likert_options]
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
