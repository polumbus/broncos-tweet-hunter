import streamlit as st
import os
import tweepy
from anthropic import Anthropic
from datetime import datetime, timedelta

st.set_page_config(page_title="Broncos Tweet Hunter", layout="wide")

st.markdown("""
<style>
.main { background-color: #000000; color: #e7e9ea; }
.stButton>button {
background-color: #1d9bf0;
color: white;
border-radius: 20px;
border: none;
font-weight: bold;
}
.tweet-card {
background-color: #16181c;
border: 1px solid #2f3336;
border-radius: 16px;
padding: 16px;
margin: 12px 0;
}
.tweet-header {
display: flex;
align-items: center;
margin-bottom: 12px;
gap: 10px;
}
.tweet-text {
font-size: 15px;
line-height: 20px;
color: #e7e9ea;
margin-bottom: 12px;
}
.tweet-metrics {
display: flex;
gap: 20px;
color: #71767b;
font-size: 13px;
margin: 12px 0;
}
.metric-high { color: #f91880; font-weight: bold; }
.rewrite-preview {
background-color: #1c1f23;
border-left: 3px solid #1d9bf0;
padding: 12px;
margin: 8px 0;
border-radius: 8px;
font-size: 14px;
}
.priority-badge {
display: inline-block;
padding: 4px 12px;
border-radius: 12px;
font-size: 12px;
font-weight: bold;
}
.bo-nix { background-color: #ff4500; color: white; }
.sean-payton { background-color: #ff8c00; color: white; }
.broncos { background-color: #fb4f14; color: white; }
.tweet-media {
margin: 12px 0;
border-radius: 12px;
overflow: hidden;
}
.tweet-link {
display: inline-block;
padding: 8px 16px;
background-color: #1d9bf0;
color: white;
text-decoration: none;
border-radius: 20px;
font-weight: bold;
margin-top: 8px;
}
.tweet-link:hover {
background-color: #1a8cd8;
}
</style>
""", unsafe_allow_html=True)

os.environ["TWITTER_BEARER_TOKEN"] = st.secrets["TWITTER_BEARER_TOKEN"]
os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]

client = Anthropic()
client_twitter = tweepy.Client(bearer_token=os.environ["TWITTER_BEARER_TOKEN"], wait_on_rate_limit=True)

st.title("🏈 Broncos Tweet Hunter")
st.caption("Find viral Broncos debates from the last 48 hours")

def determine_priority(tweet_text):
"""Determine ranking priority based on content"""
text_lower = tweet_text.lower()

if "bo nix" in text_lower or "bo mix" in text_lower:
return {"rank": 1, "label": "🔥 BO NIX", "color": "bo-nix", "priority": 1000000}
elif "sean payton" in text_lower or "payton" in text_lower:
return {"rank": 2, "label": "⚡ SEAN PAYTON", "color": "sean-payton", "priority": 500000}
else:
return {"rank": 3, "label": "🏈 BRONCOS", "color": "broncos", "priority": 100000}

def get_tweet_media(tweet_id):
"""Fetch media (images/videos) attached to a tweet"""
try:
tweet = client_twitter.get_tweet(
id=tweet_id,
tweet_fields=['attachments'],
expansions=['attachments.media_keys'],
media_fields=['url', 'preview_image_url', 'type', 'variants']
)

media_list = []
if tweet.includes and 'media' in tweet.includes:
for media in tweet.includes['media']:
media_list.append({
'type': media.data['type'],
'url': media.data.get('url'),
'preview_url': media.data.get('preview_image_url')
})
return media_list
except:
return []

def search_viral_tweets(keywords, hours=48):
"""Search for viral tweets"""
query = " OR ".join([f'"{k}"' for k in keywords]) + " -is:retweet lang:en"
start_time = datetime.utcnow() - timedelta(hours=hours)

try:
tweets = client_twitter.search_recent_tweets(
query=query,
max_results=100,
start_time=start_time,
tweet_fields=['public_metrics', 'created_at'],
expansions=['author_id'],
user_fields=['username', 'name']
)

if not tweets.data:
return []

users = {user.id: user for user in tweets.includes['users']}
scored_tweets = []

for tweet in tweets.data:
metrics = tweet.public_metrics
priority_info = determine_priority(tweet.text)

engagement_score = (metrics['reply_count'] * 1000) + priority_info['priority']

user = users.get(tweet.author_id)

scored_tweets.append({
'id': tweet.id,
'text': tweet.text,
'author': user.username if user else 'Unknown',
'author_name': user.name if user else 'Unknown',
'created_at': tweet.created_at,
'likes': metrics['like_count'],
'retweets': metrics['retweet_count'],
'replies': metrics['reply_count'],
'impressions': metrics.get('impression_count', 0),
'engagement_score': engagement_score,
'priority': priority_info,
'url': f"https://twitter.com/{user.username if user else 'twitter'}/status/{tweet.id}"
})

scored_tweets.sort(key=lambda x: x['engagement_score'], reverse=True)
return scored_tweets[:10]

except Exception as e:
st.error(f"Error: {str(e)}")
return []

def generate_rewrites(original_tweet):
"""Generate all 4 rewrite styles at once"""
styles = {
"Default": "Rewrite this tweet in Tyler's voice as a Broncos analyst. Keep it punchy and real.",
"Analytical": "Rewrite with deep analysis. What would a former player see that others don't?",
"Controversial": "Rewrite as a spicy take. Call out bad decisions. Make it debatable.",
"Personal": "Rewrite with personal playing experience. Reference the locker room."
}

rewrites = {}

for style_name, prompt in styles.items():
try:
message = client.messages.create(
model="claude-3-5-sonnet-20241022",
max_tokens=280,
messages=[{
"role": "user",
"content": f"""You are Tyler, a Denver Broncos analyst and former player.

Original tweet: "{original_tweet}"

{prompt}

Keep it under 280 characters. Sound like Tyler - insider perspective, conversational, punchy."""
}]
)
rewrites[style_name] = message.content[0].text
except Exception as e:
rewrites[style_name] = f"ERROR: {str(e)}"

return rewrites

if st.button("🔍 Scan for Viral Broncos Debates", use_container_width=True):
with st.spinner("Scanning Twitter for controversial Broncos content..."):
keywords = ["Denver Broncos", "Sean Payton", "Bo Nix", "Broncos"]
tweets = search_viral_tweets(keywords)

if tweets:
st.success(f"✅ Found {len(tweets)} viral debates! Sorted by controversy (reply count).")

for tweet in tweets:
st.markdown(f"""
<div class="tweet-card">
<div class="tweet-header">
<span class="priority-badge {tweet['priority']['color']}">{tweet['priority']['label']}</span>
<strong>{tweet['author_name']}</strong> @{tweet['author']}
</div>
<div class="tweet-text">{tweet['text']}</div>
</div>
""", unsafe_allow_html=True)

# Display media (images/videos)
media = get_tweet_media(tweet['id'])
if media:
for item in media:
if item['type'] == 'photo' and item['url']:
st.image(item['url'], use_column_width=True)
elif item['type'] == 'video' and item['preview_url']:
st.image(item['preview_url'], caption="Video thumbnail (click link to view)", use_column_width=True)

# Tweet metrics and link
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("💬 Replies", tweet['replies'])
col2.metric("❤️ Likes", tweet['likes'])
col3.metric("🔄 Retweets", tweet['retweets'])
col4.metric("👁️ Impressions", tweet['impressions'])
col5.markdown(f"<a href='{tweet['url']}' target='_blank' class='tweet-link'>View on Twitter →</a>", unsafe_allow_html=True)

st.write("")

# Generate all 4 rewrites
with st.spinner("Generating rewrites in your voice..."):
rewrites = generate_rewrites(tweet['text'])

st.markdown("**✍️ Your Rewrites (Pick One to Edit & Post):**")

col1, col2 = st.columns(2)

with col1:
st.markdown(f"<div class='rewrite-preview'><strong>Default:</strong><br>{rewrites['Default']}</div>", unsafe_allow_html=True)
st.markdown(f"<div class='rewrite-preview'><strong>Analytical:</strong><br>{rewrites['Analytical']}</div>", unsafe_allow_html=True)

with col2:
st.markdown(f"<div class='rewrite-preview'><strong>Controversial:</strong><br>{rewrites['Controversial']}</div>", unsafe_allow_html=True)
st.markdown(f"<div class='rewrite-preview'><strong>Personal:</strong><br>{rewrites['Personal']}</div>", unsafe_allow_html=True)

st.markdown("---")
else:
st.warning("No tweets found. Try again in a few moments!")




