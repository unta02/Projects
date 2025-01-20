import os
import pandas as pd
import sqlite3

from datetime import datetime
import streamlit as st
import numpy as np
from streamlit_pagination import pagination_component
import io
import time
import plotly.express as px
import plotly.graph_objects as go
import streamlit.components.v1 as components
# Page configuration
# st.set_page_config(
#     page_title="Contract Draft Request Tracker",
#     layout="wide"
# )
if 'foo' not in st.session_state:
    st.session_state['foo'] = 0

# Custom CSS for styling
st.markdown("""
    <style>
            
    div[data-testid="stCaptionContainer"]{
    
        font-size: 15px;
       color: #595959;
        opacity: 1;
    }  
    div[data-testid="stButton"]{
    text-align: right;
   
    }    
    .stApp {
        background-color: #f9fafb;
    }
    .block-container {
        padding-top: 3rem;
        padding-bottom: 2rem;
    }
    [data-testid="stSidebar"] {
        background-color: white;
        padding: 2rem 1rem;
         border-right: 1px solid #e2e2e2;
}   
    }
    .st-emotion-cache-16txtl3 {
        padding: 1rem;
    }
             .header {
            text-align: center;
            margin-top: 20px;
        }

        .header h1 {
            font-size: 28px;
            margin: 0;
        }

        .header p {
            font-size: 14px;
            margin: 5px 0 20px;
            color: #555;
        }

        div[data-baseweb="select"]  {
            font-size: 14px;
            margin: 5px 0 10px;
            color: #555;
            border: 1px solid #c6c6c6;
            border-radius: 8px;
            
        }   
            
        div[data-baseweb="select"] > div
            {
            background: white;
            text-color:black;
            } 

        div[data-testid="stTextInputRootElement"]  {
            font-size: 14px;
            margin: 5px 0 10px;
            color: #555;
            border: 1px solid #c6c6c6;
            border-radius: 8px;
            width: 70%;
        }   
            
        label[data-testid="stWidgetLabel"] > div    
        {
            font-size: 16px;
            
        }  

        div[data-testid="stSidebarHeader"]   
        {
            display:none;
            
        }  

            iframe{
            height:34px;
            width:500px;
            }

        .MuiPaginationItem-textPrimary.Mui-selected {
            color: #fff;
            background-color: #000 !important;
        }

.material-symbols-outlined {
  font-variation-settings:
  'FILL' 0,
  'wght' 400,
  'GRAD' 0,
  'opsz' 24
}
            div[data-testid="stToolbar"] {
    visibility: hidden;
    height: 0%;
    position: fixed;
    }
    div[data-testid="stDecoration"] {
    visibility: hidden;
    height: 0%;
    position: fixed;
    }
    div[data-testid="stStatusWidget"] {
    visibility: hidden;
    height: 0%;
    position: fixed;
    }
    #MainMenu {
    visibility: hidden;
    height: 0%;
    }
    header {
    visibility: hidden;
    height: 0%;
    }
    footer {
    visibility: hidden;
    height: 0%;
    }
    </style>
""", unsafe_allow_html=True)

def navigation(reportdate):
    navigation_component = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/react/17.0.2/umd/react.development.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/react-dom/17.0.2/umd/react-dom.development.js"></script>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/tailwindcss/2.2.19/tailwind.min.css" rel="stylesheet">
    </head>
    <body>
        <div id="react-navigation-root"></div>
        <script>
            const testdate = "{reportdate}"; // Pass Python variable as a JavaScript variable

            const Navigation = () => {{
                return React.createElement('div', {{ className: 'flex flex-col w-full' }},
                    
                    React.createElement('div', {{ className: 'w-full bg-purple-900 px-4 py-2' }},
                        React.createElement('div', {{ className: 'flex items-center justify-between' }},
                            // Left section
                            React.createElement('div', {{ className: 'flex items-center space-x-4' }},
                                React.createElement('span', {{ className: 'text-white text-xl font-semibold' }}, `wtw | Contract Draft Request Tracker`)
                            ),
                            // Right section
                            React.createElement('div', {{ className: 'flex items-center space-x-4' }},
                                React.createElement('span', {{ className: 'text-l text-white font-medium font-semibold' }},
                                    `Report as of: {testdate}`
                                )
                            )
                        )
                    )
                );
            }};

            ReactDOM.render(
                React.createElement(Navigation),
                document.getElementById('react-navigation-root')
            );
        </script>
    </body>
    </html>
    """
    return navigation_component
@st.cache_data(show_spinner=False)  # Disable default cache spinner since we'll use our own
def load_data(last_modified):
    """Load data from SQLite database"""
    try:
        # Get the absolute path to the database
        current_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(current_dir, "data", "contracts.db")
        
        with st.spinner("Loading data from database... Please wait"):
            # Connect to SQLite database
            conn = sqlite3.connect(db_path)
            
            # Load the main data table
            df = pd.read_sql("SELECT * FROM contracts", conn)
            
            # Load the report date from metadata table
            report_date_df = pd.read_sql("SELECT report_date FROM report_metadata", conn)
            report_date = report_date_df['report_date'].iloc[0]
            report_date = pd.to_datetime(report_date).strftime('%Y-%m-%d')

            conn.close()
            
            return df, report_date
    except sqlite3.Error as e:
        st.error(f"Database error: {str(e)}")
        return None, None
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return None, None
    ## Export button
@st.dialog("Download Excel File")
def show_download_dialog(filtered_df, selected_columns):
    with st.spinner("Preparing your Excel file..."):
        try:
            # Convert datetime back to datetime format for Excel
            export_df = filtered_df[selected_columns].copy()
            if 'Created On' in export_df.columns:
                export_df['Created On'] = pd.to_datetime(export_df['Created On'])
            
            # Create Excel file in memory using BytesIO
            buffer = io.BytesIO()
            
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                export_df.to_excel(writer, index=False, sheet_name='Sheet1')
                
                # Access the XlsxWriter workbook and worksheet objects
                workbook = writer.book
                worksheet = writer.sheets['Sheet1']
                
                # Add a basic header format
                header_format = workbook.add_format({
                    'bold': True,
                    'fg_color': '#D3D3D3',
                    'border': 1
                })
                
                # Set column widths based on header length
                for idx, col in enumerate(export_df.columns):
                    header_length = len(str(col))
                    adjusted_width = header_length + 4
                    adjusted_width = max(adjusted_width, 8)
                    worksheet.set_column(idx, idx, adjusted_width)
                    worksheet.write(0, idx, col, header_format)
            
            # Reset buffer position
            buffer.seek(0)
            
            # Show success message in dialog
            st.success("File is ready for download!")
            
            # Add download button to dialog
            st.download_button(
                label="⬇️ Click here to Download the Excel File",
                data=buffer,
                file_name="contract_tracker_export.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            # Add close button
            # if st.button("Close"):
            #     st.rerun()
            
        except Exception as e:
            st.error(f"Error exporting data: {str(e)}")
            if st.button("Close"):
                st.rerun()
def main():

    # Initialize loading state
    with st.spinner("Initializing application..."):
        # Get the last modified time of the database file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(current_dir, "data", "contracts.db")
        
        try:
            last_modified = os.path.getmtime(db_path)
        except FileNotFoundError:
            st.error("Database file not found. Please check if the database exists in the data folder.")
            return
        except Exception as e:
            st.error(f"Error accessing database: {str(e)}")
            return

    # Load data
    df, report_date = load_data(last_modified)
    
    if df is None:
        st.error("Failed to load data. Please check the database connection.")
        return

    # Once data is loaded successfully, show a success message that auto-disappears
    # success_container = st.empty()
    # success_container.success("Data loaded successfully!")
    # time.sleep(.5)  # Show success message for 2 seconds
    # success_container.empty()  # Remove the success message
    
 # Main header
    #st.header("Contract Draft Request Tracker")
    if isinstance(report_date, (pd.Timestamp, datetime)):
        date_str = report_date.strftime('%B %d, %Y')
    else:
        date_str = str(report_date)
    st.sidebar.markdown(f"<span class='header'><h1>Contract Draft Request Tracker</h1><i>Report as of {date_str}</i></span><br><br>",unsafe_allow_html=True)
    # Add content to the sidebar with a Material Icon
    
    # st.markdown("""
    # <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&icon_names=dashboard" />    """, unsafe_allow_html=True)
    # st.sidebar.markdown(f"""
    #         <h1><span class="material-symbols-outlined">dashboard</span> Contract Draft Request Tracker</h1>
    #         <i>Report as of {date_str}</i>
    #         <br><br>
    #         """, unsafe_allow_html=True)

    st.sidebar.header(":material/filter_list: Filters")
    #st.logo("images/Logo_WTW.png",icon_image="images/Logo_WTW.png",size="large")
    # Create filters for each specified column
    filter_columns = ['Status', 'Agreement Type','WTW Business(s)','Requester Name', 'Legal Contact', 
                      'COE Assessor']
    
    filters = {}
    for column in filter_columns:
        if column in df.columns:
            unique_values = sorted(df[column].dropna().unique().tolist())
            filters[column] = st.sidebar.multiselect(
                f"**Select {column}:**",
                options=unique_values,
                default=[]
            )
    
    # Apply filters
    filtered_df = df.copy()
    for column, selected_values in filters.items():
        if selected_values and column in filtered_df.columns:
            filtered_df = filtered_df[filtered_df[column].isin(selected_values)]

    # Search functionality
    
    #st.markdown(":material/search: **Search by ID or Agreement Name**") # write the name of the icon 'Settings' next to the word Search (you can use any word you wish)

    #search_term = input(default_value="", type='text', placeholder="", key="input1")
    col3, col4 = st.columns([2, 2],vertical_alignment="center")
    #Search box    
    search_term = col3.text_input(" :material/search:  **Search by Client Entity Name or Requester Name**:", "",placeholder="Search")
    if search_term:
            with st.spinner("Searching records..."):
                mask = (
                    filtered_df['Client Entity Name'].astype(str).str.contains(search_term, case=False) |
                    filtered_df['Requester Name'].astype(str).str.contains(search_term, case=False)
                )
                filtered_df = filtered_df[mask]

    status_counts = filtered_df['Status'].value_counts()
    fig = go.Figure(data=[
        go.Bar(
            x=status_counts.index,
            y=status_counts.values,
            text=status_counts.values,  # This will be displayed on top of bars
            textposition='outside',     # Position the text above the bars
            marker_color='rgb(143, 103, 230)',
            opacity=0.8,
            textfont=dict(size=12)
        )
    ])

    # Update layout for better visibility
    fig.update_layout(
        title="Contract Status Distribution",
        xaxis_title="Status",
        yaxis_title="Number of Contracts",
        height=500,  # Increased height for better visibility
        width=1000,  # Increased width for better visibility
        margin=dict(t=30, b=120, l=60, r=20),  # Increased bottom margin for rotated labels
        xaxis=dict(
            tickangle=-45,
            tickfont=dict(size=10)
        ),
        yaxis=dict(
            # Add gridlines for better readability
            gridcolor='rgba(0,0,0,0.1)',
            gridwidth=1
        ),
        showlegend=False,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        # Add hover template
        hovermode='x unified'
    )

    # Optional: Add custom hover template
    fig.update_traces(
        hovertemplate="<b>Status:</b> %{x}<br>" +
                    "<b>Count:</b> %{y}<br>" +
                    "<extra></extra>"  # This removes the trace name from hover
    )

    
    with col4.popover("Status Distribution",icon=":material/bar_chart:"):
        #st.write("Click on a bar to filter the dataframe.")
        #event_data = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key="plotly_chart",selection_mode="points")
        event_data = st.plotly_chart(fig, use_container_width=True)
        #st.caption("*To clear the selection, click on the selected bar again*")
    
    
    # # Check for selection data
    # if event_data.selection["points"]:
    #     selected_points = event_data.selection["points"]
    #     if selected_points:
    #         # Extract the selected category
    #         selected_category = selected_points[0]["x"]
            
    #         # Filter the dataframe based on the selected category
    #         filtered_df = df[df['Status'] == selected_category]
            
    #         # Display the filtered dataframe
    #         col4.write(f"<span style='color:red'>Filtered DataFrame for Category: {selected_category}</span>",unsafe_allow_html=True)
    #         #st.dataframe(filtered_df)
    #     else:
    #         st.write("No bar selected. Click on a bar to filter the dataframe.")
    # else:
    #     st.write("")
    #     #st.dataframe(df)

    




    # Default columns to display
    default_columns = [
        'ID', 'Status', 'Created On','Agreement Name', 'Client Entity Name', 
            'Requester Name','Agreement Type', 'COE Assessor', 
        'Legal Contact', 'WTW Business(s)'
    ]
    
    # Ensure default columns exist in the dataframe
    default_columns = [col for col in default_columns if col in df.columns]
    
    # Column selector
    all_columns = df.columns.tolist()
    selected_columns = st.multiselect(
        ":material/variable_add: **Select columns to display:**",
        options=all_columns,
        default=default_columns,
    )
    #st.sidebar.ui.badges(badge_list=[("Total records displayed:", "secondary"), (f"{len(filtered_df)}", "secondary")], class_name="flex gap-2", key="main_badges1")
    #st.caption(f"<span class='DefLen'>Total records displayeds: {len(filtered_df)}</span>",unsafe_allow_html=True)
    def data_chunk_choice():
        if 'foo' not in st.session_state:
            return 0
        return st.session_state['foo']
    #st.session_state['foo']
    
    n = 100
    
    list_df = [filtered_df[i:i+n] for i in range(0,filtered_df.shape[0],n)] 
    
    #st.write(f"Length of list_df: {len(list_df)}")
    #reset page number selected if filtered_df is used 
    if st.session_state['foo'] >= len(list_df):
        st.session_state['foo'] = 0
    
    if search_term and len(list_df)==0:
        st.warning("No search results found")
        return
    
    data_l = list_df[data_chunk_choice()] 
    # st.session_state['foo']
    pagecount =st.session_state['foo']
    # st.write(f"Length of list_df: {len(list_df)}")
    #st.write(f"Current page number: {pagecount}")
    
    def style_dataframe(df):
        # Define the CSS styles
        styles = [
            # Header style - darker gray (#404040) with black text
            dict(selector="th", props=[
                ("background-color", "#404040"),
                ("color", "#000000"),
                ("font-weight", "bold"),
                ("padding", "15px")
            ]),
            # Row style
            dict(selector="td", props=[
                ("background-color", "white"),
                ("padding", "15px")
            ])
        ]
        
        # Apply the styling
        styled_df = df.style\
            .set_table_styles(styles)\
            .set_properties(**{
                'background-color': 'white',
                'color': 'black',
            })
        
        return styled_df

    #Dataframe display
    if selected_columns:
        with st.spinner("Preparing data display..."):
            layout = {
                'color': "light",
                'style': {'margin-top': '1px'}
            }
            

                
            styled_df = style_dataframe(data_l[selected_columns])
            st.dataframe(
                styled_df,
                column_config={
                    "ID": st.column_config.TextColumn(
                        "CDR ID",
                        help="Contract Draft Request ID",
                        max_chars=50,
                        pinned=True
                    )
                },
                use_container_width=True,
                hide_index=True
            )
    else:
        st.warning("Please select at least one column to display")

    col2, col1 = st.columns(2)

    #pagination
    pagination_component(len(list_df)+1, layout=layout, key="foo")

    #page count and download excel button
    if pagecount == 0:
        col2.caption(f"**Total records displayed**: {len(data_l)} of {len(filtered_df)}")
    else:
        if len(list_df)==pagecount:
            FinalPageCount =   (len(filtered_df) - n*(pagecount-1)) + n*(pagecount-1)
            col2.caption(f"Total records displayed: {FinalPageCount+1} of {len(filtered_df)}")
        else:
            col2.caption(f"Total records displayed: {n*pagecount+1} of {len(filtered_df)}")
    if col1.button(":material/download: Download Excel File"):
            show_download_dialog(filtered_df, selected_columns)
            


#if __name__ == "__main__":
main()