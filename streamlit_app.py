python
import streamlit as st
import os
import tweepy
from anthropic import Anthropic
from datetime import datetime, timedelta
import json

st.set_page_config(page_title="Broncos Tweet Hunter", layout="wide", initial_sidebar_state="collapsed")

# Set environment variables
os.environ["TWITTER_BEARER_TOKEN"] = st.secrets["TWITTER_BEARER_TOKEN"]
os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]

# Initialize clients
client = Anthropic()
client_twitter = tweepy.Client(bearer_token=os.environ["TWITTER_BEARER_TOKEN"], wait_on_rate_limit=True)

# Custom CSS for Twitter-like appearance
st.markdown("""
<style>
* {
font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
}

.tweet-card {
border: 1px solid #e1e8ed;
border-radius: 16px;
padding: 16px;
margin: 12px 0;
background: white;
transition: background-color 0.2s;
}

.tweet-card:hover {
background-color: #f7f9fa;
}

.tweet-header {
display: flex;
justify-content: space-between;
align-items: center;
margin-bottom: 12px;
}

.tweet-author {
font-weight: 700;
color: #0f1419;
font-size: 15px;
}

.tweet-handle {
color: #536471;
font-size: 15px;
}

.tweet-text {
color: #0f1419;
font-size: 15px;
line-height: 1.5;
margin: 12px 0;
word-wrap: break-word;
}

.tweet-metrics {
display: flex;
gap: 16px;
color: #536471;
font-size: 13px;
margin: 12px 0;
padding: 12px 0;
border-top: 1px solid #e1e8ed;
border-bottom: 1px solid #e1e8ed;
}

.metric-item {
display: flex;
gap: 4px;
}

.metric-number {
font-weight: 700;
color: #0f1419;
}

.ranking-badge {
display: inline-block;
padding: 4px 12px;
border-radius: 20px;
font-size: 12px;
font-weight: 700;
margin-bottom: 8px;
}

.rank-bo-nix {
background-color: #ffe0e6;
color: #c91c1c;
}

.rank-payton {
background-color: #fff3cd;
color: #ff6b35;
}

.rank-other {
background-color: #e3f2fd;
color: #1976d2;
}

.rewrite-section {
background-color: #f7f9fa;
border-radius: 16px;
padding: 16px;
margin-top: 12px;
}

.action-buttons {
display: flex;
gap: 8px;
margin-top: 12px;
flex-wrap: wrap;
}
</style>
""", unsafe_allow_html=True)

# Page title
st.markdown("# 🏈 BRONCOS TWEET HUNTER")
st.markdown("*Find trending Broncos discussion → Rewrite or generate → Post to your audience*")

# Quick stats
col1, col2, col3 = st.columns(3)
col1.metric("⏱️ Time to scan", "2-3 min")
col2.metric("📊 Tweets found", "10-15")
col3.metric("🚀 Ready to post", "Instantly")

st.markdown("---")

# RANKING SYSTEM
def get_ranking(text):
"""Determine ranking priority based on content"""
text_lower = text.lower()

bo_nix_keywords = ["bo nix", "bo nicks", "nix", "quarterback", "qb"]
payton_keywords = ["sean payton", "payton", "coach", "coaching decision", "offense"]

bo_mentions = sum(1 for keyword in bo_nix_keywords if keyword in text_lower)
payton_mentions = sum(1 for keyword in payton_keywords if keyword in text_lower)

if bo_mentions > 0:
return {"rank": 1, "label": "🔥 BO NIX", "color": "rank-bo-nix", "priority": 1000000}
elif payton_mentions > 0:
return {"rank": 2, "label": "⚡ SEAN PAYTON", "color": "rank-payton", "priority": 100000}
else:
return {"rank": 3, "label": "🏈 BRONCOS", "color": "rank-other", "priority": 10000}

def search_viral_tweets(keywords, max_results=50):
"""Search Twitter for viral tweets - prioritize by REPLIES"""
query = " OR ".join([f'"{k}"' for k in keywords]) + " -is:retweet lang:en"
start_time = datetime.utcnow() - timedelta(hours=48)

try:
tweets = client_twitter.search_recent_tweets(
query=query,
max_results=max_results,
start_time=start_time,
tweet_fields=['public_metrics', 'created_at', 'author_id'],
expansions=['author_id'],
user_fields=['username', 'name', 'profile_image_url']
)

if not tweets.data:
return []

users = {user.id: user for user in tweets.includes['users']}
scored_tweets = []

for tweet in tweets.data:
metrics = tweet.public_metrics
ranking = get_ranking(tweet.text)

# PRIORITY: Replies first, then impressions
engagement_score = (metrics['reply_count'] * 1000) + metrics['impression_count']

scored_tweets.append({
'id': tweet.id,
'text': tweet.text,
'author': user.username if user else 'Unknown',
'author_name': user.name if user else 'Unknown',
'created_at': tweet.created_at,
'likes': metrics['like_count'],
'retweets': metrics['retweet_count'],
'replies': metrics['reply_count'],
'impressions': metrics['impression_count'],
'engagement_score': engagement_score,
'ranking': ranking,
'url': f"https://twitter.com/{user.username if user else 'twitter'}/status/{tweet.id}"
})

# Sort by ranking priority, then by reply count (replies weighted heaviest)
scored_tweets.sort(key=lambda x: (x['ranking']['priority'], -x['replies']), reverse=True)
return scored_tweets[:15]

except Exception as e:
st.error(f"Error: {str(e)}")
return []

def rewrite_tweet(text, style="rewrite"):
"""Rewrite or generate new tweet"""

voice = """You are Tyler, a Denver Broncos analyst and former player.
Your voice: insider perspective, conversational but smart, mix analysis with personality,
ask rhetorical questions, short punchy paragraphs, willing to have spicy takes."""

if style == "rewrite":
prompt = f"""{voice}

Original tweet: "{text}"

Rewrite this in your voice. Keep it under 280 characters. Preserve the core message but put it in your own words."""
else:
prompt = f"""{voice}

Based on this topic: "{text}"

Generate a completely NEW tweet take on this topic. Make it punchy, engaging, and something YOUR audience would want to retweet. Under 280 characters."""

try:
message = client.messages.create(
model="claude-3-5-sonnet-20241022",
max_tokens=300,
messages=[{"role": "user", "content": prompt}]
)
return message.content[0].text
except Exception as e:
return f"Error: {str(e)}"

# MAIN SCAN BUTTON
if st.button("🔍 SCAN VIRAL BRONCOS TWEETS", use_container_width=True, key="scan_btn"):
with st.spinner("Scanning Twitter for viral Broncos discussion..."):
keywords = ["Denver Broncos", "Sean Payton", "Bo Nix", "Broncos drama"]
tweets = search_viral_tweets(keywords)

if tweets:
st.success(f"✅ Found {len(tweets)} viral tweets | Sorted by replies")

for i, tweet in enumerate(tweets, 1):
with st.container():
st.markdown(f"""
<div class="tweet-card">
<div class="ranking-badge {tweet['ranking']['color']}">{tweet['ranking']['label']}</div>
<div class="tweet-header">
<div>
<span class="tweet-author">@{tweet['author']}</span>
<span class="tweet-handle">@{tweet['author']}</span>
</div>
<span style="color: #536471; font-size: 13px;">{tweet['created_at'].strftime('%b %d')}</span>
</div>
<div class="tweet-text">{tweet['text']}</div>
<div class="tweet-metrics">
<div class="metric-item"><span class="metric-number">{tweet['replies']:,}</span> Replies</div>
<div class="metric-item"><span class="metric-number">{tweet['retweets']:,}</span> Retweets</div>
<div class="metric-item"><span class="metric-number">{tweet['likes']:,}</span> Likes</div>
<div class="metric-item"><span class="metric-number">{tweet['impressions']:,}</span> Impressions</div>
</div>
</div>
""", unsafe_allow_html=True)

# Options
opt1, opt2 = st.columns(2)

with opt1:
if st.button(f"✏️ Rewrite this tweet", key=f"rewrite_{tweet['id']}"):
rewrite = rewrite_tweet(tweet['text'], "rewrite")
st.session_state[f"rewrite_{tweet['id']}"] = rewrite

with opt2:
if st.button(f"💡 Generate new take", key=f"generate_{tweet['id']}"):
generated = rewrite_tweet(tweet['text'], "generate")
st.session_state[f"generate_{tweet['id']}"] = generated

# Show previews if generated
if f"rewrite_{tweet['id']}" in st.session_state:
rewrite_text = st.session_state[f"rewrite_{tweet['id']}"]
st.markdown(f"""
<div class="rewrite-section">
<strong>📝 Your Rewrite:</strong><br>
{rewrite_text}
</div>
""", unsafe_allow_html=True)

edited = st.text_area(f"Edit before posting:", value=rewrite_text, key=f"edit_rewrite_{tweet['id']}")

col1, col2 = st.columns(2)
with col1:
if st.button(f"📤 Post now", key=f"post_now_{tweet['id']}"):
st.success(f"✅ Would post: {edited[:50]}...")
with col2:
if st.button(f"⏰ Schedule for later", key=f"schedule_{tweet['id']}"):
st.info(f"📅 Ready to schedule: {edited[:50]}...")

if f"generate_{tweet['id']}" in st.session_state:
gen_text = st.session_state[f"generate_{tweet['id']}"]
st.markdown(f"""
<div class="rewrite-section">
<strong>💡 Generated Take:</strong><br>
{gen_text}
</div>
""", unsafe_allow_html=True)

edited = st.text_area(f"Edit before posting:", value=gen_text, key=f"edit_gen_{tweet['id']}")

col1, col2 = st.columns(2)
with col1:
if st.button(f"📤 Post now", key=f"post_now_gen_{tweet['id']}"):
st.success(f"✅ Would post: {edited[:50]}...")
with col2:
if st.button(f"⏰ Schedule for later", key=f"schedule_gen_{tweet['id']}"):
st.info(f"📅 Ready to schedule: {edited[:50]}...")

st.markdown("---")
else:
st.warning("No tweets found. Try again!")
