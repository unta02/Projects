import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import calendar
import numpy as np

# Page config
st.set_page_config(layout="wide", page_title="Contract Management Dashboard")

# Custom CSS to match the modern, contained look from the screenshot
st.markdown("""
    <style>
    .metric-container {
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        border: 1px solid #eaeaea;
        margin-bottom: 20px;
    }
    .stMetric {
        background-color: white;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #eaeaea;
    }
    .stMetric:hover {
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
    }
    .metric-value {
        font-size: 24px;
        font-weight: bold;
        color: #1f2937;
    }
    .metric-label {
        font-size: 14px;
        color: #6b7280;
    }
    .block-container {
        padding-top: 3rem;
        padding-bottom: 2rem;
    }
    div[data-testid="stHorizontalBlock"]:nth-of-type(4)>div {
        background: white;
    }
    div[data-testid="stHorizontalBlock"]:nth-of-type(5)>div {
        background: white;
    }
    div[data-testid="stHorizontalBlock"]:nth-of-type(5) + div[data-testid="stVerticalBlockBorderWrapper"] {
        background: white;
    }
    </style>
    """, unsafe_allow_html=True)

# Load data
@st.cache_data
def load_data():
    # Change to read_excel instead of read_csv
    df = pd.read_excel("for_coe_dashboard.xlsx")
    
    # Convert date column
    df['Request Received Date'] = pd.to_datetime(df['Request Received Date'])
    
    # Replace blank or NaN values with a default value (e.g., empty string)
   # df['Coordinator'] = df['Coordinator'].fillna('Unknown')
    df['Contract Request'] = df['Contract Request'].fillna('Unknown')
    df['Contract Type'] = df['Contract Type'].fillna('Unknown')
    df['Region'] = df['Region'].fillna('Unknown')
    df['Complexity'] = df['Complexity'].fillna('Unknown')
    
    # Extract month and year from the date column
    df['Month'] = df['Request Received Date'].dt.strftime('%b')  # Abbreviated month name (e.g., Jan, Feb)
    df['Month'] = df['Month'].fillna('Unknown')  # Replace NaN values in the Month column
    df['Year'] = df['Request Received Date'].dt.year  # Extract year
    df['Year'] = df['Year'].fillna(0).astype(int)  # Replace NaN values with 0 and convert to integer
    
    # Rename 'In_COMET' to 'In COMET'
    df = df.rename(columns={'In_COMET': 'In COMET'})
    
    return df

df = load_data()

# Sidebar filters with updated styling
with st.sidebar:
    st.header("Filters")
    
    # Coordinator filter
    # coordinators = sorted(df['Coordinator'].unique())
    # selected_coordinator = st.multiselect("Coordinator", coordinators)
    
    # Date range filter
    date_range = st.date_input(
        "Request Received Date Range",
        value=(df['Request Received Date'].min(), df['Request Received Date'].max()),
        key='date_range'
    )
    
    # Year filter
    years = sorted(df[df['Year'] != 0]['Year'].unique(), reverse=True)  # Sort years in descending order, excluding 0
    selected_years = st.multiselect("Year", years)
    
    # Month filter
    # Sort months chronologically, handling 'Unknown' values
    month_order = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    months = sorted(df['Month'].unique(), key=lambda x: month_order.index(x) if x in month_order else len(month_order))
    selected_months = st.multiselect("Month", months)
    
    # Other filters
    contract_requests = sorted(df['Contract Request'].unique())
    selected_contract_request = st.multiselect("Contract Request", contract_requests)
    
    contract_types = sorted(df['Contract Type'].unique())
    selected_contract_type = st.multiselect("Contract Type", contract_types)
    
    regions = sorted(df['Region'].unique())
    selected_region = st.multiselect("Region", regions)
    
    complexity_levels = sorted(df['Complexity'].unique())
    selected_complexity = st.multiselect("Complexity", complexity_levels)

# Apply filters
filtered_df = df.copy()
# if selected_coordinator:
#     filtered_df = filtered_df[filtered_df['Coordinator'].isin(selected_coordinator)]
if selected_contract_request:
    filtered_df = filtered_df[filtered_df['Contract Request'].isin(selected_contract_request)]
if selected_contract_type:
    filtered_df = filtered_df[filtered_df['Contract Type'].isin(selected_contract_type)]
if selected_region:
    filtered_df = filtered_df[filtered_df['Region'].isin(selected_region)]
if selected_complexity:
    filtered_df = filtered_df[filtered_df['Complexity'].isin(selected_complexity)]
if selected_months:
    filtered_df = filtered_df[filtered_df['Month'].isin(selected_months)]
if selected_years:
    filtered_df = filtered_df[filtered_df['Year'].isin(selected_years)]

# Apply date range filter
if date_range and len(date_range) == 2:  # Ensure date_range has exactly two values
    start_date, end_date = date_range
    filtered_df = filtered_df[
        (filtered_df['Request Received Date'] >= pd.to_datetime(start_date)) &
        (filtered_df['Request Received Date'] <= pd.to_datetime(end_date))
    ]

# Top metrics in containers
col1, col2, col3, col4 = st.columns(4)

with col1:
    total_requests = len(filtered_df)
    st.metric("Request Received March - YTD", f"{total_requests:,}")

with col2:
    comet_coe = len(filtered_df[filtered_df['In COMET'] == 'Yes'])  # Updated column name
    st.metric("COMET Contract Request with COE YTD", f"{comet_coe:,}")

with col3:
    contracts_uploaded = len(filtered_df[filtered_df['Contract Request'] == 'Contract Upload'])
    st.metric("Contracts Uploaded In_COMET YTD", f"{contracts_uploaded:,}")

with col4:
    coe_uploads = len(filtered_df[
        (filtered_df['Contract Request'] == 'Contract Upload') & 
        (filtered_df['In COMET'] == 'Yes')  # Updated column name
    ])
    st.metric("Contracts In_COMET uploaded by COE YTD", f"{coe_uploads:,}")

# Visualizations in containers
col1, col2 = st.columns(2)

with col1:
    pie_chart1_container = st.container(border=True)
    with pie_chart1_container:
        region_counts = filtered_df['Region'].value_counts().reset_index()
        region_counts.columns = ['Region', 'Count']
        
        fig_region = px.pie(
            region_counts,
            names='Region',
            values='Count',
            title='Contract Reviews by Region',
            hover_data=['Count'],
            custom_data=['Count']
        )
        fig_region.update_traces(
            hovertemplate="<b>Region:</b> %{label}<br>" +
                         "<b>Count:</b> %{value}<br>" +
                         "<b>Percentage:</b> %{percent}<extra></extra>"
        )
        fig_region.update_layout(
            plot_bgcolor='white',
            paper_bgcolor='white',
            margin=dict(t=40, l=20, r=20, b=20)
        )
        st.plotly_chart(fig_region, use_container_width=True)

with col2:
    pie_chart2_container = st.container(border=True)
    with pie_chart2_container:
        uploads_by_region = filtered_df[filtered_df['Contract Request'] == 'Contract Upload']
        region_upload_counts = uploads_by_region['Region'].value_counts().reset_index()
        region_upload_counts.columns = ['Region', 'Count']
        
        fig_uploads = px.pie(
            region_upload_counts,
            names='Region',
            values='Count',
            title='Contract Uploads by Region',
            hover_data=['Count'],
            custom_data=['Count']
        )
        fig_uploads.update_traces(
            hovertemplate="<b>Region:</b> %{label}<br>" +
                         "<b>Count:</b> %{value}<br>" +
                         "<b>Percentage:</b> %{percent}<extra></extra>"
        )
        fig_uploads.update_layout(
            plot_bgcolor='white',
            paper_bgcolor='white',
            margin=dict(t=40, l=20, r=20, b=20)
        )
        st.plotly_chart(fig_uploads, use_container_width=True)

# Bar charts - each in separate container
col1, col2 = st.columns(2)

with col1:
    bar_chart1_container = st.container(border=True)
    with bar_chart1_container:
        # Use 'Contract Request' instead of 'Contract Type'
        request_types = filtered_df['Contract Request'].value_counts()
        fig_types = px.bar(
            request_types,
            title='Types of Requests',
            labels={'value': 'Count', 'index': 'Contract Request'}  # Update label
        )
        fig_types.update_layout(
            plot_bgcolor='white',
            paper_bgcolor='white',
            margin=dict(t=40, l=20, r=20, b=20)
        )
        st.plotly_chart(fig_types, use_container_width=True)

with col2:
    bar_chart2_container = st.container(border=True)
    with bar_chart2_container:
        complexity_counts = filtered_df['Complexity'].value_counts()
        fig_complexity = px.bar(
            complexity_counts,
            title='Requests by Complexity',
            labels={'value': 'Count', 'index': 'Complexity'}
        )
        fig_complexity.update_layout(
            plot_bgcolor='white',
            paper_bgcolor='white',
            margin=dict(t=40, l=20, r=20, b=20)
        )
        st.plotly_chart(fig_complexity, use_container_width=True)

# Heatmap in its own container
heatmap_container = st.container(border=True)
with heatmap_container:
    # Create date-related columns and week number
    filtered_df['Week'] = pd.to_datetime(filtered_df['Request Received Date']).dt.isocalendar().week
    filtered_df['Month'] = pd.to_datetime(filtered_df['Request Received Date']).dt.strftime('%b')
    filtered_df['MonthNum'] = pd.to_datetime(filtered_df['Request Received Date']).dt.month
    
    # Aggregate counts by month and week
    weekly_counts = filtered_df.groupby(['Month', 'MonthNum', 'Week']).size().reset_index(name='count')
    
    # Sort months in correct order
    month_order = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    # Create pivot table for heatmap
    heatmap_data = weekly_counts.pivot_table(
        index='Month',
        columns='Week',
        values='count',
        fill_value=None  # Fill NaNs with None to leave them blank
    )
    
    # Reorder months
    heatmap_data = heatmap_data.reindex(month_order)
    
    # Create custom colorscale
    colorscale = [
        [0.0, '#ebedf0'],     # Light gray for zero values
        [0.2, '#9be9a8'],     # Light green
        [0.4, '#40c463'],     # Medium green
        [0.6, '#30a14e'],     # Darker green
        [1.0, '#216e39']      # Darkest green
    ]
    
    # Create text array for cell values
    text_array = heatmap_data.values.astype(str)
    text_array[heatmap_data.isna()] = ''  # Hide NaNs
    text_array[heatmap_data.values == 0] = ''  # Hide zeros
    
    fig = go.Figure(data=go.Heatmap(
        z=heatmap_data.values,
        x=heatmap_data.columns,
        y=heatmap_data.index,
        colorscale=colorscale,
        showscale=True,
        text=text_array,
        texttemplate="%{text}",
        textfont={"size": 10},
        hoverongaps=False,
        hovertemplate='Week: %{x}<br>Month: %{y}<br>Count: %{z}<extra></extra>'
    ))
    
    # Update layout
    fig.update_layout(
        title=dict(
            text='Weekly Request Counts by Month<br>2024',
            x=0.5,
            y=0.95,
            xanchor='center',
            yanchor='top',
            font=dict(size=16)
        ),
        plot_bgcolor='white',
        paper_bgcolor='white',
        margin=dict(t=80, l=50, r=50, b=20),
        height=400,
        xaxis=dict(
            title='Week Number',
            side='bottom',  # Move week labels to the bottom
            tickmode='linear',
            tickangle=0,
            showgrid=False,
            showline=False,
        ),
        yaxis=dict(
            title='Month',
            showgrid=False,
            showline=False,
            ticks='',
            ticksuffix='  ',  # Add some padding
        ),
        coloraxis_colorbar=dict(
            title='Count',
            thicknessmode='pixels',
            thickness=20,
            lenmode='pixels',
            len=300,
            yanchor='top',
            y=1,
            ypad=0,
            xpad=20
        )
    )
    
    st.plotly_chart(fig, use_container_width=True)