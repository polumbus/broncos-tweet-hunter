import os
from datetime import datetime, timedelta
from anthropic import Anthropic

# Initialize Anthropic client
client = Anthropic()
anthropic_key = os.getenv("ANTHROPIC_API_KEY")

# Simulate tweet data (since we're starting simple)
SAMPLE_TWEETS = [
    {
        "text": "Bo Nix's injury is worse than Sean Payton is letting on. Mark my words.",
        "author": "@NFLAnalyst1",
        "likes": 2450,
        "retweets": 890,
        "replies": 340,
        "timestamp": "2 hours ago"
    },
    {
        "text": "Payton's comments about Bo's ankle being 'predisposed' are throwing the locker room off",
        "author": "@DenverSports",
        "likes": 3200,
        "retweets": 1100,
        "replies": 520,
        "timestamp": "4 hours ago"
    },
    {
        "text": "Trading for a running back at 11-12M? That's Walmart money but Hall is different",
        "author": "@RosterTalk",
        "likes": 1890,
        "retweets": 670,
        "replies": 280,
        "timestamp": "6 hours ago"
    },
    {
        "text": "Jokic just dropped 35 points and nobody's talking about it. Nuggets are different",
        "author": "@NBAHot",
        "likes": 4100,
        "retweets": 1450,
        "replies": 600,
        "timestamp": "3 hours ago"
    },
    {
        "text": "Davis Webb leaving would be HUGE. He's the bridge between Payton and Bo",
        "author": "@BroncosInsider",
        "likes": 2100,
        "retweets": 750,
        "replies": 410,
        "timestamp": "5 hours ago"
    }
]

ANALYST_VOICE = """You are Tyler, a Denver Broncos analyst and former player. Your voice:
- Insider perspective (you know team dynamics from playing)
- Conversational and smart (not generic)
- Mix analysis with personality and humor
- Ask rhetorical questions to engage readers
- Reference your playing experience
- Short, punchy paragraphs
- Willing to have spicy takes
- Examples: 'Bo's presser was a DIRECT RESPONSE to Sean', 'It's Walmart money', 'this bridge matters'"""

def generate_rewrite(tweet_text, style="default"):
    """Use Claude to rewrite tweet in your voice"""
    
    style_prompts = {
        "default": f"Rewrite this tweet in Tyler's voice as a Broncos analyst. Keep it under 280 characters. Sound conversational and smart: {tweet_text}",
        "analytical": f"Rewrite this as a deep analytical take from Tyler (former Broncos player). Break down the strategy/implications. Under 280 chars: {tweet_text}",
        "controversial": f"Rewrite this as a spicy hot take from Tyler. Make it debate-worthy. Keep it under 280 chars: {tweet_text}",
        "personal": f"Rewrite this from Tyler's personal experience as a former player. Reference the locker room/playing experience. Under 280 chars: {tweet_text}"
    }
    
    prompt = style_prompts.get(style, style_prompts["default"])
    
    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=300,
        system=ANALYST_VOICE,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    return message.content[0].text

# Streamlit UI
import streamlit as st

st.set_page_config(page_title="Broncos Tweet Hunter", layout="wide")

# Custom CSS for Broncos colors
st.markdown("""
    <style>
    .stApp {
        background-color: #001f3f;
        color: white;
    }
    .tweet-card {
        background-color: #003d7a;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
        border-left: 4px solid #FB4F14;
    }
    .engagement {
        color: #FB4F14;
        font-weight: bold;
    }
    .header {
        color: #FB4F14;
        font-size: 32px;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("<div class='header'>🐴 Broncos Tweet Hunter</div>", unsafe_allow_html=True)
st.markdown("**85% Broncos | 15% Nuggets** - Find viral content from last 48 hours")

# Main content
st.subheader("🔥 Viral Tweets (Last 48 Hours)")

for i, tweet in enumerate(SAMPLE_TWEETS):
    st.markdown(f"""
    <div class='tweet-card'>
        <b>{tweet['author']}</b> · {tweet['timestamp']}<br>
        {tweet['text']}<br><br>
        <span class='engagement'>❤️ {tweet['likes']:,} · 🔄 {tweet['retweets']:,} · 💬 {tweet['replies']:,}</span>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("Default Rewrite", key=f"default_{i}"):
            rewrite = generate_rewrite(tweet['text'], "default")
            st.write(rewrite)
    with col2:
        if st.button("Analytical", key=f"analytical_{i}"):
            rewrite = generate_rewrite(tweet['text'], "analytical")
            st.write(rewrite)
    with col3:
        if st.button("Controversial", key=f"controversial_{i}"):
            rewrite = generate_rewrite(tweet['text'], "controversial")
            st.write(rewrite)
    with col4:
        if st.button("Personal", key=f"personal_{i}"):
            rewrite = generate_rewrite(tweet['text'], "personal")
            st.write(rewrite)

st.markdown("---")
st.markdown(f"**Cost Tracker:** Claude API usage only (~$0.01 per rewrite)")
