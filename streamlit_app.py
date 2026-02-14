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
    st.error("API keys missing! Add them in Streamlit Secrets.")
    st.stop()

client = Anthropic(api_key=api_key)
client_twitter = tweepy.Client(bearer_token=bearer_token, wait_on_rate_limit=True)

st.success("✅ Connected to Twitter and Claude AI!")

if st.button("🔍 Scan for Viral Tweets"):
    st.write("Searching Twitter for viral Broncos content...")
    
    try:
        # Search for Broncos tweets
        query = "Denver Broncos OR Sean Payton OR Bo Nix -is:retweet lang:en"
        start_time = datetime.utcnow() - timedelta(hours=48)
        
        tweets = client_twitter.search_recent_tweets(
            query=query,
            max_results=10,
            start_time=start_time,
            tweet_fields=['public_metrics', 'created_at'],
            expansions=['author_id'],
            user_fields=['username']
        )
        
        if tweets.data:
            st.success(f"Found {len(tweets.data)} viral tweets!")
            
            for tweet in tweets.data:
                st.divider()
                metrics = tweet.public_metrics
                st.write(f"**@{tweet.author_id}**")
                st.write(f"❤️ {metrics['like_count']} | 🔄 {metrics['retweet_count']} | 💬 {metrics['reply_count']}")
                st.write(tweet.text)
                
                if st.button(f"Rewrite This Tweet", key=tweet.id):
                    with st.spinner("AI is rewriting..."):
                        message = client.messages.create(
                            model="claude-3-5-sonnet-20241022",
                            max_tokens=280,
                            messages=[
                                {
                                    "role": "user",
                                    "content": f"Rewrite this tweet as Tyler, a Broncos analyst and former player. Keep it under 280 characters, punchy and real: {tweet.text}"
                                }
                            ]
                        )
                        st.success("✅ AI Rewrite:")
                        st.write(message.content[0].text)
        else:
            st.warning("No tweets found. Try again later!")
            
    except Exception as e:
        st.error(f"Error: {str(e)}")


