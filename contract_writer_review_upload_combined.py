import streamlit as st
import google.generativeai as genai
import re
from writerai import Writer
import streamlit_authenticator as stauth
from dotenv import load_dotenv
from auth_manager import AuthenticationManager
from datetime import datetime
import time
import pypandoc  # For .doc files (requires pandoc to be installed)
from docx2python import docx2python
from streamlit_option_menu import option_menu
import os
# Load environment variables
load_dotenv()

# Constants
FILE_REVIEW_TYPES = ["pdf", "docx"]  # Added .doc support
FILE_UPLOAD_TYPES = ["pdf"]  # Added .doc support
MODEL_NAME = "gemini-1.5-flash"
COOKIE_NAME = 'contract_extractor_cookie'
COOKIE_KEY = "abcde"
COOKIE_EXPIRY_DAYS = 30

class ContractExtractor:
    def __init__(self):
        self.setup_page_config()
        self.initialize_session_state()
        self.setup_api_clients()

    def setup_page_config(self):
        st.set_page_config(
            page_title="Contract extractors",
            page_icon="🧊",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        load_css("styles.css")
        
    def initialize_session_state(self):
        # Initialize all session state variables
        if 'processed_data' not in st.session_state:
            st.session_state['processed_data'] = None
        if 'current_file_name' not in st.session_state:
            st.session_state['current_file_name'] = None
        if 'parsed_text' not in st.session_state:
            st.session_state['parsed_text'] = None
        if 'extracted_data' not in st.session_state:
            st.session_state['extracted_data'] = None

    def setup_api_clients(self):
        # Initialize Gemini
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(MODEL_NAME)

        # Initialize Writer
        writer_api_key = st.secrets["WRITER_API_KEY"]
        self.writer_client = Writer(api_key=writer_api_key)
        self.writer_completion_client = self.writer_client.completions
    

class FileProcessor:
    def __init__(self, writer_client):
        self.writer_client = writer_client

    def upload_file_to_writer(self, uploaded_file):
        try:
            raw_bytes = uploaded_file.read()
            if not raw_bytes:
                raise ValueError("The uploaded file is empty.")

            file_name = uploaded_file.name
            if not file_name:
                raise ValueError("The uploaded file has no name.")

            # Check file size
            file_size = len(raw_bytes)
            if file_size > 10 * 1024 * 1024:  # 10 MB limit
                raise ValueError("File size exceeds the maximum allowed limit (10 MB).")

            content_disposition = f'attachment; filename="{file_name}"'
            content_type = "application/pdf" if file_name.endswith(".pdf") else "application/msword"

            # Upload with increased timeout
            file_response = self.writer_client.files.upload(
                content=raw_bytes,
                content_disposition=content_disposition,
                content_type=content_type,
                timeout=60  # Increase timeout to 60 seconds
            )
            return file_response.id
        except Exception as e:
            st.error(f"File Upload Error: {e}")
            return f"File Upload Error: {e}"

    def parse_file_with_writer(self, file_id, file_type):
        try:
            if file_type == "pdf":
                response = self.writer_client.tools.parse_pdf(
                    file_id=file_id,
                    format="markdown",
                )
            else:
                # For .doc and .docx files, we first extract the text and then send it to the Writer API
                response = self.writer_client.tools.parse_text(
                    file_id=file_id,
                    format="markdown",
                )
            return response.content
        except Exception as e:
            return f"Error parsing file with Writer Tools API: {e}"
    @staticmethod
    def is_file_locked(file_path):
        """
        Check if a file is open or locked by another process.
        """
        try:
            # Attempt to open the file in exclusive mode
            with open(file_path, "a", encoding="utf-8") as f:
                pass
            return False  # File is not locked
        except (IOError, PermissionError):
            return True  # File is locked
    @staticmethod
    def extract_text_from_word_file(uploaded_file):
        try:
            file_name = uploaded_file.name
            if file_name.endswith(".docx"):
                # Use docx2python to extract text
                with open("temp.docx", "wb") as f:
                    f.write(uploaded_file.getbuffer())
                document = docx2python("temp.docx")
                full_text = document.text  # Extract all text
                return full_text
            elif file_name.endswith(".doc"):
                # Use pypandoc for .doc files
                with open("temp.doc", "wb") as f:
                    f.write(uploaded_file.getbuffer())
                text = pypandoc.convert_file("temp.doc", "plain")
                return text
            else:
                raise ValueError("Unsupported file format")
        except Exception as e:
            return f"Error extracting text from Word file: {e}"


def process_file(uploaded_file, file_processor, model, auth_manager, writer_completion_client, request_type):
    """Process the uploaded file and store results in session state"""
    try:
        # Initialize progress bar
        progress_text = "Initializing file processing..."
        progress_bar = st.progress(0, text=progress_text)
        
        start_time = datetime.now()
        st.session_state['process_start_time'] = start_time
        
        # Get file size before processing (10% progress)
        progress_bar.progress(10, text="Checking file size...")
        uploaded_file.seek(0, 2)
        filesize = uploaded_file.tell()
        uploaded_file.seek(0)
        
        # Check upload timeout (20% progress)
        progress_bar.progress(20, text="Checking upload permissions...")
        upload_start = datetime.now()
        username = st.session_state.get('username')
        can_upload, wait_time = auth_manager.check_upload_timeout(username)
        
        if not can_upload:
            progress_bar.empty()
            st.error(f"Please wait {wait_time} seconds before uploading another file.")
            st.session_state['current_file_name'] = "clear.pdf"
            return False
        
        # Upload to Writer API (40% progress)
        progress_bar.progress(40, text="Uploading file to processing server...")
        file_id = file_processor.upload_file_to_writer(uploaded_file)
        upload_end = datetime.now()
        st.session_state['upload_time'] = (upload_end - upload_start).total_seconds()
        
        if "Error" in str(file_id):
            progress_bar.empty()
            st.error(f"File Upload Error: {file_id}")
            return False

        # Parse file (60% progress)
        progress_bar.progress(60, text="Parsing file content...")
        parse_start = datetime.now()
        
        file_type = "pdf" if uploaded_file.name.endswith(".pdf") else "word"
        if file_type == "word":
            # Extract text from .doc or .docx and send it to Writer API
            parsed_text = file_processor.extract_text_from_word_file(uploaded_file)
        else:
            parsed_text = file_processor.parse_file_with_writer(file_id, file_type)
        
        parse_end = datetime.now()
        st.session_state['parse_time'] = (parse_end - parse_start).total_seconds()
        
        if not parsed_text:
            progress_bar.empty()
            st.error("Error during file parsing")
            return False
            
        # Check token limit (70% progress)
        progress_bar.progress(70, text="Checking document length...")
        if not auth_manager.check_token_limit(parsed_text):
            progress_bar.empty()
            st.session_state['current_file_name'] = "clear.pdf"
            return False

        # Store parsed text (80% progress)
        progress_bar.progress(80, text="Processing extracted text...")
        st.session_state['parsed_text'] = parsed_text
        
        # Extract information (90% progress)
        progress_bar.progress(90, text="Extracting contract information...")
        extract_start = datetime.now()
        if request_type == "Review":
            extracted_data = extract_info_gemini_vision_review(parsed_text, writer_completion_client)
        else:
            extracted_data = extract_info_gemini_vision_upload(parsed_text, writer_completion_client)
        extract_end = datetime.now()
        st.session_state['extract_time'] = (extract_end - extract_start).total_seconds()
        
        if not extracted_data:
            progress_bar.empty()
            st.error("Error during information extraction.")
            return False
        else:
           st.session_state['extracted_data'] = extracted_data    

        # Finalize processing (100% progress)
        progress_bar.progress(100, text="Finalizing processing...")
        st.session_state['current_file_name'] = uploaded_file.name

        # Calculate metrics
        token_count = len(parsed_text) / 4
        document_length = len(parsed_text)

        # Log the upload
        if username:
            auth_manager.log_file_upload(
                username=username,
                filename=uploaded_file.name,
                filesize=filesize,
                token_count=int(token_count),
                document_length=document_length,
                upload_time=st.session_state.get('upload_time'),
                parse_time=st.session_state.get('parse_time'),
                extract_time=st.session_state.get('extract_time'),
                total_process_time=st.session_state.get('total_process_time'),
                request_type=request_type  # Add this line
            )
            
        total_time = (datetime.now() - start_time).total_seconds()
        st.session_state['total_process_time'] = total_time
        
        # Clear progress bar after completion
        time.sleep(1)
        progress_bar.empty()
        return True
        
    except Exception as e:
        if 'progress_bar' in locals():
            progress_bar.empty()
        st.error(f"Error processing file: {e}")
        return False
    
def load_css(css_file):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    css_path = os.path.join(current_dir, css_file)
    with open(css_path, 'r') as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

def main():
    # Initialize main components

    extractor = ContractExtractor()
    auth_manager = AuthenticationManager()
    is_authenticated = auth_manager.setup_authentication()
    
    if not is_authenticated:
        return

    # Initialize file processor
    file_processor = FileProcessor(extractor.writer_client)

    # Sidebar setup
    st.sidebar.header("Writer Contract Information Extractor", divider="gray")
    st.sidebar.markdown("<br>", unsafe_allow_html=True)
    # Add a dropdown for request type
    #request_type = st.sidebar.selectbox("Request Type", ["Review", "Upload"])
    
    with st.sidebar:
            request_type = option_menu(
            menu_title=None,  # No title
            options=["Review", "Upload"],  # Menu options
            icons=['file-earmark-text', 'cloud-upload'],  # Icons for each option
            menu_icon="cast",  # Menu icon (optional)
            default_index=0,  # Default selected option
            orientation="Horizontal",  # Horizontal layout
            styles={
                # Container styles
                "container": {
                    "padding": "0!important",  # No padding
                    "background-color": "#ffffff",  # White background
                    "border-radius": "4px",  # Rounded corners
                    "box-shadow": "0 2px 4px rgba(0, 0, 0, 0.1)",  # Subtle shadow
                    "width": "80%",  # Width of the menu
                    "margin": "auto",  # Center the menu
                    "border": "1px solid #e2e8f0"
                    
                },
                # Icon styles
                "icon": {
                    "color": "#8F67E6",  # Indigo color for icons
                    "font-size": "20px",  # Icon size
                    "margin-right": "8px",  # Space between icon and text
                },
                # Nav link styles (unselected options)
                "nav-link": {
                    "font-size": "15px",  # Font size
                    "text-align": "center",  # Center text
                    "padding": "10px 20px",  # Padding for buttons
                    "margin": "0px",  # No margin
                    "color": "#4b5563",  # Gray text color
                    "border-radius": "8px",  # Rounded corners
                    "transition": "all 0.3s ease",  # Smooth transition
                },
                # Nav link hover styles
                "nav-link:hover": {
                    "background-color": "#f3f4f6",  # Light gray background on hover
                    "color": "#fffff",  # Indigo text color on hover
                },
                # Selected nav link styles
                "nav-link-selected": {
                    "background-color": "#374151",  # Indigo background for selected option
                    "color": "#ffffff",  # White text color for selected option
                    "font-weight": "600",  # Bold text for selected option
                    "border-radius": "4px",  # Rounded corners
                },
            }
        )
    #st.sidebar.markdown("<br>", unsafe_allow_html=True)
    if request_type == "Review":
        request_label = "Review a Contract"
    else:
        request_label = "Upload a Contract"
    st.sidebar.divider()
    st.header(request_label)
    uploaded_file = st.sidebar.file_uploader("Upload File", type=FILE_REVIEW_TYPES)

    st.sidebar.divider()
    
    if uploaded_file is None:
        st.error("Please upload a contract PDF, or DOCX to begin.")
        return
    
    # Check if we need to process a new file
    if (st.session_state['current_file_name'] != uploaded_file.name and 
        uploaded_file is not None):
        with st.spinner("Processing file..."):
            success = process_file(uploaded_file, file_processor, extractor.model, auth_manager, extractor.writer_completion_client, request_type)
            if not success:
                return

    # Display results if we have them
    if st.session_state['parsed_text'] and st.session_state['extracted_data']:
        display_results(request_type)

    


def display_results(request_type):
    """Display the processed results"""
    parsed_text = st.session_state['parsed_text']
    extracted_data = st.session_state['extracted_data']

    st.success("PDF processed successfully!")
    
    # Create three tabs
    tab1, tab2, tab3 = st.tabs(["Extracted Information", "Raw Text", "Upload History"])
    
    # Tab 1: Extracted Information
    with tab1:
        if request_type == "Review":
            display_extracted_information_review(extracted_data)
        else:
            display_extracted_information_upload(extracted_data)
    # Tab 2: Raw Text
    with tab2:
        st.markdown("### Raw Extracted Text")
        st.code(parsed_text, language="html", wrap_lines=True)
        
    # Tab 3: Upload History
    with tab3:
        display_upload_history()
    
    # Display token statistics in sidebar
    display_token_statistics(parsed_text)

def display_upload_history():
    """Display upload history in a formatted table"""
    if st.session_state.get('username'):
        auth_manager = AuthenticationManager()
        logs = auth_manager.get_user_logs(username=st.session_state['username'])
        
        if logs:
            import pandas as pd
            
            df = pd.DataFrame(logs)
            
            # Calculate total time
            df['total_time'] = df['upload_time'] + df['parse_time'] + df['extract_time']
            
            # Format the data
            df['filesize'] = df['filesize'].apply(lambda x: f"{x/1024:.1f} KB")
            df['token_count'] = df['token_count'].apply(lambda x: f"{x:,}")
            df['document_length'] = df['document_length'].apply(lambda x: f"{x:,}")
            
            # Rename columns for display
            df = df.rename(columns={
                'filename': 'File Name',
                'filesize': 'File Size',
                'token_count': 'Tokens',
                'document_length': 'Document Length',
                'upload_timestamp': 'Upload Date',
                'upload_time': 'Upload Time',
                'parse_time': 'Parse Time',
                'extract_time': 'Extract Time',
                'total_time': 'Total Time',
                'request_type': 'Request Type'

            })
            
            # Reorder columns and drop ID
            columns_order = ['File Name', 'File Size', 'Request Type', 'Tokens', 'Document Length', 
                           'Upload Date', 'Upload Time', 'Parse Time', 'Extract Time', 'Total Time']
            df = df[columns_order]
            
            st.markdown("### Upload History")
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True
            )
            
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "Download Upload History",
                csv,
                "upload_history.csv",
                "text/csv",
                key='download-csv'
            )
        else:
            st.info("No upload history available")
    else:
        st.warning("Please log in to view upload history")


def extract_info_gemini_vision_review(parsed_text, writer_completion_client):
    prompt = """Analyze the provided contract document and extract the following information, highlighting relevant clauses, keywords, and details:

1. Payment Terms
Description: Identify payment terms, including standard periods (e.g., 30 days), conditions for exceeding terms, and invoice requirements. Highlight any deviations from the standard policy.
Keywords: Pay, Payable, Invoice, Net.
Sample Format:
a.) Payment due within [X] days of receipt of a correct invoice.
b.) Any deviations require [specific approval or conditions].

2. Rate Cards
Description: Extract details about rate cards, hourly rate structures, and personnel-based fees. Reference any rate tables.
Keywords: Rate, Rate Cards, Hourly.
Sample Format:
a.) Fee structure for hourly rates based on personnel levels, types of work, and geographical regions.
b.) Provide examples where applicable, including rate tables or caps.

3. Client Travel and Expense Policy
Description: Identify clauses related to travel and expense reimbursement. Note if the client's travel policy applies and highlight any restrictions or exceptions.
Keywords: Expense, Travel, Expense Policy, Travel Guide.
Sample Format:
a.) Reimbursement terms for travel-related expenses, including approvals and documentation requirements.
b.) Policies about economy fares, preferred accommodations, and non-reimbursable items.


4. Diverse Supplier Provisions
Description: Highlight provisions encouraging the use of diverse suppliers and related reporting requirements.
Keywords: Diversity, Diverse Supplier, Inclusion.
Sample Format:
a.) Include language supporting diverse supplier inclusion and any reporting requirements (e.g., quarterly reports).


5. Termination Clauses
Description: Identify terms for termination, including "termination for convenience" or "material breach." Highlight any fees or specific conditions.
Keywords: Termination for convenience, Termination without cause, Material breach.
Sample Format:
a.) Right to terminate with [X] days' notice or under specific conditions.
b.) Associated termination fees, if any, and their calculation.


6. Limitation of Liability
Description: Extract limitations of liability clauses, including standard caps or carveouts.
Keywords: Indirect damage exclusion, Mutual limits, Super cap.
Sample Format:
a.) Liability capped at [X] or a multiple of fees paid within a specific timeframe.
b.) Uncapped liability for specific scenarios, such as gross negligence.


7. Data Privacy
Description: Summarize data privacy obligations, including compliance with regulations like GDPR or specific client data protection requirements.
Keywords: Data Privacy, Data Processing, GDPR.
Sample Format:
a.) Outline responsibilities for protecting personal data and compliance with regulations.
b.) Highlight any cross-border data restrictions or notification obligations in case of breaches.


8. Insurance Provisions
Description: Highlight insurance coverage requirements, including limits and types of coverage (e.g., liability, workers' compensation).
Keywords: Insurance, Coverage.
Sample Format:
a.)Required insurance types and coverage limits.
b.) Period of coverage and renewal obligations.


9. Background Check/Drug Screening
Description: Extract clauses requiring background checks or drug testing. Note any restrictions or client-specific requirements.
Keywords: Background check, Drug, Alcohol testing.
Sample Format:
a.) Requirements for background checks or drug screening, including specific roles or access levels.



Additional Instructions:

                1. Analyze the attached contracts and extract relevant information. Ensure that the section numbers and names are accurately provided only if explicitly mentioned in the document and are directly relevant to the extracted content. If section numbers are absent or irrelevant, exclude them from the output. The focus should be on providing precise, contextually relevant details based solely on the content of the document.

                2. For each of the above, only output the relevant text that was parsed from the document and format the output in the following format using these tags.
                - In the raw relevant text thaw will be extracted if section numbers or section names are available include them in the export

[Payment Terms]
[results]
<b>Payment Terms:</b> <Summary of payment terms> <br>
<span style="font-size: 13px;font-style: italic;">Section no.(s): [section number(s)]<br> Section Name(s): [section name(s)]</span>
[raw extracted]
<relevant text from the payment terms section>
[Payment Terms]

[Rate Cards]
[results]
<b>Rate Cards:</b> <Summary of rate card terms> <br>
<span style="font-size: 13px;font-style: italic;">Section no.(s): [section number(s)]<br> Section Name(s): [section name(s)]</span>
[raw extracted]
<relevant text from the rate cards section>
[Rate Cards]

[Travel and Expense Policies]
[results]
<b>Travel and Expense Policies:</b> <Summary of travel and expense policy terms> <br>
<span style="font-size: 13px;font-style: italic;">Section no.(s): [section number(s)]<br> Section Name(s): [section name(s)]</span>
[raw extracted]
<relevant text from the travel and expense policies section>
[Travel and Expense Policies]

[Diverse Supplier Provisions]
[results]
<b>Diverse Supplier Provisions:</b> <Summary of diverse supplier clauses> <br>
<span style="font-size: 13px;font-style: italic;">Section no.(s): [section number(s)]<br> Section Name(s): [section name(s)]</span>
[raw extracted]
<relevant text from the diverse supplier provisions section>
[Diverse Supplier Provisions]

[Termination Clauses]
[results]
<b>Termination Clauses:</b> <Summary of termination clauses> <br>
<span style="font-size: 13px;font-style: italic;">Section no.(s): [section number(s)]<br> Section Name(s): [section name(s)]</span>
[raw extracted]
<relevant text from the termination clauses section>
[Termination Clauses]

[Limitation of Liability]
[results]
<b>Limitation of Liability:</b> <Summary of liability limitations> <br>
<span style="font-size: 13px;font-style: italic;">Section no.(s): [section number(s)]<br> Section Name(s): [section name(s)]</span>
[raw extracted]
<relevant text from the limitation of liability section>
[Limitation of Liability]

[Data Privacy]
[results]
<b>Data Privacy:</b> <Summary of data privacy clauses> <br>
<span style="font-size: 13px;font-style: italic;">Section no.(s): [section number(s)]<br> Section Name(s): [section name(s)]</span>
[raw extracted]
<relevant text from the data privacy section>
[Data Privacy]

[Insurance Provisions]
[results]
<b>Insurance Provisions:</b> <Summary of insurance provisions> <br>
<span style="font-size: 13px;font-style: italic;">Section no.(s): [section number(s)]<br> Section Name(s): [section name(s)]</span>
[raw extracted]
<relevant text from the insurance provisions section>
[Insurance Provisions]

[Background Check/Drug Screening]
[results]
<b>Background Check/Drug Screening:</b> <Summary of background check or drug screening terms> <br>
<span style="font-size: 13px;font-style: italic;">Section no.(s): [section number(s)]<br> Section Name(s): [section name(s)]</span>
[raw extracted]
<relevant text from the background check/drug screening section>
[Background Check/Drug Screening]

Note: The Service Provider is always Towers Watson or Willis Towers Watson. 
"""

    try:
        completion = writer_completion_client.create(
            model="palmyra-x-004",
            prompt=f"{prompt}\n\nDocument Content:\n{parsed_text}",
            #max_tokens=50000,
            temperature=0.0,
            stream=False
        )
        return completion.choices[0].text
    except Exception as e:
        return f"Error querying Writer API: {e}"

def display_extracted_information_review(extracted_data):
    # Define sections with their patterns and display titles
    sections = {
        'Payment Terms': {
            'title': '💰 Financial Terms',
            'pattern': r'\[Payment Terms\]\s+\[results\]\s+<b>Payment Terms:</b>.*?\[raw extracted\].*?\[Payment Terms\]',
            'expanded': False
        },
        'Rate Cards': {
            'title': '💰 Financial Terms',
            'pattern': r'\[Rate Cards\]\s+\[results\]\s+<b>Rate Cards:</b>.*?\[raw extracted\].*?\[Rate Cards\]',
            'expanded': False
        },
        'Travel and Expense Policies': {
            'title': '✈️ Travel & Expenses',
            'pattern': r'\[Travel and Expense Policies\]\s+\[results\]\s+<b>Travel and Expense Policies:</b>.*?\[raw extracted\].*?\[Travel and Expense Policies\]',
            'expanded': False
        },
        'Diverse Supplier Provisions': {
            'title': '🤝 Supplier Relations',
            'pattern': r'\[Diverse Supplier Provisions\]\s+\[results\]\s+<b>Diverse Supplier Provisions:</b>.*?\[raw extracted\].*?\[Diverse Supplier Provisions\]',
            'expanded': False
        },
        'Termination Clauses': {
            'title': '📋 Contract Terms',
            'pattern': r'\[Termination Clauses\]\s+\[results\]\s+<b>Termination Clauses:</b>.*?\[raw extracted\].*?\[Termination Clauses\]',
            'expanded': False
        },
        'Limitation of Liability': {
            'title': '⚖️ Legal Provisions',
            'pattern': r'\[Limitation of Liability\]\s+\[results\]\s+<b>Limitation of Liability:</b>.*?\[raw extracted\].*?\[Limitation of Liability\]',
            'expanded': False
        },
        'Data Privacy': {
            'title': '🔒 Privacy & Security',
            'pattern': r'\[Data Privacy\]\s+\[results\]\s+<b>Data Privacy:</b>.*?\[raw extracted\].*?\[Data Privacy\]',
            'expanded': False
        },
        'Insurance Provisions': {
            'title': '🛡️ Insurance & Compliance',
            'pattern': r'\[Insurance Provisions\]\s+\[results\]\s+<b>Insurance Provisions:</b>.*?\[raw extracted\].*?\[Insurance Provisions\]',
            'expanded': False
        },
        'Background Check/Drug Screening': {
            'title': '🛡️ Insurance & Compliance',
            'pattern': r'\[Background Check/Drug Screening\]\s+\[results\]\s+<b>Background Check/Drug Screening:</b>.*?\[raw extracted\].*?\[Background Check/Drug Screening\]',
            'expanded': False
        }
    }

    def extract_content(text, section_name):
        pattern = sections[section_name]['pattern']
        match = re.search(pattern, text, re.DOTALL)
        if match:
            full_text = match.group(0)
            results_match = re.search(r'\[results\]\s+(.*?)\s+\[raw extracted\]', full_text, re.DOTALL)
            raw_match = re.search(r'\[raw extracted\]\s+(.*?)\s+\[' + section_name + '\]', full_text, re.DOTALL)
            
            if results_match and raw_match:
                return {
                    'results': results_match.group(1).strip(),
                    'raw': raw_match.group(1).strip()
                }
        return None

    # Group sections by their display titles
    grouped_sections = {}
    for section_name, section_info in sections.items():
        title = section_info['title']
        if title not in grouped_sections:
            grouped_sections[title] = []
        grouped_sections[title].append(section_name)

    # Display sections grouped by title
    for title, section_names in grouped_sections.items():
        with st.expander(title, expanded=False):
            for section_name in section_names:
                content = extract_content(extracted_data, section_name)
                if content:
                    st.markdown(content['results'], unsafe_allow_html=True)
                    st.code(content['raw'], wrap_lines=True, language="html")
                else:
                    st.write(f"No information found for {section_name}")
    #st.code(extracted_data)

def extract_info_gemini_vision_upload(parsed_text, writer_completion_client):
    prompt = f"""
            Analyze the following contract document below and extract the following information: 

    1. Termination Notice No. of Days: Specify the termination notice period mentioned in the contract. Include whether the notice is for cause or without cause, and highlight any associated termination fees or conditions.
    2. Auto Renewal Clause: Determine if the contract includes an auto-renewal clause. If present, provide details about the clause, including the notice period required to prevent renewal.
    3. Signed Date of the Client: Extract the date when the client signed the contract (if available in the document).
    4. Effective Date: Identify and extract the effective date of the agreement. Include details about initial terms and any mentioned renewal periods.
    5. Service Provider: Extract the name of the vendor or service provider involved in the agreement, including any affiliated entities referenced. Start by examining the signed section of the document for the entity name. If the service provider is not found in the signed section, check other sections of the document, such as the introduction, definitions, or relevant clauses, for mentions of the vendor or its affiliated entities.
    6. Data Privacy Link: Search for the presence of the specific link mentioned in the contract: https://www.willistowerswatson.com/en-gb/notices/global-data-processing-protocol. If it exists, extract it; if not, indicate as no Data Privacy link found.
    7. Associated or connected with a Higher-Level Agreement: Identify whether the contract references another related or higher-level agreement, such as a Master Services Agreement (MSA). 
    For example, clauses such as:
    "The services described in this Scope of Work will be provided subject to the Master Services Agreement (MSA) between service provider and client dated (date agreement) and any subsequent amendments." 
    Extract such references if available and dont be to specific from this example find something like this.

    8. Duration or Expiration Date: Extract the duration of the contract, including its start date and end date or Provide any information related to the expiration date or potential conditions for renewal or termination.

            Additional instructions:

                1. Analyze the attached contracts and extract relevant information. Ensure that the section numbers and names are accurately provided only if explicitly mentioned in the document and are directly relevant to the extracted content. If section numbers are absent or irrelevant, exclude them from the output. The focus should be on providing precise, contextually relevant details based solely on the content of the document.
                
                2. For each of the above, only output the relevant text that was parsed from the document and format the output in the following format using these tags.
                        - In the raw relevant text thaw will be extracted if section numbers or section names are available include them in the export

                    [Service]

                    [results]

                    <b>WTW Entity:</b> <Service provider>

                    [raw extracted]

                    <relevant text from the signature section>

                    [Service]

                    [Termination]

                    [results]

                    <b>Termination Notice No. of Days:</b> <Termination Notice and which party is giving the notice> <br>

                    <span style="font-size: 13px;font-style: italic;">Section no.(s): [section number(s)]<br> Section Name(s): [section name(s)]</span>

                    [raw extracted]

                    <relevant text from the termination section>

                    [Termination]

                    [Renewal]

                    [results]

                    <b>Auto Renewal:</b> <Renewal Clause Details> <br>

                    <span style="font-size: 13px;font-style: italic;">Section no.(s): [section number(s)]<br> Section Name(s): [section name(s)]</span>an>

                    [raw extracted]

                    <relevant text from the renewal section>

                    [Renewal]

                    [Signed Date]

                    [results]

                    <b>Signed Date of the Client (<client name>):</b> <Date of the client signing> <br>

                    <span style="font-size: 13px;font-style: italic;">Section no.(s): [section number(s)]<br> Section Name(s): [section name(s)]</span>

                    [raw extracted]

                    <relevant text from the signature section>

                    [Signed Date]

                    [Effectivity Date]

                    [results]

                    <b>Effectivity Date:</b> <Effectivity Date> <br>

                    <span style="font-size: 13px;font-style: italic;">Section no.(s): [section number(s)]<br> Section Name(s): [section name(s)]</span>
                    [raw extracted]

                    <relevant text from the Effectivity section>

                    [Effectivity Date]

                    [Data privacy]

                    [results]

                    <b>Data privacy Link:</b> <Data privacy if link is found or not> <br>

                    <span style="font-size: 13px;font-style: italic;">Section no.(s): [section number(s)]<br> Section Name(s): [section name(s)]</span>

                    [raw extracted]

                    <relevant text from the Data privacy section>

                    [Data privacy]

                    [Higher Level]

                    [results]

                    <b>Associated with a Higher Level agreement:</b> <Add summary here if the current document is Associated with a Higher Level agreement> <br>

                    <span style="font-size: 13px;font-style: italic;">Section no.(s): [section number(s)]<br> Section Name(s): [section name(s)]</span>

                    [raw extracted]

                    <relevant text from the Associated with a Higher Level agreement section>

                    [Higher Level]

                    [Expiration]

                    [results]

                    <b>Expiration Date:</b> <Duration or Expiration Date information> <br>

                        <span style="font-size: 13px;font-style: italic;">Section no.(s): [section number(s)]<br> Section Name(s): [section name(s)]</span>

                    [raw extracted]

                    <relevant text from the Duration or Expiration Date date section>

                    [Expiration]



            Note: The Service Provider is always Towers Watson or Willis Towers Watson. Please extract only the Client's Signature Date.
                """
    try:
        completion = writer_completion_client.create(
            model="palmyra-x-004",
            prompt=f"{prompt}\n\nDocument Content:\n{parsed_text}",
            max_tokens=50000,
            temperature=0.0,
            stream=False
        )
        return completion.choices[0].text
    except Exception as e:
        return f"Error querying Writer API: {e}"

def display_extracted_information_upload(extracted_data):
    # Define sections with their patterns and display titles
    sections = {
        'Service': {
            'title': '🏢 WTW and client info',
            'pattern': r'\[Service\]\s+\[results\]\s+<b>WTW Entity:</b>.*?\[raw extracted\].*?\[Service\]',
            'expanded': True
        },
        'Signed Date': {
            'title': '🏢 WTW and client info',
            'pattern': r'\[Signed Date\]\s+\[results\]\s+<b>Signed Date of the Client \(.*?\):</b>.*?\[raw extracted\].*?\[Signed Date\]',
            'expanded': True
        },
        'Effectivity Date': {
            'title': '📅 Contract Duration',
            'pattern': r'\[Effectivity Date\]\s+\[results\]\s+<b>Effectivity Date:</b>.*?\[raw extracted\].*?\[Effectivity Date\]',
            'expanded': True
        },
        'Expiration': {
            'title': '📅 Contract Duration',
            'pattern': r'\[Expiration\]\s+\[results\]\s+<b>Expiration Date:</b>.*?\[raw extracted\].*?\[Expiration\]',
            'expanded': True
        },
        'Termination': {
            'title': '⛔ Termination',
            'pattern': r'\[Termination\]\s+\[results\]\s+<b>Termination Notice No\. of Days:</b>.*?\[raw extracted\].*?\[Termination\]',
            'expanded': True
        },
        'Renewal': {
            'title': '🔄 Auto Renewal',
            'pattern': r'\[Renewal\]\s+\[results\]\s+<b>Auto Renewal:</b>.*?\[raw extracted\].*?\[Renewal\]',
            'expanded': True
        },
        'Data privacy': {
            'title': '🔒 Data privacy Link',
            'pattern': r'\[Data privacy\]\s+\[results\]\s+<b>Data privacy Link:</b>.*?\[raw extracted\].*?\[Data privacy\]',
            'expanded': True
        },
        'Higher Level': {
            'title': '📜 With a higher level agreement',
            'pattern': r'\[Higher Level\]\s+\[results\]\s+<b>Associated with a Higher Level agreement:</b>.*?\[raw extracted\].*?\[Higher Level\]',
            'expanded': True
        }
    }

    def extract_content(text, section_name):
        pattern = sections[section_name]['pattern']
        match = re.search(pattern, text, re.DOTALL)
        if match:
            full_text = match.group(0)
            results_match = re.search(r'\[results\]\s+(.*?)\s+\[raw extracted\]', full_text, re.DOTALL)
            raw_match = re.search(r'\[raw extracted\]\s+(.*?)\s+\[' + section_name + '\]', full_text, re.DOTALL)
            
            if results_match and raw_match:
                return {
                    'results': results_match.group(1).strip(),
                    'raw': raw_match.group(1).strip()
                }
        return None

    # Group sections by their display titles
    grouped_sections = {}
    
    for section_name, section_info in sections.items():
        title = section_info['title']
        if title not in grouped_sections:
            grouped_sections[title] = []
        grouped_sections[title].append(section_name)
    #grouped_sections
    # Display sections grouped by title
    for title, section_names in grouped_sections.items():
        with st.expander(title, expanded=True):
            cols = st.columns(len(section_names))
            for col, section_name in zip(cols, section_names):
                with col:
                    content = extract_content(extracted_data, section_name)
                    
                    if content:
                        st.markdown(content['results'], unsafe_allow_html=True)
                        st.code(content['raw'], wrap_lines=True, language="html")
                    else:
                        st.write("Not found")
                            
def display_token_statistics(parsed_text):
  with st.sidebar:
     with st.expander("📊 Statistics", expanded=False):   
        # Processing Statistics Section
       
        st.markdown("<div class='stats-container'>", unsafe_allow_html=True)
        st.markdown("### Processing Statistics")
        # Display time metrics if available
        time_metrics = {
            'Upload time': st.session_state.get('upload_time'),
            'Parse time': st.session_state.get('parse_time'),
            'Extract time': st.session_state.get('extract_time'),
            'Total time': st.session_state.get('total_process_time')
        }
        
        for label, value in time_metrics.items():
            if value is not None:
                st.markdown(f"""
                    <div class='stat-card processing-stat'>
                        <div class='stat-label'>{label}</div>
                        <div class='stat-value processing-value'>{value:.2f}s</div>
                    </div>
                """, unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Document Statistics Section
        st.markdown("### Document Statistics")
        st.markdown("<div class='stats-container'>", unsafe_allow_html=True)
        
        # Token count and document length
        doc_metrics = {
            'Token count': len(parsed_text) / 4,
            'Document length': len(parsed_text)
        }
        
        for label, value in doc_metrics.items():
            st.markdown(f"""
                <div class='stat-card document-stat'>
                    <div class='stat-label'>{label}</div>
                    <div class='stat-value document-value'>{value:.0f}</div>
                </div>
            """, unsafe_allow_html=True)
            
        st.markdown("</div>", unsafe_allow_html=True)

if __name__ == '__main__':
    
    main()
