# auth_manager.py
import sqlite3
import streamlit as st
import streamlit_authenticator as stauth
import os
from dotenv import load_dotenv
from datetime import datetime
import pytz  # Add this import
# Load environment variables
load_dotenv()

# Constants
COOKIE_NAME = 'contract_extractor_cookie'
COOKIE_KEY = "abcde"
COOKIE_EXPIRY_DAYS = 30


class AuthenticationManager:
    def __init__(self):
        self.db_path = 'userdata.db'
        self.names = []
        self.usernames = []
        self.passwords = []
        self.emails = []
        
        # Create or connect to database and load data
        self._ensure_database_exists()
        self.load_user_data()

    def _ensure_database_exists(self):
        """Ensure database and tables exist"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Create users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL
                )
            ''')
            
            # Create userlogs table
            # Inside the _ensure_database_exists method
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS userlogs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    filesize INTEGER NOT NULL,
                    token_count INTEGER NOT NULL,
                    document_length INTEGER NOT NULL,
                    upload_time FLOAT,
                    parse_time FLOAT,
                    extract_time FLOAT,
                    total_process_time FLOAT,
                    upload_timestamp TEXT NOT NULL,
                    request_type TEXT NOT NULL,  -- Add this line
                    FOREIGN KEY (username) REFERENCES users(username)
                )
            ''')
            
            # Check if users table is empty and add default users if needed
            cursor.execute('SELECT COUNT(*) FROM users')
            if cursor.fetchone()[0] == 0:
                default_users = [
                    ('Test User', 'testuser', 'testpass', 'email@example.com'),
                    ('Test User 2', 'testuser2', 'testpass2', 'email2@example.com')
                ]
                cursor.executemany(
                    'INSERT INTO users (name, username, password, email) VALUES (?, ?, ?, ?)',
                    default_users
                )
            
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            st.error(f"Database error: {e}")
            raise

    def get_utc_now(self):
        """Get current time in UTC"""
        return datetime.now(pytz.UTC)

    def format_timestamp(self, dt):
        """Format datetime object for storage (always in UTC)"""
        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)
        return dt.astimezone(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S %z')

    def parse_timestamp(self, timestamp_str):
        """Parse stored timestamp string back to datetime object (in UTC)"""
        return datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S %z').astimezone(pytz.UTC)

    def check_upload_timeout(self, username):
        """Check if user can upload based on their last upload time"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT upload_timestamp 
                FROM userlogs 
                WHERE username = ? 
                ORDER BY upload_timestamp DESC 
                LIMIT 1
            ''', (username,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                last_upload = self.parse_timestamp(result[0])
                current_time = self.get_utc_now()
                time_diff = current_time - last_upload
                seconds_since_last_upload = time_diff.total_seconds()
                
                if seconds_since_last_upload < 60:  # 1 minute timeout
                    seconds_to_wait = int(60 - seconds_since_last_upload)
                    return False, seconds_to_wait
            
            return True, 0
            
        except sqlite3.Error as e:
            st.error(f"Error checking upload timeout: {e}")
            return False, 60

    def check_token_limit(self, parsed_text):
        """
        Check if the document exceeds token limit
        Returns: bool - True if within limit, False if exceeded
        """
        estimated_tokens = len(parsed_text) / 4  # Approximate token count
        if estimated_tokens > 70000:  # 100k token limit
            st.error(f"File exceeds token limit of 100,000 tokens. Estimated tokens: {int(estimated_tokens)}")
            return False
        return True

    def log_file_upload(self, username, filename, filesize, token_count, document_length, 
                    upload_time=None, parse_time=None, extract_time=None, 
                    total_process_time=None, request_type=None):  # Add request_type parameter
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Store timestamp in UTC
            current_time = self.get_utc_now()
            formatted_timestamp = self.format_timestamp(current_time)
            
            cursor.execute('''
                INSERT INTO userlogs 
                (username, filename, filesize, token_count, document_length, 
                upload_time, parse_time, extract_time, total_process_time, 
                upload_timestamp, request_type)  -- Add request_type to the query
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (username, filename, filesize, token_count, document_length, 
                upload_time, parse_time, extract_time, total_process_time, 
                formatted_timestamp, request_type))  # Add request_type to the values
            
            conn.commit()
            conn.close()
            return True
        except sqlite3.Error as e:
            st.error(f"Error logging file upload: {e}")
            return False

    def get_user_logs(self, username=None, limit=None):
        """Retrieve user logs (all timestamps in UTC)"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = 'SELECT * FROM userlogs'
            params = []
            
            if username:
                query += ' WHERE username = ?'
                params.append(username)
            
            query += ' ORDER BY upload_timestamp DESC'
            
            if limit:
                query += ' LIMIT ?'
                params.append(limit)
            
            cursor.execute(query, params)
            logs = cursor.fetchall()
            
            # Keep timestamps in UTC format for display
            result = []
            for row in logs:
                row_dict = dict(row)
                # Parse and format the timestamp to ensure consistent UTC display
                utc_timestamp = self.parse_timestamp(row_dict['upload_timestamp'])
                row_dict['upload_timestamp'] = utc_timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')
                result.append(row_dict)
            
            conn.close()
            return result
        except sqlite3.Error as e:
            st.error(f"Error retrieving logs: {e}")
            return []
        
    def load_user_data(self):
        """Load user data from the database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Clear existing data
            self.names = []
            self.usernames = []
            self.passwords = []
            self.emails = []
            
            # Load data from database
            cursor.execute('SELECT name, username, password, email FROM users')
            users = cursor.fetchall()
            
            # Populate lists
            for user in users:
                self.names.append(user[0])
                self.usernames.append(user[1])
                self.passwords.append(user[2])
                self.emails.append(user[3])
            
            conn.close()
        except sqlite3.Error as e:
            st.error(f"Error loading user data: {e}")
            raise

    def add_user(self, name, username, password, email):
        """Add a new user to the database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                'INSERT INTO users (name, username, password, email) VALUES (?, ?, ?, ?)',
                (name, username, password, email)
            )
            
            conn.commit()
            conn.close()
            
            self.load_user_data()
            return True
        except sqlite3.IntegrityError:
            st.error("Username or email already exists")
            return False
        except Exception as e:
            st.error(f"Error adding user: {e}")
            return False

    def update_user(self, username, updates):
        """Update user information"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            update_query = 'UPDATE users SET '
            update_values = []
            
            for field, value in updates.items():
                if field in ['name', 'password', 'email']:
                    update_query += f"{field} = ?, "
                    update_values.append(value)
            
            if update_values:
                update_query = update_query.rstrip(', ')
                update_query += ' WHERE username = ?'
                update_values.append(username)
                
                cursor.execute(update_query, update_values)
                conn.commit()
            
            conn.close()
            
            self.load_user_data()
            return True
        except Exception as e:
            st.error(f"Error updating user: {e}")
            return False

    def delete_user(self, username):
        """Delete a user from the database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM users WHERE username = ?', (username,))
            conn.commit()
            conn.close()
            
            self.load_user_data()
            return True
        except Exception as e:
            st.error(f"Error deleting user: {e}")
            return False

    def setup_authentication(self):
        """Setup Streamlit authentication"""
        try:
            hasher = stauth.Hasher(self.passwords)
            hashed_passwords = [hasher.hash(password) for password in self.passwords]
            
            credentials = {
                'usernames': {
                    username: {
                        'name': name,
                        'password': hashed_password,
                        'email': email
                    }
                    for username, name, hashed_password, email in zip(
                        self.usernames, self.names, hashed_passwords, self.emails
                    )
                }
            }

            self._initialize_session_state()
            
            authenticator = stauth.Authenticate(
                credentials,
                COOKIE_NAME,
                COOKIE_KEY,
                COOKIE_EXPIRY_DAYS
            )

            authenticator.login("main")

            if st.session_state['authentication_status']:
                authenticator.logout('Logout', 'main')
                
                USER_INPUT = '''
        
                        <div style="text-align: center; margin-bottom: 0%;"><img src="https://media.wtwco.com/-/media/WTW/Logo/Logo_Desktop.svg?iar=0&modified=20220630202346&imgeng=meta_true&hash=56F49BEC51919C8E565A890FBF0C1B85" width=80>
                        
                        </div>
                        
                        '''
                st.sidebar.markdown(USER_INPUT,unsafe_allow_html=True)    
                st.markdown(f'<div class="welcome-msg">Welcome, <b>{st.session_state["name"]}</b></div>', 
                   unsafe_allow_html=True)
    
            elif st.session_state['authentication_status'] is False:
                st.error('Username/password is incorrect')
            
            return st.session_state['authentication_status']
        except Exception as e:
            st.error(f"Authentication error: {e}")
            return False

    def _initialize_session_state(self):
        """Initialize session state variables"""
        session_vars = ['authentication_status', 'name', 'username', 'email']
        for var in session_vars:
            if var not in st.session_state:
                st.session_state[var] = None