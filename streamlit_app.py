```python
import streamlit as st
import tweepy
from anthropic import Anthropic
from datetime import datetime, timedelta
import os

st.set_page_config(page_title="Broncos Tweet Hunter", layout="wide")
st.title("🏈 Broncos Tweet Hunter")
st.write("Find viral Broncos & Nuggets content from the last 48 hours")

bearer_token = os.getenv("TWITTER_BEARER_TOKEN")
api_key = os.getenv("ANTHROPIC_API_KEY")

if not bearer_token or not api_key:
st.error("API keys missing!")
st.stop()

client = Anthropic()
client_twitter = tweepy.Client(bearer_token=bearer_token, wait_on_rate_limit=True)

if st.button("🔍 Scan for Viral Tweets"):
st.write("Searching...")
st.write("✅ Tool is working!")
```
