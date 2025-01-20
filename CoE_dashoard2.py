import pandas as pd
import streamlit as st
import plotly.express as px
from calendar import month_abbr
from datetime import datetime

# Load the data
data = pd.read_excel("for_coe_dashboard.xlsx")

# Ensure the date column is in datetime format
data['Request Received Date'] = pd.to_datetime(data['Request Received Date'], errors='coerce')

# Filter rows with valid dates
data = data.dropna(subset=['Request Received Date'])

# Add a Year column for filtering
data['Year'] = data['Request Received Date'].dt.year

# Handle invalid years (if any)
data['Year'] = data['Year'].fillna(0).astype(int)  # Replace NaN values with 0 and convert to integer

# Get the current year as the default year
current_year = datetime.now().year

# Streamlit app
st.title("Weekly Request Heatmap")

# Year selection dropdown
valid_years = sorted(data[data['Year'] != 0]['Year'].unique(), reverse=True)  # Sort years in descending order, excluding 0
selected_year = st.selectbox(
    "Select Year",
    options=valid_years,  # Show valid years
    index=0  # Default to the first option (current year or latest year)
)

# Filter data for the selected year
filtered_data = data[data['Year'] == selected_year]

# Define a function to calculate the week number within each month
def get_week_in_month(date):
    first_day = date.replace(day=1)
    week_in_month = (date.day + first_day.weekday()) // 7 + 1
    return week_in_month

# Add week and month columns
filtered_data['Week'] = filtered_data['Request Received Date'].apply(get_week_in_month)
filtered_data['Month'] = filtered_data['Request Received Date'].dt.strftime('%b')

# Count requests per week and month
heatmap_data = filtered_data.groupby(['Month', 'Week']).size().unstack(fill_value=0)

# Generate the full range of weeks and months for the selected year
all_months = list(month_abbr)[1:]  # All months (Jan, Feb, ..., Dec)
all_weeks = range(1, 6)  # Assume up to 5 weeks per month

# Create a DataFrame with all possible combinations of months and weeks
full_heatmap_data = pd.DataFrame(0, index=all_months, columns=all_weeks)

# Update the full_heatmap_data with the actual data
full_heatmap_data.update(heatmap_data)

# Replace NaN values with 0 and convert to integers
full_heatmap_data = full_heatmap_data.fillna(0).astype(int)

# Melt the DataFrame for Plotly
heatmap_melted = full_heatmap_data.reset_index().melt(id_vars='index', var_name='Week', value_name='Requests')
heatmap_melted.rename(columns={'index': 'Month'}, inplace=True)

# Add a hover text column to show the week range
def get_week_range(month, week):
    # Get the first day of the month
    first_day = datetime.strptime(f"{month} {selected_year}", "%b %Y")
    # Calculate the start and end of the week
    start = first_day.replace(day=1) + pd.Timedelta(days=(week - 1) * 7)
    end = start + pd.Timedelta(days=6)
    return f"Week {week}: {start.strftime('%b %d')} - {end.strftime('%b %d')}"

heatmap_melted['Week Range'] = heatmap_melted.apply(lambda row: get_week_range(row['Month'], row['Week']), axis=1)

# Create the heatmap using Plotly
fig = px.imshow(
    full_heatmap_data,
    labels=dict(x="Week", y="Month", color="Requests"),
    x=full_heatmap_data.columns,
    y=full_heatmap_data.index,
    color_continuous_scale="Purples",  # Use the "Purples" color palette
    text_auto=True  # Automatically add annotations
)

# Update hover template
fig.update_traces(
    hovertemplate="<b>%{y}</b><br>%{x}<br>Requests: %{z}<extra></extra>"
)

# Update layout
fig.update_layout(
    title=f"Heatmap of Weekly Requests by Month and Week ({selected_year})",
    xaxis_title="Week of Month",
    yaxis_title="Month",
    xaxis_nticks=len(all_weeks),
    yaxis_nticks=len(all_months),
    width=800,
    height=600
)

# Display the Plotly figure in Streamlit
st.plotly_chart(fig)

# Optional: Display the raw data for debugging
st.write("Filtered Data:")
st.write(filtered_data.head())
st.write("Heatmap Data:")
st.write(full_heatmap_data)