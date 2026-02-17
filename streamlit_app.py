# Added to session state
if 'current_broncos_tweets' not in st.session_state:
    st.session_state.current_broncos_tweets = []

if 'current_nuggets_tweets' not in st.session_state:
    st.session_state.current_nuggets_tweets = []

# When scanning, store tweets
top_broncos, top_nuggets = get_top_debate_tweets(...)
st.session_state.current_broncos_tweets = top_broncos
st.session_state.current_nuggets_tweets = top_nuggets

# Display from session state (persists across reruns!)
if st.session_state.current_broncos_tweets or st.session_state.current_nuggets_tweets:
    top_broncos = st.session_state.current_broncos_tweets
    top_nuggets = st.session_state.current_nuggets_tweets
    # ... display tweets and rewrites
```

---

## 🎯 How It Works Now:

### Flow 1: Initial Scan
```
1. Click "Scan for Viral Debates"
2. Tweets fetched from Twitter
3. Tweets STORED in session state
4. Tweets displayed
```

### Flow 2: Generate Rewrites
```
1. Click "Generate Rewrites" on Tweet #1
2. AI generates 4 rewrites
3. Rewrites STORED in session state
4. Page reruns (refreshes)
5. Tweets STILL THERE (from session state)
6. Rewrites APPEAR below tweet
7. You edit them
8. You click "Copy"
```

### Flow 3: Clear Everything
```
1. Click "Clear History"
2. Clears shown_tweet_ids
3. Clears generated_rewrites
4. Clears current_broncos_tweets
5. Clears current_nuggets_tweets
6. Fresh start!
